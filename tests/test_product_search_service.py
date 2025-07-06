"""Tests for ProductSearchService."""

from unittest.mock import MagicMock, patch

import pytest

from src.services.product_search_service import ProductSearchService


class TestProductSearchService:
    @pytest.fixture
    def search_service(self):
        return ProductSearchService()

    @pytest.fixture
    def mock_db_cursor(self):
        with patch("src.services.product_search_service.db.get_cursor") as mock_cursor:
            cursor = MagicMock()
            mock_cursor.return_value.__enter__.return_value = cursor
            yield cursor

    @pytest.fixture
    def mock_redis(self):
        with patch("src.services.product_search_service.redis_client") as mock_redis:
            yield mock_redis

    def test_search_products_cache_hit(self, search_service, mock_redis):
        """Test search with cache hit."""
        # Mock cache hit
        cached_data = {"products": [{"id": "P001", "name": "Test Product"}], "total_count": 1}
        mock_redis.get_json.return_value = cached_data

        result = search_service.search_products("test query")

        assert result["cache_hit"] is True
        assert result["products"] == cached_data["products"]
        mock_redis.get_json.assert_called_once()

    def test_search_products_cache_miss(self, search_service, mock_db_cursor, mock_redis):
        """Test search with cache miss."""
        # Mock cache miss
        mock_redis.get_json.return_value = None

        # Mock database results
        mock_db_cursor.fetchone.return_value = {"total": 1}
        mock_db_cursor.fetchall.return_value = [
            {
                "id": "P001",
                "name": "Test Product",
                "description": "Test description",
                "price": 99.99,
                "category_name": "Test Category",
            }
        ]

        result = search_service.search_products("test query")

        assert result["cache_hit"] is False
        assert len(result["products"]) == 1
        assert result["products"][0]["id"] == "P001"
        mock_redis.set_json.assert_called_once()

    def test_search_products_with_filters(self, search_service, mock_db_cursor, mock_redis):
        """Test search with category and price filters."""
        mock_redis.get_json.return_value = None
        mock_db_cursor.fetchone.return_value = {"total": 1}
        mock_db_cursor.fetchall.return_value = [{"id": "P001", "name": "Test Product", "price": 50.0}]

        result = search_service.search_products("test", category="C001", min_price=10.0, max_price=100.0)

        assert result["cache_hit"] is False
        assert result["filters"]["category_id"] == "C001"
        assert result["filters"]["min_price"] == 10.0
        assert result["filters"]["max_price"] == 100.0

    def test_search_by_category(self, search_service, mock_db_cursor, mock_redis):
        """Test search by category."""
        mock_redis.get_json.return_value = None
        mock_db_cursor.fetchall.return_value = [{"id": "P001", "name": "Test Product", "category_name": "Electronics"}]

        result = search_service.search_by_category("Electronics")

        assert len(result) == 1
        assert result[0]["category_name"] == "Electronics"

    def test_get_product_suggestions(self, search_service, mock_db_cursor, mock_redis):
        """Test product name suggestions."""
        mock_redis.get_json.return_value = None
        mock_db_cursor.fetchall.return_value = [{"name": "Test Product 1"}, {"name": "Test Product 2"}]

        result = search_service.get_product_suggestions("test")

        assert len(result) == 2
        assert "Test Product 1" in result
        assert "Test Product 2" in result

    def test_clear_search_cache(self, search_service, mock_redis):
        """Test clearing search cache."""
        mock_redis.client.keys.return_value = ["search:key1", "search:key2"]
        mock_redis.client.delete.return_value = True

        result = search_service.clear_search_cache()

        assert result is True
        mock_redis.client.delete.assert_called_once()

    def test_cache_hit_rate_calculation(self, search_service):
        """Test cache hit rate calculation."""
        search_service.cache_hit_count = 7
        search_service.cache_miss_count = 3

        hit_rate = search_service.get_cache_hit_rate()

        assert hit_rate == 0.7

    def test_cache_hit_rate_no_requests(self, search_service):
        """Test cache hit rate with no requests."""
        search_service.cache_hit_count = 0
        search_service.cache_miss_count = 0

        hit_rate = search_service.get_cache_hit_rate()

        assert hit_rate == 0.0

    def test_search_products_database_error(self, search_service, mock_db_cursor, mock_redis):
        """Test search with database error."""
        mock_redis.get_json.return_value = None
        mock_db_cursor.execute.side_effect = Exception("Database error")

        with pytest.raises(Exception):
            search_service.search_products("test query")

    def test_generate_cache_key(self, search_service):
        """Test cache key generation."""
        key1 = search_service._generate_cache_key("test", {"limit": 10})
        key2 = search_service._generate_cache_key("test", {"limit": 10})
        key3 = search_service._generate_cache_key("test", {"limit": 20})

        assert key1 == key2  # Same parameters should generate same key
        assert key1 != key3  # Different parameters should generate different keys
