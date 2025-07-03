"""
Pydantic models for MongoDB 'user_preferences' collection.
"""

from typing import Any

from pydantic import BaseModel, Field


class UserPreferences(BaseModel):
    id: str | None = Field(None, alias="_id")
    user_id: str
    favorite_categories: list[str] = []
    viewed_products: list[str] = []
    purchase_history: list[str] = []
    settings: dict[str, Any] = {}  # Additional user-specific settings/preferences
