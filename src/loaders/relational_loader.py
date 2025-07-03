"""Load data into PostgreSQL database."""

from src.db.postgres_client import db
from src.utils.data_parser import DataParser


class RelationalLoader:
    def __init__(self):
        self.db = db
        self.parser = DataParser()

    def load_categories(self):
        """Load categories into PostgreSQL."""
        categories = self.parser.parse_categories()

        with self.db.get_cursor() as cursor:
            for _, row in categories.iterrows():
                # TODO: Implement INSERT query
                query = """
                        INSERT INTO categories (id, name, description)
                        VALUES (%(ID)s, %(NAME)s, %(DESCRIPTION)s) ON CONFLICT (id) DO NOTHING; \
                        """
                cursor.execute(query, row.to_dict())

        print(f"Loaded {len(categories)} categories")

    def load_sellers(self):
        """Load sellers into PostgreSQL."""
        sellers = self.parser.parse_sellers()

        with self.db.get_cursor() as cursor:
            for _, row in sellers.iterrows():
                data = {
                    "id": row["ID"],
                    "name": row["NAME"],
                    "specialty": row["SPECIALTY"],
                    "rating": row["rating"],
                    "joined": row["joined"],
                }
                cursor.execute(
                    """
                    INSERT INTO sellers (id, name, specialty, rating, joined)
                    VALUES (%(id)s, %(name)s, %(specialty)s, %(rating)s, %(joined)s)
                    ON CONFLICT (id) DO NOTHING;
                    """,
                    data,
                )
        print(f"Loaded {len(sellers)} sellers")

    def load_users(self):
        """Load users into PostgreSQL."""
        users = self.parser.parse_users()

        with self.db.get_cursor() as cursor:
            for _, row in users.iterrows():
                data = {
                    "id": row["ID"],
                    "name": row["NAME"],
                    "email": row["EMAIL"],
                    "join_date": row["join_date"],
                    "location": row.get("LOCATION"),
                    "interests": ",".join(row["interests"]) if isinstance(row["interests"], list) else row["INTERESTS"],
                }
                cursor.execute(
                    """
                    INSERT INTO users (id, name, email, join_date, location, interests)
                    VALUES (%(id)s, %(name)s, %(email)s, %(join_date)s, %(location)s, %(interests)s)
                    ON CONFLICT (id) DO NOTHING;
                    """,
                    data,
                )
        print(f"Loaded {len(users)} users")

    def load_products(self):
        """Load products into PostgreSQL."""
        products = self.parser.parse_products()

        # TODO: mb list is not that bad for tags
        with self.db.get_cursor() as cursor:
            for _, row in products.iterrows():
                data = {
                    "id": row["ID"],
                    "name": row["NAME"],
                    "category": row["CATEGORY"],
                    "price": row["price"],
                    "seller_id": row["SELLER_ID"],
                    "description": row.get("DESCRIPTION"),
                    "tags": ",".join(row["tags"]) if isinstance(row["tags"], list) else row["TAGS"],
                    "stock": row.get("STOCK", 0),  # Default to 0 if not present
                }
                cursor.execute(
                    """
                    INSERT INTO products (id, name, category, price, seller_id, description, tags, stock)
                    VALUES (%(id)s, %(name)s, %(category)s, %(price)s, %(seller_id)s, %(description)s, %(tags)s, %(stock)s)
                    ON CONFLICT (id) DO NOTHING;
                    """,
                    data,
                )
        print(f"Loaded {len(products)} products")

    def load_all(self):
        """Load all data into PostgreSQL."""
        print("Creating tables...")
        self.db.create_tables()

        print("Loading categories...")
        self.load_categories()

        print("Loading sellers...")
        self.load_sellers()

        print("Loading users...")
        self.load_users()

        print("Loading products...")
        self.load_products()

        print("Relational data loading complete!")


if __name__ == "__main__":
    loader = RelationalLoader()
    loader.load_all()
