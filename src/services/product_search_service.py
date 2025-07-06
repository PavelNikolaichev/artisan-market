"""Product search service with caching capabilities."""

import hashlib
import json
import logging
from typing import Any

from src.db.postgres_client import db
from src.db.redis_client import redis_client

logger = logging.getLogger(__name__)


class ProductSearchService:
    def __init__(self):
        self.cache_ttl = 3600  # 1 hour TTL for search results
        self.cache_hit_count = 0
        self.cache_miss_count = 0

    def _generate_cache_key(self, query: str, filters: dict[str, Any]) -> str:
        """Generate a cache key for search parameters."""
        search_params = {"query": query, "filters": filters}
        params_str = json.dumps(search_params, sort_keys=True)
        # noinspection PyTypeChecker
        return f"search:{hashlib.md5(params_str.encode()).hexdigest()}"

    def get_cache_hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total_requests = self.cache_hit_count + self.cache_miss_count
        if total_requests == 0:
            return 0.0
        return self.cache_hit_count / total_requests

    def search_products(
        self,
        query: str,
        category: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        """
        Search products with full-text search and caching.

        Args:
            query: Search query for name, description, tags
            category: Category name filter (optional)
            min_price: Minimum price filter
            max_price: Maximum price filter
            limit: Maximum number of results
            offset: Pagination offset

        Returns:
            Dict containing products, total count, and cache info
        """
        filters = {
            "category": category,
            "min_price": min_price,
            "max_price": max_price,
            "limit": limit,
            "offset": offset,
        }

        # Generate cache key
        cache_key = self._generate_cache_key(query, filters)

        # Try to get from cache first
        cached_result = redis_client.get_json(cache_key)
        if cached_result:
            self.cache_hit_count += 1
            logger.info(f"Cache hit for search: {query}")
            return {**cached_result, "cache_hit": True, "cache_hit_rate": self.get_cache_hit_rate()}

        # Cache miss - perform database search
        self.cache_miss_count += 1
        logger.info(f"Cache miss for search: {query}")

        # Build SQL query with full-text search
        sql_conditions = []
        params = []

        # Full-text search on name, description, and tags
        if query:
            sql_conditions.append("""
                (p.name ILIKE %s OR 
                 p.description ILIKE %s OR 
                 p.tags ILIKE %s OR
                 to_tsvector('english', p.name || ' ' || p.description || ' ' || COALESCE(p.tags, '')) @@ plainto_tsquery('english', %s))
            """)
            like_query = f"%{query}%"
            params.extend([like_query, like_query, like_query, query])

        # Category filter
        if category:
            sql_conditions.append("p.category = %s")
            params.append(category)

        # Price filters
        if min_price is not None:
            sql_conditions.append("p.price >= %s")
            params.append(min_price)

        if max_price is not None:
            sql_conditions.append("p.price <= %s")
            params.append(max_price)

        # Build WHERE clause
        where_clause = "WHERE " + " AND ".join(sql_conditions) if sql_conditions else ""

        # Count query
        count_sql = f"""
            SELECT COUNT(*) as total
            FROM products p
            JOIN categories c ON p.category = c.name
            {where_clause}
        """

        # Main query with ranking
        main_sql = f"""
            SELECT 
                p.id,
                p.name,
                p.description,
                p.price,
                p.stock,
                p.tags,
                p.seller_id,
                p.created_at,
                p.updated_at,
                c.name as category_name,
                CASE 
                    WHEN p.name ILIKE %s THEN 3
                    WHEN p.description ILIKE %s THEN 2
                    WHEN p.tags ILIKE %s THEN 1
                    ELSE 0
                END as relevance_score
            FROM products p
            JOIN categories c ON p.category = c.name
            {where_clause}
            ORDER BY relevance_score DESC, p.created_at DESC
            LIMIT %s OFFSET %s
        """

        try:
            with db.get_cursor() as cursor:
                # Get total count
                cursor.execute(count_sql, params)
                total_count = cursor.fetchone()["total"]

                # Get products with relevance scoring
                if query:
                    like_query = f"%{query}%"
                    main_params = [like_query, like_query, like_query] + params + [limit, offset]
                else:
                    main_params = params + [limit, offset]

                cursor.execute(main_sql, main_params)
                products = cursor.fetchall()

                # Convert to dict format
                products_list = [dict(row) for row in products]
                for product in products_list:
                    # Convert datetime fields to ISO format
                    product["created_at"] = product["created_at"].isoformat() if product["created_at"] else None
                    product["updated_at"] = product["updated_at"].isoformat() if product["updated_at"] else None

                result = {
                    "products": products_list,
                    "total_count": total_count,
                    "limit": limit,
                    "offset": offset,
                    "query": query,
                    "filters": filters,
                }

                # Cache the result
                redis_client.set_json(cache_key, result, self.cache_ttl)

                return {**result, "cache_hit": False, "cache_hit_rate": self.get_cache_hit_rate()}

        except Exception as e:
            logger.error(f"Error searching products: {e}")
            raise e

    def search_by_category(self, category_name: str, limit: int = 20) -> list[dict[str, Any]]:
        """Search products by category name."""
        cache_key = f"category_search:{category_name}:{limit}"

        # Check cache
        cached_result = redis_client.get_json(cache_key)
        if cached_result:
            self.cache_hit_count += 1
            return cached_result

        self.cache_miss_count += 1

        try:
            with db.get_cursor() as cursor:
                cursor.execute(
                    """
                    SELECT p.*, c.name as category_name
                    FROM products p
                    JOIN categories c ON p.category = c.name
                    WHERE c.name ILIKE %s
                    ORDER BY p.created_at DESC
                    LIMIT %s
                """,
                    (f"%{category_name}%", limit),
                )

                products = [dict(row) for row in cursor.fetchall()]

                for product in products:
                    # Convert datetime fields to ISO format
                    product["created_at"] = product["created_at"].isoformat() if product["created_at"] else None
                    product["updated_at"] = product["updated_at"].isoformat() if product["updated_at"] else None

                # Cache the result
                redis_client.set_json(cache_key, products, self.cache_ttl)

                return products

        except Exception as e:
            logger.error(f"Error searching by category: {e}")
            raise e

    def get_product_suggestions(self, query: str, limit: int = 5) -> list[str]:
        """Get product name suggestions for autocomplete."""
        cache_key = f"suggestions:{query}:{limit}"

        # Check cache
        cached_result = redis_client.get_json(cache_key)
        if cached_result:
            return cached_result

        try:
            with db.get_cursor() as cursor:
                cursor.execute(
                    """
                    SELECT DISTINCT name
                    FROM products
                    WHERE name ILIKE %s
                    ORDER BY name
                    LIMIT %s
                """,
                    (f"%{query}%", limit),
                )

                suggestions = [row["name"] for row in cursor.fetchall()]

                # Cache for shorter time (5 minutes)
                redis_client.set_json(cache_key, suggestions, 300)

                return suggestions

        except Exception as e:
            logger.error(f"Error getting suggestions: {e}")
            raise e

    def clear_search_cache(self) -> bool:
        """Clear all search-related cache entries."""
        try:
            # Get all search cache keys
            keys = redis_client.client.keys("search:*")
            keys.extend(redis_client.client.keys("category_search:*"))
            keys.extend(redis_client.client.keys("suggestions:*"))

            if keys:
                redis_client.client.delete(*keys)
                logger.info(f"Cleared {len(keys)} search cache entries")

            return True

        except Exception as e:
            logger.error(f"Error clearing search cache: {e}")
            return False


# Singleton instance
product_search_service = ProductSearchService()
