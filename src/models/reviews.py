"""
Pydantic models for MongoDB 'reviews' collection.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class Comment(BaseModel):
    user_id: str
    content: str
    created_at: datetime


class Review(BaseModel):
    id: str | None = Field(None, alias="_id")
    product_id: str
    user_id: str
    rating: int
    title: str
    content: str
    images: list[str] = []
    helpful_votes: int = 0
    verified_purchase: bool = False
    created_at: datetime
    comments: list[Comment] = []
