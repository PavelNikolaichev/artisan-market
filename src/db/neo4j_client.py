"""Neo4j connection and utilities."""

from typing import Any

from neo4j import GraphDatabase

from src.config import NEO4J_CONFIG


class Neo4jClient:
    def __init__(self):
        self.driver = GraphDatabase.driver(NEO4J_CONFIG["uri"], auth=(NEO4J_CONFIG["user"], NEO4J_CONFIG["password"]))

    def close(self):
        self.driver.close()

    def create_constraints(self):
        """Create uniqueness constraints."""
        with self.driver.session() as session:
            # User constraint
            session.run("CREATE CONSTRAINT user_id IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE")
            # Product constraint
            session.run("CREATE CONSTRAINT product_id IF NOT EXISTS FOR (p:Product) REQUIRE p.id IS UNIQUE")
            # TODO: Add more constraints

    def add_purchase(self, user_id: str, product_id: str, quantity: int, date: str):
        """Add a purchase relationship."""
        with self.driver.session() as session:
            session.run(
                """
                MERGE (u:User {id: $user_id})
                MERGE (p:Product {id: $product_id})
                CREATE (u)-[:PURCHASED {quantity: $quantity, date: $date}]->(p)
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


# Singleton instance
neo4j_client = Neo4jClient()
