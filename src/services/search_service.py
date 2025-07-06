"""Semantic search service using vector embeddings."""

import logging
from typing import Any

import torch
from sentence_transformers import SentenceTransformer

from src.db.postgres_client import db
from src.db.redis_client import redis_client

logger = logging.getLogger(__name__)


class SemanticSearchService:
    def __init__(self):
        device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = SentenceTransformer("all-MiniLM-L6-v2", device=device)
        self.cache_ttl = 3600  # 1 hour cache for semantic search results

    def semantic_search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """
        Search products using semantic similarity.

        Args:
            query: Natural language search query
            limit: Maximum number of results

        Returns:
            List of products with similarity scores
        """
        cache_key = f"semantic_search:{hash(query)}:{limit}"

        # Check cache first
        cached_result = redis_client.get_json(cache_key)
        if cached_result:
            return cached_result

        try:
            # Generate embedding for search query
            query_embedding = self.model.encode(query)

            # Find similar products using pgvector cosine similarity
            with db.get_cursor() as cursor:
                cursor.execute(
                    """
                    SELECT 
                        p.id,
                        p.name,
                        p.description,
                        p.price,
                        p.seller_id,
                        p.stock,
                        p.tags,
                        c.name as category_name,
                        1 - (pe.embedding <=> %s::vector) as similarity_score
                    FROM products p
                    JOIN product_embeddings pe ON p.id = pe.product_id
                    JOIN categories c ON p.category = c.name
                    WHERE p.stock > 0
                    ORDER BY pe.embedding <=> %s::vector
                    LIMIT %s
                """,
                    (query_embedding.tolist(), query_embedding.tolist(), limit),
                )

                results = [dict(row) for row in cursor.fetchall()]

                # Cache the results
                redis_client.set_json(cache_key, results, self.cache_ttl)

                return results

        except Exception as e:
            logger.error(f"Error in semantic search: {e}")
            return []

    def more_like_this(self, product_id: str, limit: int = 5) -> list[dict[str, Any]]:
        """
        Find products similar to a given product.

        Args:
            product_id: Product ID to find similar products for
            limit: Maximum number of similar products

        Returns:
            List of similar products with similarity scores
        """
        cache_key = f"more_like_this:{product_id}:{limit}"

        # Check cache first
        cached_result = redis_client.get_json(cache_key)
        if cached_result:
            return cached_result

        try:
            with db.get_cursor() as cursor:
                # Get the target product's embedding
                cursor.execute(
                    """
                    SELECT pe.embedding
                    FROM product_embeddings pe
                    WHERE pe.product_id = %s
                """,
                    (product_id,),
                )

                result = cursor.fetchone()
                if not result:
                    logger.warning(f"No embedding found for product {product_id}")
                    return []

                target_embedding = result["embedding"]

                # Find similar products
                cursor.execute(
                    """
                    SELECT 
                        p.id,
                        p.name,
                        p.description,
                        p.price,
                        p.seller_id,
                        p.stock,
                        p.tags,
                        c.name as category_name,
                        1 - (pe.embedding <=> %s::vector) as similarity_score
                    FROM products p
                    JOIN product_embeddings pe ON p.id = pe.product_id
                    JOIN categories c ON p.category = c.name
                    WHERE p.id != %s AND p.stock > 0
                    ORDER BY pe.embedding <=> %s::vector
                    LIMIT %s
                """,
                    (target_embedding, product_id, target_embedding, limit),
                )

                results = [dict(row) for row in cursor.fetchall()]

                # Cache the results
                redis_client.set_json(cache_key, results, self.cache_ttl)

                return results

        except Exception as e:
            logger.error(f"Error in more_like_this: {e}")
            return []

    def natural_language_search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """
        Process natural language queries and return relevant products.

        Args:
            query: Natural language search query
            limit: Maximum number of results

        Returns:
            List of products matching the natural language query
        """
        # For now, this is the same as semantic search
        # Could be enhanced with NLP preprocessing, query expansion, etc.
        return self.semantic_search(query, limit)

    def hybrid_search(self, query: str, limit: int = 10, semantic_weight: float = 0.7) -> list[dict[str, Any]]:
        """
        Combine semantic search with traditional full-text search.

        Args:
            query: Search query
            limit: Maximum number of results
            semantic_weight: Weight for semantic search (0.0 to 1.0)

        Returns:
            List of products from hybrid search
        """
        cache_key = f"hybrid_search:{hash(query)}:{limit}:{semantic_weight}"

        # Check cache first
        cached_result = redis_client.get_json(cache_key)
        if cached_result:
            return cached_result

        try:
            # Get semantic search results
            semantic_results = self.semantic_search(query, limit * 2)

            # Get traditional full-text search results
            with db.get_cursor() as cursor:
                cursor.execute(
                    """
                    SELECT 
                        p.id,
                        p.name,
                        p.description,
                        p.price,
                        p.seller_id,
                        p.stock,
                        p.tags,
                        c.name as category_name,
                        ts_rank(to_tsvector('english', p.name || ' ' || p.description || ' ' || COALESCE(p.tags, '')), 
                               plainto_tsquery('english', %s)) as text_rank
                    FROM products p
                    JOIN categories c ON p.category = c.name
                    WHERE to_tsvector('english', p.name || ' ' || p.description || ' ' || COALESCE(p.tags, '')) @@ plainto_tsquery('english', %s)
                    AND p.stock > 0
                    ORDER BY text_rank DESC
                    LIMIT %s
                """,
                    (query, query, limit * 2),
                )

                text_results = [dict(row) for row in cursor.fetchall()]

            # Combine results with weighted scoring
            combined_results = {}

            # Add semantic results
            for i, result in enumerate(semantic_results):
                product_id = result["id"]
                semantic_score = result.get("similarity_score", 0)
                combined_results[product_id] = {
                    **result,
                    "semantic_score": semantic_score,
                    "text_score": 0,
                    "hybrid_score": semantic_score * semantic_weight,
                }

            # Add text search results
            for i, result in enumerate(text_results):
                product_id = result["id"]
                text_score = result.get("text_rank", 0)

                if product_id in combined_results:
                    combined_results[product_id]["text_score"] = text_score
                    combined_results[product_id]["hybrid_score"] += text_score * (1 - semantic_weight)
                else:
                    combined_results[product_id] = {
                        **result,
                        "semantic_score": 0,
                        "text_score": text_score,
                        "hybrid_score": text_score * (1 - semantic_weight),
                    }

            # Sort by hybrid score and limit results
            final_results = sorted(combined_results.values(), key=lambda x: x["hybrid_score"], reverse=True)[:limit]

            # Cache the results
            redis_client.set_json(cache_key, final_results, self.cache_ttl)

            return final_results

        except Exception as e:
            logger.error(f"Error in hybrid search: {e}")
            return []

    def generate_embeddings_for_products(self, batch_size: int = 100) -> bool:
        """
        Generate embeddings for products that don't have them.

        Args:
            batch_size: Number of products to process at once

        Returns:
            True if successful, False otherwise
        """
        try:
            with db.get_cursor() as cursor:
                # Get products without embeddings
                cursor.execute(
                    """
                    SELECT p.id, p.name, p.description, p.tags
                    FROM products p
                    LEFT JOIN product_embeddings pe ON p.id = pe.product_id
                    WHERE pe.product_id IS NULL
                    LIMIT %s
                """,
                    (batch_size,),
                )

                products = cursor.fetchall()

                if not products:
                    logger.info("No products need embeddings")
                    return True

                # Generate embeddings
                for product in products:
                    # Combine product text for embedding
                    text_to_embed = f"{product['name']} {product['description'] or ''} {product['tags'] or ''}"
                    embedding = self.model.encode(text_to_embed)

                    # Store embedding
                    cursor.execute(
                        """
                        INSERT INTO product_embeddings (product_id, embedding)
                        VALUES (%s, %s)
                        ON CONFLICT (product_id) DO UPDATE SET
                        embedding = EXCLUDED.embedding,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                        (product["id"], embedding.tolist()),
                    )

                logger.info(f"Generated embeddings for {len(products)} products")
                return True

        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            return False

    def clear_semantic_cache(self) -> bool:
        """Clear all semantic search cache entries."""
        try:
            keys = redis_client.client.keys("semantic_search:*")
            keys.extend(redis_client.client.keys("more_like_this:*"))
            keys.extend(redis_client.client.keys("hybrid_search:*"))

            if keys:
                redis_client.client.delete(*keys)
                logger.info(f"Cleared {len(keys)} semantic search cache entries")

            return True

        except Exception as e:
            logger.error(f"Error clearing semantic cache: {e}")
            return False


# Singleton instance
semantic_search_service = SemanticSearchService()
