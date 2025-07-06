"""Shopping cart management service with Redis session storage."""

import json
import logging
from datetime import datetime, timedelta, date
from typing import Any

from src.db.postgres_client import db
from src.db.redis_client import redis_client

logger = logging.getLogger(__name__)


class ShoppingCartService:
    def __init__(self):
        self.cart_ttl = 86400  # 24 hours TTL for cart sessions
        self.cart_key_prefix = "cart:"

    def _get_cart_key(self, user_id: str) -> str:
        """Generate cart key for user."""
        return f"{self.cart_key_prefix}{user_id}"

    def _get_product_info(self, product_id: str) -> dict[str, Any] | None:
        """Get product information from database."""
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
            logger.error(f"Error fetching product info: {e}")
            return None

    def add_item(self, user_id: str, product_id: str, quantity: int = 1) -> dict[str, Any]:
        """
        Add item to user's cart.

        Args:
            user_id: User ID
            product_id: Product ID to add
            quantity: Quantity to add

        Returns:
            Dict with operation result and cart info
        """
        if quantity <= 0:
            return {"success": False, "message": "Quantity must be positive"}

        # Get product info to validate and get price
        product_info = self._get_product_info(product_id)
        if not product_info:
            return {"success": False, "message": "Product not found"}

        # Check stock availability
        if product_info["stock"] < quantity:
            return {"success": False, "message": f"Insufficient stock. Available: {product_info['stock']}"}

        cart_key = self._get_cart_key(user_id)

        try:
            # Get current cart
            current_cart = redis_client.get_json(cart_key) or {"items": {}, "created_at": datetime.now().isoformat()}

            # Add or update item
            if product_id in current_cart["items"]:
                # noinspection PyTypeChecker
                new_quantity = current_cart["items"][product_id]["quantity"] + quantity
                # Check total quantity against stock
                if new_quantity > product_info["stock"]:
                    return {
                        "success": False,
                        "message": f"Cannot add {quantity} items. Total would exceed stock ({product_info['stock']})",
                    }
                current_cart["items"][product_id]["quantity"] = new_quantity
            else:
                current_cart["items"][product_id] = {
                    "quantity": quantity,
                    "price": float(product_info["price"]),
                    "name": product_info["name"],
                }

            current_cart["updated_at"] = datetime.now().isoformat()

            # Save to Redis with TTL
            redis_client.set_json(cart_key, current_cart, self.cart_ttl)

            # Calculate totals
            cart_summary = self._calculate_cart_totals(current_cart)

            return {"success": True, "message": "Item added to cart", "cart": current_cart, "summary": cart_summary}

        except Exception as e:
            logger.error(f"Error adding item to cart: {e}")
            return {"success": False, "message": "Failed to add item to cart"}

    def remove_item(self, user_id: str, product_id: str) -> dict[str, Any]:
        """
        Remove item completely from cart.

        Args:
            user_id: User ID
            product_id: Product ID to remove

        Returns:
            Dict with operation result
        """
        cart_key = self._get_cart_key(user_id)

        try:
            current_cart = redis_client.get_json(cart_key)
            if not current_cart or product_id not in current_cart.get("items", {}):
                return {"success": False, "message": "Item not found in cart"}

            # Remove item
            del current_cart["items"][product_id]
            current_cart["updated_at"] = datetime.now().isoformat()

            # Save updated cart
            if current_cart["items"]:
                redis_client.set_json(cart_key, current_cart, self.cart_ttl)
            else:
                # Clear cart if empty
                redis_client.client.delete(cart_key)
                current_cart = {"items": {}}

            cart_summary = self._calculate_cart_totals(current_cart)

            return {"success": True, "message": "Item removed from cart", "cart": current_cart, "summary": cart_summary}

        except Exception as e:
            logger.error(f"Error removing item from cart: {e}")
            return {"success": False, "message": "Failed to remove item from cart"}

    def update_item_quantity(self, user_id: str, product_id: str, quantity: int) -> dict[str, Any]:
        """
        Update quantity of item in cart.

        Args:
            user_id: User ID
            product_id: Product ID to update
            quantity: New quantity (0 to remove item)

        Returns:
            Dict with operation result
        """
        if quantity < 0:
            return {"success": False, "message": "Quantity cannot be negative"}

        if quantity == 0:
            return self.remove_item(user_id, product_id)

        # Get product info to check stock
        product_info = self._get_product_info(product_id)
        if not product_info:
            return {"success": False, "message": "Product not found"}

        if quantity > product_info["stock"]:
            return {"success": False, "message": f"Insufficient stock. Available: {product_info['stock']}"}

        cart_key = self._get_cart_key(user_id)

        try:
            current_cart = redis_client.get_json(cart_key)
            if not current_cart or product_id not in current_cart.get("items", {}):
                return {"success": False, "message": "Item not found in cart"}

            # Update quantity
            current_cart["items"][product_id]["quantity"] = quantity
            current_cart["updated_at"] = datetime.now().isoformat()

            # Save updated cart
            redis_client.set_json(cart_key, current_cart, self.cart_ttl)

            cart_summary = self._calculate_cart_totals(current_cart)

            return {"success": True, "message": "Item quantity updated", "cart": current_cart, "summary": cart_summary}

        except Exception as e:
            logger.error(f"Error updating item quantity: {e}")
            return {"success": False, "message": "Failed to update item quantity"}

    def get_cart(self, user_id: str) -> dict[str, Any]:
        """
        Get user's cart contents.

        Args:
            user_id: User ID

        Returns:
            Dict with cart contents and summary
        """
        cart_key = self._get_cart_key(user_id)

        try:
            current_cart = redis_client.get_json(cart_key) or {"items": {}}
            cart_summary = self._calculate_cart_totals(current_cart)

            return {"success": True, "cart": current_cart, "summary": cart_summary}

        except Exception as e:
            logger.error(f"Error getting cart: {e}")
            return {"success": False, "message": "Failed to retrieve cart"}

    def clear_cart(self, user_id: str) -> dict[str, Any]:
        """
        Clear user's cart.

        Args:
            user_id: User ID

        Returns:
            Dict with operation result
        """
        cart_key = self._get_cart_key(user_id)

        try:
            redis_client.client.delete(cart_key)

            return {
                "success": True,
                "message": "Cart cleared",
                "cart": {"items": {}},
                "summary": {"total_items": 0, "total_price": 0.0},
            }

        except Exception as e:
            logger.error(f"Error clearing cart: {e}")
            return {"success": False, "message": "Failed to clear cart"}

    def _calculate_cart_totals(self, cart: dict[str, Any]) -> dict[str, Any]:
        """Calculate cart totals."""
        items = cart.get("items", {})
        total_items = sum(item["quantity"] for item in items.values())
        total_price = sum(item["quantity"] * item["price"] for item in items.values())

        return {"total_items": total_items, "total_price": round(total_price, 2), "item_count": len(items)}

    def convert_cart_to_order(self, user_id: str, shipping_address: dict[str, str]) -> dict[str, Any]:
        """
        Convert cart to order and clear cart.

        Args:
            user_id: User ID
            shipping_address: Shipping address details

        Returns:
            Dict with operation result and order ID
        """
        cart_key = self._get_cart_key(user_id)

        try:
            # Get current cart
            current_cart = redis_client.get_json(cart_key)
            if not current_cart or not current_cart.get("items"):
                return {"success": False, "message": "Cart is empty"}

            # Validate stock for all items
            for product_id, item in current_cart["items"].items():
                product_info = self._get_product_info(product_id)
                if not product_info:
                    return {"success": False, "message": f"Product {product_id} not found"}

                if item["quantity"] > product_info["stock"]:
                    return {
                        "success": False,
                        "message": f"Insufficient stock for {product_info['name']}. Available: {product_info['stock']}",
                    }

            # Create order in database
            cart_summary = self._calculate_cart_totals(current_cart)

            with db.get_cursor() as cursor:
                # Generate new order ID
                order_id = f"order_{user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                # Insert order
                cursor.execute(
                    """
                    INSERT INTO orders (id, user_id)
                    VALUES (%s, %s)
                """,
                    (order_id, user_id),
                )

                # Insert order items and update stock
                for product_id, item in current_cart["items"].items():
                    order_item_id = f"order_item_{order_id}_{product_id}"
                    cursor.execute(
                        """
                        INSERT INTO order_items (id, order_id, product_id, quantity)
                        VALUES (%s, %s, %s, %s)
                    """,
                        (order_item_id, order_id, product_id, item["quantity"]),
                    )

                    # Update product stock
                    cursor.execute(
                        """
                        UPDATE products 
                        SET stock = stock - %s
                        WHERE id = %s
                    """,
                        (item["quantity"], product_id),
                    )

            # Clear cart
            redis_client.client.delete(cart_key)

            return {
                "success": True,
                "message": "Order created successfully",
                "order_id": order_id,
                "order_summary": cart_summary,
            }

        except Exception as e:
            logger.error(f"Error converting cart to order: {e}")
            return {"success": False, "message": "Failed to create order"}

    def get_cart_expiry(self, user_id: str) -> datetime | None:
        """Get cart expiry time."""
        cart_key = self._get_cart_key(user_id)

        try:
            ttl = redis_client.client.ttl(cart_key)
            if ttl > 0:
                return datetime.now() + timedelta(seconds=ttl)
            return None

        except Exception as e:
            logger.error(f"Error getting cart expiry: {e}")
            return None

    def extend_cart_expiry(self, user_id: str) -> bool:
        """Extend cart expiry by resetting TTL."""
        cart_key = self._get_cart_key(user_id)

        try:
            current_cart = redis_client.get_json(cart_key)
            if current_cart:
                redis_client.set_json(cart_key, current_cart, self.cart_ttl)
                return True
            return False

        except Exception as e:
            logger.error(f"Error extending cart expiry: {e}")
            return False


# Singleton instance
shopping_cart_service = ShoppingCartService()
