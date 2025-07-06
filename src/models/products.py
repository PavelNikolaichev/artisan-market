"""
Products SQLAlchemy model.
"""

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql.schema import CheckConstraint

from src.db.postgres_bootstrap import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(String, primary_key=True)
    name = Column(String(255), nullable=False, index=True)
    category = Column(String, nullable=False, index=True)
    price = Column(Float, CheckConstraint("price >= 0.0"), nullable=False, default=0.0)
    seller_id = Column(String, ForeignKey("sellers.id", ondelete="CASCADE"), nullable=False, index=True)
    description = Column(String(512), nullable=True)  # Product description
    tags = Column(String(512), nullable=True)  # Comma-separated tags for the product
    stock = Column(Integer, nullable=False, default=0)  # Stock quantity of the product

    created_at = Column(DateTime, nullable=False, server_default="now()", index=True)
    updated_at = Column(DateTime, nullable=False, server_default="now()", onupdate="now()", index=True)

    seller = relationship("Seller", back_populates="products")
    embeddings = relationship("ProductEmbedding", back_populates="product", cascade="all, delete-orphan")
    items = relationship("OrderItem", back_populates="product")

    def __repr__(self):
        return f"<Product(id={self.id}, name={self.name}, category={self.category}, price={self.price}, seller_id={self.seller_id}, description={self.description}, tags={self.tags})>"
