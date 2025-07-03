"""
Sellers SQLAlchemy model.
"""

from sqlalchemy import Column, DateTime, String
from sqlalchemy.sql.schema import CheckConstraint
from sqlalchemy.sql.sqltypes import Float

from src.db.postgres_bootstrap import Base


class Seller(Base):
    __tablename__ = "sellers"

    id = Column(String, primary_key=True)
    name = Column(String(255), nullable=False)
    specialty = Column(String(255), nullable=False)  # Seller's specialty or product category
    rating = Column(Float, CheckConstraint("rating >= 0.0 AND rating <= 5.0"), nullable=False, default=0.0)
    joined = Column(DateTime, nullable=False, server_default="now()", index=True)

    created_at = Column(DateTime, nullable=False, server_default="now()", index=True)
    updated_at = Column(DateTime, nullable=False, server_default="now()", onupdate="now()", index=True)

    def __repr__(self):
        return f"<Seller(id={self.id}, name={self.name}, specialty={self.specialty}, rating={self.rating}, joined={self.joined})>"
