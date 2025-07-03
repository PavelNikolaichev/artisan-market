"""MongoDB connection and utilities."""

from pymongo import MongoClient
from pymongo.database import Database

from src.config import MONGO_CONFIG


class MongoDBClient:
    def __init__(self):
        self.client = MongoClient(MONGO_CONFIG["uri"])
        self.db: Database = self.client[MONGO_CONFIG["database"]]

    def get_collection(self, name: str):
        """Get a MongoDB collection."""
        return self.db[name]

    def create_indexes(self):
        """Create necessary indexes."""
        # Reviews indexes
        self.db.get_collection("reviews").create_index("product_id")
        self.db.get_collection("reviews").create_index("user_id")
        # Product specs indexes
        self.db.get_collection("product_specs").create_index("product_id", unique=True)
        self.db.get_collection("product_specs").create_index("category")
        # Seller profiles indexes
        self.db.get_collection("seller_profiles").create_index("seller_id", unique=True)
        # User preferences indexes
        self.db.get_collection("user_preferences").create_index("user_id", unique=True)


# Singleton instance
mongo_client = MongoDBClient()
