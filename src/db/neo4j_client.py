"""Neo4j connection and utilities."""

from typing import Any

from neo4j import GraphDatabase

from src.config import NEO4J_CONFIG


class Neo4jClient:
    def __init__(self):
        self.driver = GraphDatabase.driver(NEO4J_CONFIG["uri"], auth=(NEO4J_CONFIG["user"], NEO4J_CONFIG["password"]))

    def close(self):
        self.driver.close()

    def flush_database(self):
        """Flush the Neo4j database by dropping all nodes and relationships."""
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
            session.run("CALL db.clearQueryCaches()")


    def create_constraints(self):
        """Create uniqueness constraints."""
        with self.driver.session() as session:
            # User constraint
            session.run("CREATE CONSTRAINT user_id IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE")
            # Product constraint
            session.run("CREATE CONSTRAINT product_id IF NOT EXISTS FOR (p:Product) REQUIRE p.id IS UNIQUE")
            # Category constraint
            session.run("CREATE CONSTRAINT category_name IF NOT EXISTS FOR (c:Category) REQUIRE c.name IS UNIQUE")


    def add_purchase(self, user_id: str, product_id: str, quantity: int, date: str):
        """Add a purchase relationship, merging duplicates and summing quantity."""
        with self.driver.session() as session:
            session.run(
                """
                MATCH (u:User {id: $user_id})
                MATCH (p:Product {id: $product_id})
                CREATE (u)-[:PURCHASED {date: $date, quantity: $quantity}]->(p)
                """,
                user_id=user_id,
                product_id=product_id,
                quantity=quantity,
                date=date,
            )

    def get_recommendations(self, user_id: str, limit: int = 5) -> list[dict[str, Any]]:
        """Get product recommendations for a user."""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (u:User {id: $user_id})-[:PURCHASED]->(p:Product)<-[:PURCHASED]-(other:User)
                MATCH (other)-[:PURCHASED]->(rec:Product)
                WHERE NOT (u)-[:PURCHASED]->(rec)
                RETURN rec.id AS product_id, rec.name AS name, COUNT(*) AS score
                ORDER BY score DESC
                LIMIT $limit
                """,
                user_id=user_id,
                limit=limit,
            )
            return [record.data() for record in result]

    def merge_product_with_category(self, id: str, name: str, category: str, price: float):
        """Merge a Product node, Category node, and BELONGS_TO relationship."""
        with self.driver.session() as session:
            session.run(
                """
                MERGE (p:Product {id: $id})
                SET p.name = $name, p.category = $category, p.price = $price
                MERGE (c:Category {name: $category})
                MERGE (p)-[:BELONGS_TO]->(c)
                """,
                {"id": id, "name": name, "category": category, "price": price},
            )


# Singleton instance
neo4j_client = Neo4jClient()
