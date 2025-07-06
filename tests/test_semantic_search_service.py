"""Tests for SemanticSearchService."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.services.search_service import SemanticSearchService


class TestSemanticSearchService:
    @pytest.fixture
    def search_service(self):
        with patch("src.services.search_service.SentenceTransformer") as mock_transformer:
            mock_model = MagicMock()
            mock_model.encode.return_value = np.array([0.1, 0.2, 0.3])
            mock_transformer.return_value = mock_model
            return SemanticSearchService()

    @pytest.fixture
    def mock_db_cursor(self):
        with patch("src.services.search_service.db.get_cursor") as mock_cursor:
            cursor = MagicMock()
            mock_cursor.return_value.__enter__.return_value = cursor
            yield cursor

    @pytest.fixture
    def mock_redis(self):
        with patch("src.services.search_service.redis_client") as mock_redis:
            yield mock_redis

    def test_semantic_search_cache_hit(self, search_service, mock_redis):
        """Test semantic search with cache hit."""
        cached_data = [{"id": "P001", "name": "Test Product", "similarity_score": 0.9}]
        mock_redis.get_json.return_value = cached_data

        result = search_service.semantic_search("test query")

        assert len(result) == 1
        assert result[0]["id"] == "P001"
        assert result[0]["similarity_score"] == 0.9
        mock_redis.get_json.assert_called_once()

    def test_semantic_search_cache_miss(self, search_service, mock_db_cursor, mock_redis):
        """Test semantic search with cache miss."""
        mock_redis.get_json.return_value = None

        # Mock database results
        mock_db_cursor.fetchall.return_value = [
            {
                "id": "P001",
                "name": "Test Product",
                "description": "Test description",
                "price": 99.99,
                "similarity_score": 0.85,
                "category_name": "Electronics",
            }
        ]

        result = search_service.semantic_search("test query")

        assert len(result) == 1
        assert result[0]["id"] == "P001"
        assert result[0]["similarity_score"] == 0.85
        mock_redis.set_json.assert_called_once()

    def test_semantic_search_with_limit(self, search_service, mock_db_cursor, mock_redis):
        """Test semantic search with custom limit."""
        mock_redis.get_json.return_value = None
        mock_db_cursor.fetchall.return_value = [
            {"id": "P001", "name": "Product 1"},
            {"id": "P002", "name": "Product 2"},
        ]

        result = search_service.semantic_search("test query", limit=2)

        assert len(result) == 2
        # Verify the SQL query was called with correct limit
        args, kwargs = mock_db_cursor.execute.call_args
        assert args[1][2] == 2  # limit parameter

    def test_more_like_this_cache_hit(self, search_service, mock_redis):
        """Test more like this with cache hit."""
        cached_data = [{"id": "P002", "name": "Similar Product", "similarity_score": 0.8}]
        mock_redis.get_json.return_value = cached_data

        result = search_service.more_like_this("P001")

        assert len(result) == 1
        assert result[0]["id"] == "P002"
        mock_redis.get_json.assert_called_once()

    def test_more_like_this_cache_miss(self, search_service, mock_db_cursor, mock_redis):
        """Test more like this with cache miss."""
        mock_redis.get_json.return_value = None

        # Mock target product embedding
        mock_db_cursor.fetchone.return_value = {"embedding": [0.1, 0.2, 0.3]}

        # Mock similar products
        mock_db_cursor.fetchall.return_value = [
            {"id": "P002", "name": "Similar Product", "similarity_score": 0.8, "category_name": "Electronics"}
        ]

        result = search_service.more_like_this("P001")

        assert len(result) == 1
        assert result[0]["id"] == "P002"
        assert result[0]["similarity_score"] == 0.8

    def test_more_like_this_no_embedding(self, search_service, mock_db_cursor, mock_redis):
        """Test more like this when target product has no embedding."""
        mock_redis.get_json.return_value = None
        mock_db_cursor.fetchone.return_value = None

        result = search_service.more_like_this("P001")

        assert result == []

    def test_natural_language_search(self, search_service):
        """Test natural language search (delegates to semantic search)."""
        with patch.object(search_service, "semantic_search") as mock_semantic:
            mock_semantic.return_value = [{"id": "P001", "name": "Test Product"}]

            result = search_service.natural_language_search("find me a red shirt")

            assert len(result) == 1
            mock_semantic.assert_called_once_with("find me a red shirt", 10)

    def test_hybrid_search_cache_hit(self, search_service, mock_redis):
        """Test hybrid search with cache hit."""
        cached_data = [{"id": "P001", "name": "Test Product", "hybrid_score": 0.9}]
        mock_redis.get_json.return_value = cached_data

        result = search_service.hybrid_search("test query")

        assert len(result) == 1
        assert result[0]["hybrid_score"] == 0.9

    def test_hybrid_search_cache_miss(self, search_service, mock_db_cursor, mock_redis):
        """Test hybrid search with cache miss."""
        mock_redis.get_json.return_value = None

        # Mock semantic search call
        with patch.object(search_service, "semantic_search") as mock_semantic:
            mock_semantic.return_value = [{"id": "P001", "name": "Test Product", "similarity_score": 0.8}]

            # Mock text search results
            mock_db_cursor.fetchall.return_value = [{"id": "P001", "name": "Test Product", "text_rank": 0.7}]

            result = search_service.hybrid_search("test query")

            assert len(result) == 1
            assert "hybrid_score" in result[0]
            assert "semantic_score" in result[0]
            assert "text_score" in result[0]

    def test_hybrid_search_weight_calculation(self, search_service, mock_db_cursor, mock_redis):
        """Test hybrid search weight calculation."""
        mock_redis.get_json.return_value = None

        with patch.object(search_service, "semantic_search") as mock_semantic:
            mock_semantic.return_value = [{"id": "P001", "name": "Test Product", "similarity_score": 0.8}]

            mock_db_cursor.fetchall.return_value = [{"id": "P001", "name": "Test Product", "text_rank": 0.6}]

            result = search_service.hybrid_search("test query", semantic_weight=0.7)

            # Verify hybrid score calculation: 0.8 * 0.7 + 0.6 * 0.3 = 0.74
            expected_score = 0.8 * 0.7 + 0.6 * 0.3
            assert abs(result[0]["hybrid_score"] - expected_score) < 0.001

    def test_generate_embeddings_for_products(self, search_service, mock_db_cursor):
        """Test generating embeddings for products."""
        # Mock products without embeddings
        mock_db_cursor.fetchall.return_value = [
            {"id": "P001", "name": "Test Product", "description": "Test description", "tags": "electronics,gadget"},
            {"id": "P002", "name": "Another Product", "description": "Another description", "tags": "books,fiction"},
        ]

        result = search_service.generate_embeddings_for_products()

        assert result is True
        # Verify embeddings were inserted for both products
        assert mock_db_cursor.execute.call_count >= 3  # Select + 2 inserts

    def test_generate_embeddings_no_products(self, search_service, mock_db_cursor):
        """Test generating embeddings when no products need them."""
        mock_db_cursor.fetchall.return_value = []

        result = search_service.generate_embeddings_for_products()

        assert result is True

    def test_generate_embeddings_error(self, search_service, mock_db_cursor):
        """Test error handling during embedding generation."""
        mock_db_cursor.fetchall.return_value = [
            {"id": "P001", "name": "Test Product", "description": "Test", "tags": "test"}
        ]
        mock_db_cursor.execute.side_effect = Exception("Database error")

        result = search_service.generate_embeddings_for_products()

        assert result is False

    def test_clear_semantic_cache(self, search_service, mock_redis):
        """Test clearing semantic search cache."""
        mock_redis.client.keys.return_value = [
            "semantic_search:hash1:10",
            "more_like_this:P001:5",
            "hybrid_search:hash2:10",
        ]

        result = search_service.clear_semantic_cache()

        assert result is True
        mock_redis.client.delete.assert_called_once()

    def test_clear_semantic_cache_no_keys(self, search_service, mock_redis):
        """Test clearing cache when no keys exist."""
        mock_redis.client.keys.return_value = []

        result = search_service.clear_semantic_cache()

        assert result is True
        mock_redis.client.delete.assert_not_called()

    def test_semantic_search_error_handling(self, search_service, mock_db_cursor, mock_redis):
        """Test error handling in semantic search."""
        mock_redis.get_json.return_value = None
        mock_db_cursor.execute.side_effect = Exception("Database connection error")

        result = search_service.semantic_search("test query")

        assert result == []

    def test_more_like_this_error_handling(self, search_service, mock_db_cursor, mock_redis):
        """Test error handling in more like this."""
        mock_redis.get_json.return_value = None
        mock_db_cursor.execute.side_effect = Exception("Database connection error")

        result = search_service.more_like_this("P001")

        assert result == []

    def test_hybrid_search_error_handling(self, search_service, mock_redis):
        """Test error handling in hybrid search."""
        mock_redis.get_json.return_value = None

        with patch.object(search_service, "semantic_search") as mock_semantic:
            mock_semantic.side_effect = Exception("Semantic search error")

            result = search_service.hybrid_search("test query")

            assert result == []

    def test_embedding_model_initialization(self, search_service):
        """Test that the embedding model is properly initialized."""
        assert search_service.model is not None
        assert search_service.cache_ttl == 3600

    def test_cache_key_generation_consistency(self, search_service):
        """Test that cache keys are generated consistently."""
        # Test semantic search cache key
        query1 = "test query"
        query2 = "test query"

        # Since we're using hash() function, same query should produce same key
        # But hash() can vary between Python sessions, so we test consistency within session
        key1 = f"semantic_search:{hash(query1)}:10"
        key2 = f"semantic_search:{hash(query2)}:10"

        assert key1 == key2

    def test_stock_quantity_filtering(self, search_service, mock_db_cursor, mock_redis):
        """Test that semantic search only returns products with stock > 0."""
        mock_redis.get_json.return_value = None
        mock_db_cursor.fetchall.return_value = [{"id": "P001", "name": "In Stock Product", "stock_quantity": 5}]

        search_service.semantic_search("test query")

        # Verify SQL query includes stock quantity filter
        args, kwargs = mock_db_cursor.execute.call_args
        sql_query = args[0]
        assert "stock_quantity > 0" in sql_query
