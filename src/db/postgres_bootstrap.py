"""
This file defines the main instance of the SQLAlchemy database engine and session.
To prevent circular imports when creating all the tables."""

from sqlalchemy.orm.decl_api import declarative_base

Base = declarative_base()
