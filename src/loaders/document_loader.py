"""Load document data into MongoDB."""

import json

from src.config import DATA_DIR
from src.db.mongodb_client import mongo_client
from src.utils.data_parser import DataParser


class DocumentLoader:
    def __init__(self):
        self.client = mongo_client
        self.parser = DataParser()
        self.data_dir = DATA_DIR

    def load_reviews(self):
        """Load review documents into MongoDB."""
        self.client.create_indexes()
        col = self.client.get_collection("reviews")
        col.delete_many({})
        path = self.data_dir / "reviews.json"
        with open(path, encoding="utf-8") as f:
            docs = json.load(f)
        if docs:
            col.insert_many(docs)
        print(f"Loaded {len(docs)} reviews into MongoDB")

    def load_product_specs(self):
        """Load product specifications into MongoDB."""
        col = self.client.get_collection("product_specs")
        col.delete_many({})
        products = self.parser.parse_products()
        docs = []
        for _, row in products.iterrows():
            specs = {
                "price": row["price"],
                "description": row.get("DESCRIPTION"),
                "tags": row["tags"],
                "stock": row.get("STOCK", 0),
            }
            docs.append(
                {
                    "product_id": row["ID"],
                    "category": row["CATEGORY"],
                    "specs": specs,
                }
            )
        if docs:
            col.insert_many(docs)
        print(f"Loaded {len(docs)} product_specs into MongoDB")

    def load_seller_profiles(self):
        """Load seller profiles into MongoDB."""
        col = self.client.get_collection("seller_profiles")
        col.delete_many({})
        sellers = self.parser.parse_sellers()
        products = self.parser.parse_products()
        docs = []
        for _, row in sellers.iterrows():
            portfolio = products[products["SELLER_ID"] == row["ID"]]["ID"].tolist()
            docs.append(
                {
                    "seller_id": row["ID"],
                    "name": row["NAME"],
                    "specialty": row.get("SPECIALTY"),
                    "rating": row.get("rating"),
                    "joined": row.get("joined"),
                    "portfolio": portfolio,
                }
            )
        if docs:
            col.insert_many(docs)
        print(f"Loaded {len(docs)} seller_profiles into MongoDB")

    def load_user_preferences(self):
        """Load user preferences into MongoDB."""
        col = self.client.get_collection("user_preferences")
        col.delete_many({})
        users = self.parser.parse_users()
        docs = []
        for _, row in users.iterrows():
            docs.append(
                {
                    "user_id": row["ID"],
                    "preferences": row["interests"],
                }
            )
        if docs:
            col.insert_many(docs)
        print(f"Loaded {len(docs)} user_preferences into MongoDB")

    def load_all(self):
        """Execute all document loading tasks."""
        self.load_reviews()
        self.load_product_specs()
        self.load_seller_profiles()
        self.load_user_preferences()
        print("Document data loading complete!")


if __name__ == "__main__":
    loader = DocumentLoader()
    loader.load_all()
