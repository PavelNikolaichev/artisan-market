#!/usr/bin/env python3
"""
ArtisanMarket Backend Startup Script
This script starts the FastAPI server with all services.
"""

import uvicorn
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("Starting ArtisanMarket Backend...")
    logger.info("Available endpoints:")
    logger.info("  - Health Check: GET /health")
    logger.info("  - Product Search: POST /api/search/products")
    logger.info("  - Semantic Search: POST /api/search/semantic")
    logger.info("  - Shopping Cart: GET/POST/PUT/DELETE /api/cart/{user_id}")
    logger.info("  - Recommendations: GET /api/recommendations/*")
    logger.info("  - API Docs: http://localhost:8000/docs")
    logger.info("  - OpenAPI Schema: http://localhost:8000/openapi.json")

    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
