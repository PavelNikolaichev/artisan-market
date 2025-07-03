"""Load graph data into Neo4j."""
from src.db.neo4j_client import neo4j_client
from src.utils.data_parser import DataParser


class GraphLoader:
    def __init__(self):
        self.client = neo4j_client
        self.parser = DataParser()

    def load_constraints(self):
        """Create uniqueness constraints in Neo4j."""
        self.client.create_constraints()
        print("Created Neo4j constraints")

    def load_product_categories(self):
        """Load Product and Category nodes and BELONGS_TO relationships."""
        products = self.parser.parse_products()
        for _, row in products.iterrows():
            self.client.merge_product_with_category(
                id=row["ID"],
                name=row["NAME"],
                category=row["CATEGORY"],
                price=float(row["price"]),
            )
        print(f"Loaded {len(products)} products and categories into Neo4j")

    def load_purchases(self):
        """Load PURCHASED relationships from purchases.csv, deduplicated by user_id, product_id, date."""
        purchases = self.parser.parse_purchases()
        
        for _, row in purchases.iterrows():
            self.client.add_purchase(
                user_id=row["user_id"],
                product_id=row["product_id"],
                quantity=int(row["quantity"]),
                date=row["date"].isoformat(),
            )
        print(f"Loaded {len(purchases)} purchase relationships into Neo4j")

    def load_all(self):
        """Run all graph loading tasks."""
        # flush everything before loading
        self.client.flush_database()
        print("Flushed Neo4j database")

        self.load_constraints()
        self.load_product_categories()
        self.load_purchases()
        print("Graph data loading complete!")


if __name__ == "__main__":
    loader = GraphLoader()
    loader.load_all()
