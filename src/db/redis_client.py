"""Redis connection and utilities."""

import json
from typing import Any  # updated import

import redis

from src.config import CACHE_TTL, CART_TTL, RATE_LIMIT_REQUESTS, RATE_LIMIT_WINDOW, REDIS_CONFIG


class RedisClient:
    def __init__(self):
        self.client = redis.Redis(**REDIS_CONFIG)

    def get_json(self, key: str) -> Any | None:
        """Get JSON data from Redis."""
        data = self.client.get(key)
        return json.loads(data.decode("utf-8")) if data else None

    def set_json(self, key: str, value: Any, ttl: int = CACHE_TTL) -> bool:
        """Set JSON data in Redis with TTL."""
        return self.client.setex(key, ttl, json.dumps(value))

    def add_to_cart(self, user_id: str, product_id: str, quantity: int):
        """Add item to user's cart."""
        cart_key = f"cart:{user_id}"
        pipe = self.client.pipeline()
        pipe.hincrby(cart_key, product_id, quantity)
        pipe.expire(cart_key, CART_TTL)
        pipe.execute()
        return True

    def rate_limit_check(self, user_id: str, endpoint: str) -> bool:
        """Check if user has exceeded rate limit. Returns True if allowed, False if rate limit exceeded."""
        key = f"rate_limit:{user_id}:{endpoint}"
        count = self.client.get(key)
        if count is None:
            # first request, set counter with expiry
            self.client.setex(key, RATE_LIMIT_WINDOW, 1)
            return True
        count = int(count)
        if count < RATE_LIMIT_REQUESTS:
            self.client.incr(key)
            return True
        return False


# Singleton instance
redis_client = RedisClient()
