"""
Users SQLAlchemy model.
"""

from sqlalchemy import Column, DateTime, String
from sqlalchemy.orm import relationship  # add import
from sqlalchemy.sql.schema import CheckConstraint

from src.db.postgres_bootstrap import Base


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), CheckConstraint("email LIKE '%@%.%'"), unique=True, nullable=False)
    join_date = Column(DateTime, nullable=False, server_default="now()", index=True)
    location = Column(String(255), nullable=True)
    interests = Column(String(512), nullable=True)  # Comma-separated interests

    created_at = Column(DateTime, nullable=False, server_default="now()", index=True)
    updated_at = Column(DateTime, nullable=False, server_default="now()", onupdate="now()", index=True)

    orders = relationship("Order", back_populates="user", cascade="all, delete-orphan")  # new relationship

    def __repr__(self):
        return f"<User(id={self.id}, name={self.name}, email={self.email}, join_date={self.join_date}, location={self.location}, interests={self.interests})>"
