"""Tests for ShoppingCartService."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from src.services.shopping_cart_service import ShoppingCartService


class TestShoppingCartService:
    @pytest.fixture
    def cart_service(self):
        return ShoppingCartService()

    @pytest.fixture
    def mock_db_cursor(self):
        with patch("src.services.shopping_cart_service.db.get_cursor") as mock_cursor:
            cursor = MagicMock()
            mock_cursor.return_value.__enter__.return_value = cursor
            yield cursor

    @pytest.fixture
    def mock_redis(self):
        with patch("src.services.shopping_cart_service.redis_client") as mock_redis:
            yield mock_redis

    @pytest.fixture
    def sample_product_info(self):
        return {
            "id": "P001",
            "name": "Test Product",
            "price": 99.99,
            "stock_quantity": 10,
            "image_url": "http://example.com/image.jpg",
        }

    def test_add_item_to_empty_cart(self, cart_service, mock_db_cursor, mock_redis, sample_product_info):
        """Test adding item to empty cart."""
        mock_redis.get_json.return_value = None
        mock_db_cursor.fetchone.return_value = sample_product_info

        result = cart_service.add_item("U001", "P001", 2)

        assert result["success"] is True
        assert result["message"] == "Item added to cart"
        assert result["cart"]["items"]["P001"]["quantity"] == 2
        assert result["summary"]["total_items"] == 2
        mock_redis.set_json.assert_called_once()

    def test_add_item_to_existing_cart(self, cart_service, mock_db_cursor, mock_redis, sample_product_info):
        """Test adding item to existing cart."""
        existing_cart = {
            "items": {"P001": {"quantity": 1, "price": 99.99, "name": "Test Product"}},
            "created_at": datetime.now().isoformat(),
        }
        mock_redis.get_json.return_value = existing_cart
        mock_db_cursor.fetchone.return_value = sample_product_info

        result = cart_service.add_item("U001", "P001", 1)

        assert result["success"] is True
        assert result["cart"]["items"]["P001"]["quantity"] == 2
        assert result["summary"]["total_items"] == 2

    def test_add_item_insufficient_stock(self, cart_service, mock_db_cursor, mock_redis):
        """Test adding item with insufficient stock."""
        product_info = {
            "id": "P001",
            "name": "Test Product",
            "price": 99.99,
            "stock_quantity": 1,
            "image_url": "http://example.com/image.jpg",
        }
        mock_db_cursor.fetchone.return_value = product_info

        result = cart_service.add_item("U001", "P001", 5)

        assert result["success"] is False
        assert "Insufficient stock" in result["message"]

    def test_add_item_product_not_found(self, cart_service, mock_db_cursor, mock_redis):
        """Test adding non-existent product."""
        mock_db_cursor.fetchone.return_value = None

        result = cart_service.add_item("U001", "P999", 1)

        assert result["success"] is False
        assert result["message"] == "Product not found"

    def test_add_item_negative_quantity(self, cart_service):
        """Test adding item with negative quantity."""
        result = cart_service.add_item("U001", "P001", -1)

        assert result["success"] is False
        assert result["message"] == "Quantity must be positive"

    def test_remove_item_from_cart(self, cart_service, mock_redis):
        """Test removing item from cart."""
        existing_cart = {
            "items": {
                "P001": {"quantity": 2, "price": 99.99, "name": "Test Product"},
                "P002": {"quantity": 1, "price": 49.99, "name": "Another Product"},
            },
            "created_at": datetime.now().isoformat(),
        }
        mock_redis.get_json.return_value = existing_cart

        result = cart_service.remove_item("U001", "P001")

        assert result["success"] is True
        assert "P001" not in result["cart"]["items"]
        assert "P002" in result["cart"]["items"]
        assert result["summary"]["total_items"] == 1

    def test_remove_item_not_in_cart(self, cart_service, mock_redis):
        """Test removing item that's not in cart."""
        existing_cart = {"items": {"P001": {"quantity": 1, "price": 99.99, "name": "Test Product"}}}
        mock_redis.get_json.return_value = existing_cart

        result = cart_service.remove_item("U001", "P999")

        assert result["success"] is False
        assert result["message"] == "Item not found in cart"

    def test_remove_last_item_clears_cart(self, cart_service, mock_redis):
        """Test removing last item clears cart from Redis."""
        existing_cart = {"items": {"P001": {"quantity": 1, "price": 99.99, "name": "Test Product"}}}
        mock_redis.get_json.return_value = existing_cart

        result = cart_service.remove_item("U001", "P001")

        assert result["success"] is True
        assert result["cart"]["items"] == {}
        mock_redis.client.delete.assert_called_once()

    def test_update_item_quantity(self, cart_service, mock_db_cursor, mock_redis, sample_product_info):
        """Test updating item quantity."""
        existing_cart = {"items": {"P001": {"quantity": 1, "price": 99.99, "name": "Test Product"}}}
        mock_redis.get_json.return_value = existing_cart
        mock_db_cursor.fetchone.return_value = sample_product_info

        result = cart_service.update_item_quantity("U001", "P001", 3)

        assert result["success"] is True
        assert result["cart"]["items"]["P001"]["quantity"] == 3
        assert result["summary"]["total_items"] == 3

    def test_update_item_quantity_to_zero_removes_item(self, cart_service, mock_redis):
        """Test updating quantity to zero removes item."""
        existing_cart = {"items": {"P001": {"quantity": 1, "price": 99.99, "name": "Test Product"}}}
        mock_redis.get_json.return_value = existing_cart

        result = cart_service.update_item_quantity("U001", "P001", 0)

        assert result["success"] is True
        assert result["cart"]["items"] == {}

    def test_update_item_quantity_negative(self, cart_service):
        """Test updating quantity to negative value."""
        result = cart_service.update_item_quantity("U001", "P001", -1)

        assert result["success"] is False
        assert result["message"] == "Quantity cannot be negative"

    def test_get_cart(self, cart_service, mock_redis):
        """Test getting cart contents."""
        existing_cart = {"items": {"P001": {"quantity": 2, "price": 99.99, "name": "Test Product"}}}
        mock_redis.get_json.return_value = existing_cart

        result = cart_service.get_cart("U001")

        assert result["success"] is True
        assert result["cart"]["items"]["P001"]["quantity"] == 2
        assert result["summary"]["total_items"] == 2
        assert result["summary"]["total_price"] == 199.98

    def test_get_empty_cart(self, cart_service, mock_redis):
        """Test getting empty cart."""
        mock_redis.get_json.return_value = None

        result = cart_service.get_cart("U001")

        assert result["success"] is True
        assert result["cart"]["items"] == {}
        assert result["summary"]["total_items"] == 0

    def test_clear_cart(self, cart_service, mock_redis):
        """Test clearing cart."""
        result = cart_service.clear_cart("U001")

        assert result["success"] is True
        assert result["cart"]["items"] == {}
        assert result["summary"]["total_items"] == 0
        mock_redis.client.delete.assert_called_once()

    def test_calculate_cart_totals(self, cart_service):
        """Test cart totals calculation."""
        cart = {"items": {"P001": {"quantity": 2, "price": 99.99}, "P002": {"quantity": 1, "price": 49.99}}}

        summary = cart_service._calculate_cart_totals(cart)

        assert summary["total_items"] == 3
        assert summary["total_price"] == 249.97
        assert summary["item_count"] == 2

    def test_convert_cart_to_order(self, cart_service, mock_db_cursor, mock_redis, sample_product_info):
        """Test converting cart to order."""
        existing_cart = {"items": {"P001": {"quantity": 2, "price": 99.99, "name": "Test Product"}}}
        mock_redis.get_json.return_value = existing_cart

        # Mock product info calls - need to handle multiple calls
        product_info_with_stock = {**sample_product_info, "stock_quantity": 10}
        mock_db_cursor.fetchone.side_effect = [
            product_info_with_stock,  # First call for stock validation
            {"id": "O001"},  # Second call for order creation
        ]

        shipping_address = {"street": "123 Main St", "city": "Anytown", "state": "CA", "zip": "12345"}

        result = cart_service.convert_cart_to_order("U001", shipping_address)

        assert result["success"] is True
        assert "order_id" in result
        mock_redis.client.delete.assert_called_once()  # Cart should be cleared

    def test_convert_empty_cart_to_order(self, cart_service, mock_redis):
        """Test converting empty cart to order."""
        mock_redis.get_json.return_value = None

        result = cart_service.convert_cart_to_order("U001", {})

        assert result["success"] is False
        assert result["message"] == "Cart is empty"

    def test_get_cart_expiry(self, cart_service, mock_redis):
        """Test getting cart expiry time."""
        mock_redis.client.ttl.return_value = 3600  # 1 hour

        expiry = cart_service.get_cart_expiry("U001")

        assert expiry is not None
        assert isinstance(expiry, datetime)

    def test_get_cart_expiry_no_cart(self, cart_service, mock_redis):
        """Test getting expiry for non-existent cart."""
        mock_redis.client.ttl.return_value = -1  # No TTL set

        expiry = cart_service.get_cart_expiry("U001")

        assert expiry is None

    def test_extend_cart_expiry(self, cart_service, mock_redis):
        """Test extending cart expiry."""
        existing_cart = {"items": {"P001": {"quantity": 1, "price": 99.99, "name": "Test Product"}}}
        mock_redis.get_json.return_value = existing_cart

        result = cart_service.extend_cart_expiry("U001")

        assert result is True
        mock_redis.set_json.assert_called_once()

    def test_extend_cart_expiry_no_cart(self, cart_service, mock_redis):
        """Test extending expiry for non-existent cart."""
        mock_redis.get_json.return_value = None

        result = cart_service.extend_cart_expiry("U001")

        assert result is False
