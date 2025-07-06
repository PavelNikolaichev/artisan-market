"""
Infrastructure Setup Script for ArtisanMarket Backend
This script helps set up the database connections and initial data.
"""

import asyncio
import logging
from src.db.postgres_client import db
from src.db.redis_client import redis_client
from src.db.neo4j_client import Neo4jClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_database_connections():
    """Check if all database connections are working."""
    logger.info("Checking database connections...")
    
    # Check PostgreSQL
    try:
        with db.get_cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            if result:
                logger.info("✅ PostgreSQL connection: OK")
            else:
                logger.error("❌ PostgreSQL connection: Failed")
                return False
    except Exception as e:
        logger.error(f"❌ PostgreSQL connection error: {e}")
        return False
    
    # Check Redis
    try:
        redis_client.client.ping()
        logger.info("✅ Redis connection: OK")
    except Exception as e:
        logger.error(f"❌ Redis connection error: {e}")
        return False
    
    # Check Neo4j
    try:
        neo4j_client = Neo4jClient()
        with neo4j_client.driver.session() as session:
            session.run("RETURN 1")
        logger.info("✅ Neo4j connection: OK")
        neo4j_client.close()
    except Exception as e:
        logger.error(f"❌ Neo4j connection error: {e}")
        return False
    
    return True

async def check_data_availability():
    """Check if sample data is available."""
    logger.info("Checking data availability...")
    
    try:
        with db.get_cursor() as cursor:
            # Check products
            cursor.execute("SELECT COUNT(*) FROM products")
            product_count = cursor.fetchone()["count"]
            logger.info(f"📦 Products in database: {product_count}")
            
            # Check categories
            cursor.execute("SELECT COUNT(*) FROM categories")
            category_count = cursor.fetchone()["count"]
            logger.info(f"📂 Categories in database: {category_count}")
            
            # Check embeddings
            cursor.execute("SELECT COUNT(*) FROM product_embeddings")
            embedding_count = cursor.fetchone()["count"]
            logger.info(f"🔍 Product embeddings: {embedding_count}")
            
            if product_count == 0:
                logger.warning("⚠️ No products found. Run data loaders first.")
                return False
                
    except Exception as e:
        logger.error(f"Error checking data: {e}")
        return False
    
    return True

async def main():
    """Main setup function."""
    logger.info("🚀 Setting up ArtisanMarket Backend...")
    
    # Check database connections
    if not await check_database_connections():
        logger.error("❌ Database connection check failed!")
        return False
    
    # Check data availability
    if not await check_data_availability():
        logger.warning("⚠️ Data availability check failed!")
        logger.info("💡 To load sample data, run:")
        logger.info("   python -m src.loaders.relational_loader")
        logger.info("   python -m src.loaders.vector_loader")
        logger.info("   python -m src.loaders.graph_loader")
        return False
    
    logger.info("✅ Setup complete! Ready to start the server.")
    return True

if __name__ == "__main__":
    asyncio.run(main())
