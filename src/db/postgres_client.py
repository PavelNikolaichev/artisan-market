"""PostgreSQL connection and utilities."""

import logging
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import RealDictCursor
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.config import POSTGRES_CONFIG
from src.db.postgres_bootstrap import Base
from src.models import *  # Needed for Base metadata

logger = logging.getLogger(__name__)


class PostgresConnection:
    def __init__(self):
        self.config = POSTGRES_CONFIG
        self._engine = None
        self._session_factory = None

    @property
    def engine(self):
        if not self._engine:
            db_url = (
                f"postgresql://{self.config['user']}:{self.config['password']}@"
                f"{self.config['host']}:{self.config['port']}/{self.config['database']}"
            )
            self._engine = create_engine(db_url)
        return self._engine

    @property
    def session_factory(self):
        if not self._session_factory:
            self._session_factory = sessionmaker(bind=self.engine)
        return self._session_factory

    @contextmanager
    def get_cursor(self):
        """Get a database cursor for raw SQL queries."""
        conn = psycopg2.connect(**self.config)
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                yield cursor
                conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def create_tables(self):
        """Create all tables in the database."""

        # Reset the db
        # logger.log(logging.INFO, "Resetting the database...")
        # with self.get_cursor() as cursor:
        #     cursor.execute("DROP SCHEMA public CASCADE;")
        #     cursor.execute("CREATE SCHEMA public;")
        #     logger.log(logging.INFO, "Database reset successfully.")

        # Base metadata is used to create tables defined in SQLAlchemy models
        # In theory, should generate all the tables defined in the models
        logger.log(logging.INFO, "Creating tables...")

        try:
            Base.metadata.create_all(self.engine)
            logger.log(logging.INFO, "Tables created successfully.")
        except Exception as e:
            logger.log(logging.ERROR, f"Error creating tables: {e}")
            raise e


# Singleton instance
db = PostgresConnection()
