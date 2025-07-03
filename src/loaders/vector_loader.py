"""Load vector embeddings into pgvector."""

import numpy as np
from sentence_transformers import SentenceTransformer

from src.db.postgres_client import db
from src.utils.data_parser import DataParser


class VectorLoader:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)
        self.parser = DataParser()

    def create_vector_extension(self):
        """Enable pgvector extension and create embeddings table."""
        with db.get_cursor() as cursor:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            cursor.execute("""
create table if not exists product_embeddings
(
    id serial primary key,
    product_id varchar unique not null references products on delete cascade,
    embedding  vector(384) not null,
    created_at timestamp default '2025-07-03 07:43:02.933642'::timestamp without time zone not null,
    updated_at timestamp default '2025-07-03 07:43:02.933642'::timestamp without time zone not null
);

alter table product_embeddings
    owner to postgres;

create index if not exists ix_product_embeddings_product_id
    on product_embeddings (product_id);
            """)

    def generate_embeddings(self):
        """Generate embeddings for all product descriptions."""
        products = self.parser.parse_products()

        for _, product in products.iterrows():
            # Combine relevant text fields
            text = f"{product['NAME']} {product['DESCRIPTION']} {' '.join(product['tags'])}"

            # Generate embedding
            embedding = self.model.encode(text)

            # Store in database
            self._store_embedding(product["ID"], embedding)

    def _store_embedding(self, product_id: str, embedding: np.ndarray):
        """Store embedding in pgvector."""
        with db.get_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO product_embeddings (product_id, embedding)
                VALUES (%s, %s)
                ON CONFLICT (product_id) DO UPDATE
                    SET embedding = EXCLUDED.embedding;
                """,
                (product_id, embedding.tolist()),
            )

if __name__ == "__main__":
    loader = VectorLoader()

    loader.create_vector_extension()
    loader.generate_embeddings()

    print("Vector embeddings loaded successfully.")
