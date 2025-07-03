"""
Pydantic models for MongoDB 'seller_profiles' collection.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class PortfolioItem(BaseModel):
    title: str
    url: str


class SellerProfile(BaseModel):
    id: str | None = Field(None, alias="_id")
    seller_id: str
    name: str
    specialty: str
    rating: float
    joined: datetime
    portfolio: list[PortfolioItem] = []
