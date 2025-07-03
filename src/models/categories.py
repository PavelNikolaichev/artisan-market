"""
Categories SQLAlchemy model.
"""

from sqlalchemy import Column, DateTime, String

from src.db.postgres_bootstrap import Base


class Category(Base):
    __tablename__ = "categories"

    id = Column(String, primary_key=True)
    name = Column(String(255), nullable=False, unique=True)  # Category name must be unique
    description = Column(String(255), nullable=False)  # description of the category

    created_at = Column(DateTime, nullable=False, server_default="now()", index=True)
    updated_at = Column(DateTime, nullable=False, server_default="now()", onupdate="now()", index=True)

    def __repr__(self):
        return f"<Category(id={self.id}, name={self.name}, description={self.description})>"
