"""
ProductEmbeddings SQLAlchemy model.
"""

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from src.db.postgres_bootstrap import Base


class ProductEmbedding(Base):
    __tablename__ = "product_embeddings"

    id = Column(Integer, primary_key=True, autoincrement=True)  # Integer for easy indexing and incrementing
    product_id = Column(String, ForeignKey("products.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    embedding = Column(Vector(384), nullable=False)

    created_at = Column(DateTime, nullable=False, server_default="now()")
    updated_at = Column(DateTime, nullable=False, server_default="now()", onupdate="now()")

    product = relationship("Product", back_populates="embeddings")

    def __repr__(self):
        return f"<ProductEmbeddings(id={self.id}, product_id={self.product_id})>"
