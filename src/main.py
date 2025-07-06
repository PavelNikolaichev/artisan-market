"""FastAPI application for the ArtisanMarket backend."""

import logging
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.services.product_search_service import product_search_service
from src.services.recommendation_service import recommendation_service
from src.services.search_service import semantic_search_service
from src.services.shopping_cart_service import shopping_cart_service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="ArtisanMarket API",
    description="E-commerce backend with advanced search, recommendations, and cart management",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for request/response
class SearchRequest(BaseModel):
    query: str
    category: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    limit: int = 20
    offset: int = 0

class CartItemRequest(BaseModel):
    product_id: str
    quantity: int

class UpdateCartRequest(BaseModel):
    product_id: str
    quantity: int

class ShippingAddress(BaseModel):
    street: str
    city: str
    state: str
    zip_code: str
    country: str = "US"

class OrderRequest(BaseModel):
    user_id: str
    shipping_address: ShippingAddress


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "ArtisanMarket API"}


# Product Search Endpoints
@app.post("/api/search/products")
async def search_products(request: SearchRequest):
    """Search products with filters and caching."""
    try:
        result = product_search_service.search_products(
            query=request.query,
            category=request.category,
            min_price=request.min_price,
            max_price=request.max_price,
            limit=request.limit,
            offset=request.offset
        )
        return result
    except Exception as e:
        logger.error(f"Error searching products: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/search/categories/{category_name}")
async def search_by_category(category_name: str, limit: int = Query(20, ge=1, le=100)):
    """Search products by category."""
    try:
        result = product_search_service.search_by_category(category_name, limit)
        return {"products": result}
    except Exception as e:
        logger.error(f"Error searching by category: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/search/suggestions")
async def get_suggestions(query: str = Query(..., min_length=1), limit: int = Query(5, ge=1, le=10)):
    """Get product name suggestions for autocomplete."""
    try:
        suggestions = product_search_service.get_product_suggestions(query, limit)
        return {"suggestions": suggestions}
    except Exception as e:
        logger.error(f"Error getting suggestions: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/search/cache/stats")
async def get_cache_stats():
    """Get search cache statistics."""
    try:
        hit_rate = product_search_service.get_cache_hit_rate()
        return {
            "cache_hit_rate": hit_rate,
            "cache_hits": product_search_service.cache_hit_count,
            "cache_misses": product_search_service.cache_miss_count
        }
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.delete("/api/search/cache")
async def clear_search_cache():
    """Clear search cache."""
    try:
        success = product_search_service.clear_search_cache()
        return {"success": success, "message": "Search cache cleared"}
    except Exception as e:
        logger.error(f"Error clearing search cache: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Semantic Search Endpoints
@app.post("/api/search/semantic")
async def semantic_search(query: str = Body(..., embed=True), limit: int = Body(10, embed=True)):
    """Semantic search using vector embeddings."""
    try:
        result = semantic_search_service.semantic_search(query, limit)
        return {"products": result}
    except Exception as e:
        logger.error(f"Error in semantic search: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/search/similar/{product_id}")
async def get_similar_products(product_id: str, limit: int = Query(5, ge=1, le=20)):
    """Get products similar to a given product."""
    try:
        result = semantic_search_service.more_like_this(product_id, limit)
        return {"similar_products": result}
    except Exception as e:
        logger.error(f"Error getting similar products: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/api/search/hybrid")
async def hybrid_search(
    query: str = Body(..., embed=True), 
    limit: int = Body(10, embed=True),
    semantic_weight: float = Body(0.7, embed=True)
):
    """Hybrid search combining semantic and text search."""
    try:
        result = semantic_search_service.hybrid_search(query, limit, semantic_weight)
        return {"products": result}
    except Exception as e:
        logger.error(f"Error in hybrid search: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Shopping Cart Endpoints
@app.post("/api/cart/{user_id}/add")
async def add_to_cart(user_id: str, request: CartItemRequest):
    """Add item to shopping cart."""
    try:
        result = shopping_cart_service.add_item(user_id, request.product_id, request.quantity)
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding to cart: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.delete("/api/cart/{user_id}/remove/{product_id}")
async def remove_from_cart(user_id: str, product_id: str):
    """Remove item from shopping cart."""
    try:
        result = shopping_cart_service.remove_item(user_id, product_id)
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing from cart: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.put("/api/cart/{user_id}/update")
async def update_cart_item(user_id: str, request: UpdateCartRequest):
    """Update item quantity in cart."""
    try:
        result = shopping_cart_service.update_item_quantity(user_id, request.product_id, request.quantity)
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating cart: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/cart/{user_id}")
async def get_cart(user_id: str):
    """Get user's cart contents."""
    try:
        result = shopping_cart_service.get_cart(user_id)
        if not result["success"]:
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting cart: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.delete("/api/cart/{user_id}")
async def clear_cart(user_id: str):
    """Clear user's cart."""
    try:
        result = shopping_cart_service.clear_cart(user_id)
        return result
    except Exception as e:
        logger.error(f"Error clearing cart: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/api/cart/{user_id}/checkout")
async def checkout(user_id: str, shipping_address: ShippingAddress):
    """Convert cart to order."""
    try:
        # TODO: migrate to a new model_dump function, however it's working differently, so better to leave as it is now
        result = shopping_cart_service.convert_cart_to_order(user_id, shipping_address.dict())
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during checkout: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Recommendation Endpoints
@app.get("/api/recommendations/similar/{product_id}")
async def get_similar_product_recommendations(product_id: str, limit: int = Query(5, ge=1, le=20)):
    """Get similar product recommendations."""
    try:
        result = recommendation_service.get_similar_products(product_id, limit)
        return {"recommendations": result}
    except Exception as e:
        logger.error(f"Error getting similar recommendations: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/recommendations/also-bought/{product_id}")
async def get_also_bought_recommendations(product_id: str, limit: int = Query(5, ge=1, le=20)):
    """Get 'also bought' recommendations."""
    try:
        result = recommendation_service.get_also_bought_recommendations(product_id, limit)
        return {"recommendations": result}
    except Exception as e:
        logger.error(f"Error getting also bought recommendations: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/recommendations/personalized/{user_id}")
async def get_personalized_recommendations(user_id: str, limit: int = Query(10, ge=1, le=50)):
    """Get personalized recommendations for user."""
    try:
        result = recommendation_service.get_personalized_recommendations(user_id, limit)
        return {"recommendations": result}
    except Exception as e:
        logger.error(f"Error getting personalized recommendations: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/recommendations/comprehensive/{user_id}")
async def get_comprehensive_recommendations(
    user_id: str, 
    product_id: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=50)
):
    """Get comprehensive recommendations combining multiple approaches."""
    try:
        result = recommendation_service.get_comprehensive_recommendations(user_id, product_id, limit)
        return {"recommendations": result}
    except Exception as e:
        logger.error(f"Error getting comprehensive recommendations: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/recommendations/trending")
async def get_trending_products(limit: int = Query(10, ge=1, le=50)):
    """Get trending products."""
    try:
        result = recommendation_service.generate_trending_products(limit)
        return {"trending_products": result}
    except Exception as e:
        logger.error(f"Error getting trending products: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.delete("/api/recommendations/cache")
async def clear_recommendation_cache(
    user_id: Optional[str] = Query(None),
    product_id: Optional[str] = Query(None)
):
    """Clear recommendation cache."""
    try:
        success = recommendation_service.clear_recommendation_cache(user_id, product_id)
        return {"success": success, "message": "Recommendation cache cleared"}
    except Exception as e:
        logger.error(f"Error clearing recommendation cache: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Utility Endpoints
@app.post("/api/embeddings/generate")
async def generate_embeddings(batch_size: int = Body(100, embed=True)):
    """Generate embeddings for products without them."""
    try:
        success = semantic_search_service.generate_embeddings_for_products(batch_size)
        return {"success": success, "message": f"Generated embeddings for up to {batch_size} products"}
    except Exception as e:
        logger.error(f"Error generating embeddings: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
