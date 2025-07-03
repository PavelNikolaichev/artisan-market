"""
Pydantic models for MongoDB 'product_specs' collection.
"""

from typing import Any

from pydantic import BaseModel, Field


class ProductSpecs(BaseModel):
    id: str | None = Field(None, alias="_id")
    product_id: str
    category: str
    specs: dict[str, Any]  # Variable specifications per category
