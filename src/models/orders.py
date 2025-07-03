"""
Orders SQLAlchemy model.
"""

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship

from src.db.postgres_bootstrap import Base


class Order(Base):
    """
    Order SQLAlchemy model.
    """

    __tablename__ = "orders"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, server_default="now()", index=True)
    updated_at = Column(DateTime, nullable=False, server_default="now()", onupdate="now()", index=True)

    user = relationship("User", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Order(id={self.id}, user_id={self.user_id})>"
