"""Recommendation service using PostgreSQL embeddings and Neo4j graph data."""

import logging
from typing import Any

import torch
from sentence_transformers import SentenceTransformer

from src.db.neo4j_client import Neo4jClient
from src.db.postgres_client import db
from src.db.redis_client import redis_client

logger = logging.getLogger(__name__)


class RecommendationService:
    def __init__(self):
        device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = SentenceTransformer("all-MiniLM-L6-v2", device=device)
        self.neo4j_client = Neo4jClient()
        self.cache_ttl = 3600  # 1 hour cache for recommendations

    def get_similar_products(self, product_id: str, limit: int = 5) -> list[dict[str, Any]]:
        """
        Get similar products using PostgreSQL embeddings.

        Args:
            product_id: Product ID to find similar products for
            limit: Maximum number of similar products to return

        Returns:
            List of similar products with similarity scores
        """
        cache_key = f"similar_products:{product_id}:{limit}"

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

                # Find similar products using cosine similarity
                cursor.execute(
                    """
                    SELECT 
                        p.id,
                        p.name,
                        p.description,
                        p.price,
                        p.seller_id,
                        c.name as category_name,
                        1 - (pe.embedding <=> %s::vector) as similarity_score
                    FROM products p
                    JOIN product_embeddings pe ON p.id = pe.product_id
                    JOIN categories c ON p.category = c.name
                    WHERE p.id != %s
                    ORDER BY pe.embedding <=> %s::vector
                    LIMIT %s
                """,
                    (target_embedding, product_id, target_embedding, limit),
                )

                similar_products = [dict(row) for row in cursor.fetchall()]

                # Cache the result
                redis_client.set_json(cache_key, similar_products, self.cache_ttl)

                return similar_products

        except Exception as e:
            logger.error(f"Error getting similar products: {e}")
            return []

    def get_also_bought_recommendations(self, product_id: str, limit: int = 5) -> list[dict[str, Any]]:
        """
        Get "also bought" recommendations using Neo4j.

        Args:
            product_id: Product ID to get recommendations for
            limit: Maximum number of recommendations

        Returns:
            List of products frequently bought together
        """
        cache_key = f"also_bought:{product_id}:{limit}"

        # Check cache first
        cached_result = redis_client.get_json(cache_key)
        if cached_result:
            return cached_result

        try:
            with self.neo4j_client.driver.session() as session:
                # Find products that were bought by users who also bought the target product
                result = session.run(
                    """
                    MATCH (target:Product {id: $product_id})<-[:PURCHASED]-(user:User)-[:PURCHASED]->(rec:Product)
                    WHERE rec.id <> target.id
                    WITH rec, COUNT(user) as purchase_count
                    ORDER BY purchase_count DESC
                    LIMIT $limit
                    RETURN rec.id as product_id, rec.name as name, rec.price as price, purchase_count
                """,
                    product_id=product_id,
                    limit=limit,
                )

                recommendations = []
                for record in result:
                    pid = record.get("product_id")
                    details = self._get_product_details(pid)
                    if details:
                        recommendations.append(
                            {
                                **details,
                                "purchase_count": record.get("purchase_count"),
                                "recommendation_score": record.get("purchase_count"),
                            }
                        )

                # Cache the result
                redis_client.set_json(cache_key, recommendations, self.cache_ttl)

                return recommendations

        except Exception as e:
            logger.error(f"Error getting also bought recommendations: {e}")
            return []

    def get_frequently_bought_together(self, product_id: str, limit: int = 3) -> list[dict[str, Any]]:
        """
        Get products frequently bought together with the target product.

        Args:
            product_id: Product ID to find combinations for
            limit: Maximum number of product combinations

        Returns:
            List of product combinations with frequency scores
        """
        cache_key = f"bought_together:{product_id}:{limit}"

        # Check cache first
        cached_result = redis_client.get_json(cache_key)
        if cached_result:
            return cached_result

        try:
            with self.neo4j_client.driver.session() as session:
                # Find products bought in the same order as the target product
                result = session.run(
                    """
                    MATCH (target:Product {id: $product_id})<-[:PURCHASED]-(user:User)-[:PURCHASED]->(other:Product)
                    WHERE other.id <> target.id
                    WITH other, COUNT(user) as frequency
                    ORDER BY frequency DESC
                    LIMIT $limit
                    RETURN other.id as product_id, other.name as name, other.price as price, frequency
                """,
                    product_id=product_id,
                    limit=limit,
                )

                combinations = []
                for record in result:
                    pid = record.get("product_id")
                    details = self._get_product_details(pid)
                    if details:
                        combinations.append(
                            {
                                **details,
                                "frequency": record.get("frequency"),
                                "combination_score": record.get("frequency"),
                            }
                        )

                # Cache the result
                redis_client.set_json(cache_key, combinations, self.cache_ttl)

                return combinations

        except Exception as e:
            logger.error(f"Error getting frequently bought together: {e}")
            return []

    def get_personalized_recommendations(self, user_id: str, limit: int = 10) -> list[dict[str, Any]]:
        """
        Get personalized recommendations based on user's purchase history.

        Args:
            user_id: User ID to get recommendations for
            limit: Maximum number of recommendations

        Returns:
            List of personalized product recommendations
        """
        cache_key = f"personalized:{user_id}:{limit}"

        # Check cache first
        cached_result = redis_client.get_json(cache_key)
        if cached_result:
            return cached_result

        try:
            with self.neo4j_client.driver.session() as session:
                # Get recommendations based on collaborative filtering
                result = session.run(
                    """
                    MATCH (user:User {id: $user_id})-[:PURCHASED]->(product:Product)
                    WITH user, COLLECT(product.id) as purchased_products
                    
                    MATCH (other_user:User)-[:PURCHASED]->(product:Product)
                    WHERE other_user.id <> user.id AND product.id IN purchased_products
                    WITH user, other_user, COUNT(product) as common_purchases
                    ORDER BY common_purchases DESC
                    LIMIT 10
                    
                    MATCH (other_user)-[:PURCHASED]->(rec:Product)
                    WHERE NOT rec.id IN purchased_products
                    WITH rec, COUNT(other_user) as recommendation_strength
                    ORDER BY recommendation_strength DESC
                    LIMIT $limit
                    
                    RETURN rec.id as product_id, rec.name as name, rec.price as price, recommendation_strength
                """,
                    user_id=user_id,
                    limit=limit,
                )

                recommendations = []
                for record in result:
                    pid = record.get("product_id")
                    details = self._get_product_details(pid)
                    if details:
                        recommendations.append(
                            {
                                **details,
                                "recommendation_strength": record.get("recommendation_strength"),
                                "personalization_score": record.get("recommendation_strength"),
                            }
                        )

                # Cache the result
                redis_client.set_json(cache_key, recommendations, self.cache_ttl)

                return recommendations

        except Exception as e:
            logger.error(f"Error getting personalized recommendations: {e}")
            return []

    def get_comprehensive_recommendations(
        self, user_id: str, product_id: str | None = None, limit: int = 10
    ) -> dict[str, Any]:
        """
        Get comprehensive recommendations combining multiple approaches.

        Args:
            user_id: User ID for personalized recommendations
            product_id: Optional product ID for product-based recommendations
            limit: Maximum number of recommendations per category

        Returns:
            Dict containing different types of recommendations
        """
        recommendations = {
            "personalized": self.get_personalized_recommendations(user_id, limit),
            "similar_products": [],
            "also_bought": [],
            "frequently_bought_together": [],
        }

        if product_id:
            recommendations["similar_products"] = self.get_similar_products(product_id, limit)
            recommendations["also_bought"] = self.get_also_bought_recommendations(product_id, limit)
            recommendations["frequently_bought_together"] = self.get_frequently_bought_together(product_id, limit // 2)

        return recommendations

    def _get_product_details(self, product_id: str) -> dict[str, Any] | None:
        """Get product details from PostgreSQL."""
        try:
            with db.get_cursor() as cursor:
                cursor.execute(
                    """
                    SELECT p.*, c.name as category_name
                    FROM products p
                    JOIN categories c ON p.category = c.name
                    WHERE p.id = %s
                """,
                    (product_id,),
                )

                result = cursor.fetchone()
                return dict(result) if result else None

        except Exception as e:
            logger.error(f"Error fetching product details: {e}")
            return None

    def generate_trending_products(self, limit: int = 10) -> list[dict[str, Any]]:
        """
        Generate trending products based on recent purchase activity.

        Args:
            limit: Maximum number of trending products

        Returns:
            List of trending products with popularity scores
        """
        cache_key = f"trending_products:{limit}"

        # Check cache first
        cached_result = redis_client.get_json(cache_key)
        if cached_result:
            return cached_result

        try:
            with self.neo4j_client.driver.session() as session:
                result = session.run(
                    """
                    MATCH (product:Product)<-[purchase:PURCHASED]-(user:User)
                    WHERE purchase.date >= date() - duration('P7D')
                    WITH product, COUNT(purchase) as recent_purchases
                    ORDER BY recent_purchases DESC
                    LIMIT $limit
                    RETURN product.id as product_id, product.name as name, product.price as price, recent_purchases
                """,
                    limit=limit,
                )

                trending_products = []
                for record in result:
                    pid = record.get("product_id")
                    details = self._get_product_details(pid)
                    if details:
                        trending_products.append(
                            {
                                **details,
                                "recent_purchases": record.get("recent_purchases"),
                                "trending_score": record.get("recent_purchases"),
                            }
                        )

                # Cache for shorter time (30 minutes for trending data)
                redis_client.set_json(cache_key, trending_products, 1800)

                return trending_products

        except Exception as e:
            logger.error(f"Error generating trending products: {e}")
            return []

    def clear_recommendation_cache(self, user_id: str | None = None, product_id: str | None = None) -> bool:
        """
        Clear recommendation cache entries.

        Args:
            user_id: Optional user ID to clear specific user cache
            product_id: Optional product ID to clear specific product cache

        Returns:
            True if successful, False otherwise
        """
        try:
            keys_to_clear = []

            if user_id:
                keys_to_clear.extend(redis_client.client.keys(f"personalized:{user_id}:*"))

            if product_id:
                keys_to_clear.extend(redis_client.client.keys(f"similar_products:{product_id}:*"))
                keys_to_clear.extend(redis_client.client.keys(f"also_bought:{product_id}:*"))
                keys_to_clear.extend(redis_client.client.keys(f"bought_together:{product_id}:*"))

            if not user_id and not product_id:
                # Clear all recommendation caches
                keys_to_clear.extend(redis_client.client.keys("personalized:*"))
                keys_to_clear.extend(redis_client.client.keys("similar_products:*"))
                keys_to_clear.extend(redis_client.client.keys("also_bought:*"))
                keys_to_clear.extend(redis_client.client.keys("bought_together:*"))
                keys_to_clear.extend(redis_client.client.keys("trending_products:*"))

            if keys_to_clear:
                redis_client.client.delete(*keys_to_clear)
                logger.info(f"Cleared {len(keys_to_clear)} recommendation cache entries")

            return True

        except Exception as e:
            logger.error(f"Error clearing recommendation cache: {e}")
            return False


# Singleton instance
recommendation_service = RecommendationService()
