"""Tests for RecommendationService."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from src.services.recommendation_service import RecommendationService


class TestRecommendationService:
    @pytest.fixture
    def recommendation_service(self):
        with (
            patch("src.services.recommendation_service.SentenceTransformer"),
            patch("src.services.recommendation_service.Neo4jClient"),
        ):
            return RecommendationService()

    @pytest.fixture
    def mock_db_cursor(self):
        with patch("src.services.recommendation_service.db.get_cursor") as mock_cursor:
            cursor = MagicMock()
            mock_cursor.return_value.__enter__.return_value = cursor
            yield cursor

    @pytest.fixture
    def mock_redis(self):
        with patch("src.services.recommendation_service.redis_client") as mock_redis:
            yield mock_redis

    @pytest.fixture
    def mock_neo4j_session(self, recommendation_service):
        session = MagicMock()
        recommendation_service.neo4j_client.driver.session.return_value.__enter__.return_value = session
        return session

    def test_get_similar_products_cache_hit(self, recommendation_service, mock_redis):
        """Test getting similar products with cache hit."""
        cached_data = [{"id": "P002", "name": "Similar Product", "similarity_score": 0.9}]
        mock_redis.get_json.return_value = cached_data

        result = recommendation_service.get_similar_products("P001")

        assert len(result) == 1
        assert result[0]["id"] == "P002"
        assert result[0]["similarity_score"] == 0.9
        mock_redis.get_json.assert_called_once()

    def test_get_similar_products_cache_miss(self, recommendation_service, mock_db_cursor, mock_redis):
        """Test getting similar products with cache miss."""
        mock_redis.get_json.return_value = None

        # Mock target product embedding
        mock_db_cursor.fetchone.return_value = {"embedding": [0.1, 0.2, 0.3]}

        # Mock similar products
        mock_db_cursor.fetchall.return_value = [
            {
                "id": "P002",
                "name": "Similar Product",
                "price": 99.99,
                "similarity_score": 0.85,
                "category_name": "Electronics",
            }
        ]

        result = recommendation_service.get_similar_products("P001")

        assert len(result) == 1
        assert result[0]["id"] == "P002"
        assert result[0]["similarity_score"] == 0.85
        mock_redis.set_json.assert_called_once()

    def test_get_similar_products_no_embedding(self, recommendation_service, mock_db_cursor, mock_redis):
        """Test getting similar products when target product has no embedding."""
        mock_redis.get_json.return_value = None
        mock_db_cursor.fetchone.return_value = None

        result = recommendation_service.get_similar_products("P001")

        assert result == []

    def test_get_also_bought_recommendations(self, recommendation_service, mock_neo4j_session, mock_redis):
        """Test getting also bought recommendations."""
        mock_redis.get_json.return_value = None

        # Mock Neo4j query result
        mock_records = [
            Mock(
                get=lambda key, default=None: {
                    "product_id": "P002",
                    "name": "Also Bought Product",
                    "price": 49.99,
                    "purchase_count": 5,
                }.get(key, default)
            )
        ]
        mock_neo4j_session.run.return_value = mock_records

        # Mock product details from PostgreSQL
        with patch.object(recommendation_service, "_get_product_details") as mock_get_details:
            mock_get_details.return_value = {
                "id": "P002",
                "name": "Also Bought Product",
                "price": 49.99,
                "category_name": "Books",
            }

            result = recommendation_service.get_also_bought_recommendations("P001")

            assert len(result) == 1
            assert result[0]["id"] == "P002"
            assert result[0]["purchase_count"] == 5

    def test_get_frequently_bought_together(self, recommendation_service, mock_neo4j_session, mock_redis):
        """Test getting frequently bought together recommendations."""
        mock_redis.get_json.return_value = None

        # Mock Neo4j query result
        mock_records = [
            Mock(
                get=lambda key, default=None: {
                    "product_id": "P003",
                    "name": "Combo Product",
                    "price": 29.99,
                    "frequency": 3,
                }.get(key, default)
            )
        ]
        mock_neo4j_session.run.return_value = mock_records

        # Mock product details
        with patch.object(recommendation_service, "_get_product_details") as mock_get_details:
            mock_get_details.return_value = {
                "id": "P003",
                "name": "Combo Product",
                "price": 29.99,
                "category_name": "Accessories",
            }

            result = recommendation_service.get_frequently_bought_together("P001")

            assert len(result) == 1
            assert result[0]["id"] == "P003"
            assert result[0]["frequency"] == 3

    def test_get_personalized_recommendations(self, recommendation_service, mock_neo4j_session, mock_redis):
        """Test getting personalized recommendations."""
        mock_redis.get_json.return_value = None

        # Mock Neo4j collaborative filtering result
        mock_records = [
            Mock(
                get=lambda key, default=None: {
                    "product_id": "P004",
                    "name": "Personalized Product",
                    "price": 79.99,
                    "recommendation_strength": 4,
                }.get(key, default)
            )
        ]
        mock_neo4j_session.run.return_value = mock_records

        # Mock product details
        with patch.object(recommendation_service, "_get_product_details") as mock_get_details:
            mock_get_details.return_value = {
                "id": "P004",
                "name": "Personalized Product",
                "price": 79.99,
                "category_name": "Fashion",
            }

            result = recommendation_service.get_personalized_recommendations("U001")

            assert len(result) == 1
            assert result[0]["id"] == "P004"
            assert result[0]["recommendation_strength"] == 4

    def test_get_comprehensive_recommendations(self, recommendation_service):
        """Test getting comprehensive recommendations."""
        with (
            patch.object(recommendation_service, "get_personalized_recommendations") as mock_personalized,
            patch.object(recommendation_service, "get_similar_products") as mock_similar,
            patch.object(recommendation_service, "get_also_bought_recommendations") as mock_also_bought,
            patch.object(recommendation_service, "get_frequently_bought_together") as mock_freq_bought,
        ):
            mock_personalized.return_value = [{"id": "P001", "type": "personalized"}]
            mock_similar.return_value = [{"id": "P002", "type": "similar"}]
            mock_also_bought.return_value = [{"id": "P003", "type": "also_bought"}]
            mock_freq_bought.return_value = [{"id": "P004", "type": "freq_bought"}]

            result = recommendation_service.get_comprehensive_recommendations("U001", "P001")

            assert "personalized" in result
            assert "similar_products" in result
            assert "also_bought" in result
            assert "frequently_bought_together" in result
            assert len(result["personalized"]) == 1
            assert len(result["similar_products"]) == 1

    def test_get_product_details(self, recommendation_service, mock_db_cursor):
        """Test getting product details from PostgreSQL."""
        mock_db_cursor.fetchone.return_value = {
            "id": "P001",
            "name": "Test Product",
            "price": 99.99,
            "category_name": "Electronics",
        }

        result = recommendation_service._get_product_details("P001")

        assert result["id"] == "P001"
        assert result["name"] == "Test Product"
        assert result["price"] == 99.99
        assert result["category_name"] == "Electronics"

    def test_get_product_details_not_found(self, recommendation_service, mock_db_cursor):
        """Test getting product details for non-existent product."""
        mock_db_cursor.fetchone.return_value = None

        result = recommendation_service._get_product_details("P999")

        assert result is None

    def test_generate_trending_products(self, recommendation_service, mock_neo4j_session, mock_redis):
        """Test generating trending products."""
        mock_redis.get_json.return_value = None

        # Mock Neo4j trending query result
        mock_records = [
            Mock(
                get=lambda key, default=None: {
                    "product_id": "P005",
                    "name": "Trending Product",
                    "price": 149.99,
                    "recent_purchases": 10,
                }.get(key, default)
            )
        ]
        mock_neo4j_session.run.return_value = mock_records

        # Mock product details
        with patch.object(recommendation_service, "_get_product_details") as mock_get_details:
            mock_get_details.return_value = {
                "id": "P005",
                "name": "Trending Product",
                "price": 149.99,
                "category_name": "Trending",
            }

            result = recommendation_service.generate_trending_products()

            assert len(result) == 1
            assert result[0]["id"] == "P005"
            assert result[0]["recent_purchases"] == 10

    def test_clear_recommendation_cache_all(self, recommendation_service, mock_redis):
        """Test clearing all recommendation cache."""
        mock_redis.client.keys.return_value = ["personalized:U001:10", "similar_products:P001:5", "also_bought:P001:5"]

        result = recommendation_service.clear_recommendation_cache()

        assert result is True
        mock_redis.client.delete.assert_called_once()

    def test_clear_recommendation_cache_specific_user(self, recommendation_service, mock_redis):
        """Test clearing cache for specific user."""
        mock_redis.client.keys.return_value = ["personalized:U001:10"]

        result = recommendation_service.clear_recommendation_cache(user_id="U001")

        assert result is True
        mock_redis.client.delete.assert_called_once()

    def test_clear_recommendation_cache_specific_product(self, recommendation_service, mock_redis):
        """Test clearing cache for specific product."""
        mock_redis.client.keys.return_value = ["similar_products:P001:5", "also_bought:P001:5"]

        result = recommendation_service.clear_recommendation_cache(product_id="P001")

        assert result is True
        mock_redis.client.delete.assert_called_once()

    def test_error_handling_neo4j_failure(self, recommendation_service, mock_neo4j_session, mock_redis):
        """Test error handling when Neo4j query fails."""
        mock_redis.get_json.return_value = None
        mock_neo4j_session.run.side_effect = Exception("Neo4j connection error")

        result = recommendation_service.get_also_bought_recommendations("P001")

        assert result == []

    def test_error_handling_postgres_failure(self, recommendation_service, mock_db_cursor):
        """Test error handling when PostgreSQL query fails."""
        mock_db_cursor.execute.side_effect = Exception("PostgreSQL connection error")

        result = recommendation_service._get_product_details("P001")

        assert result is None
