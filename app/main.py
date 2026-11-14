from fastapi import FastAPI, Depends, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.api.routers import auth, cuts, locations, materials, orders, products, stock_items
from app.core.errors import DomainError
from app.core.db import get_db
from app.middleware.auth import AuthMiddleware

# Initialize the FastAPI application instance
app = FastAPI(title="Warehouse Management System")

# Register custom Auth Middleware.
# It must be added before CORS: the middleware added last runs first, and CORS
# has to wrap auth so that 401 responses still carry CORS headers.
app.add_middleware(AuthMiddleware)

# Configure CORS to allow communication with the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers with the application
# Prefix "/auth" handles all authentication-related endpoints
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(products.router, prefix="/products", tags=["products"])
app.include_router(locations.router, prefix="/locations", tags=["locations"])
app.include_router(materials.router, prefix="/materials", tags=["materials"])
app.include_router(orders.router, prefix="/orders", tags=["orders"])
app.include_router(stock_items.router, prefix="/stock-items", tags=["stock items"])
app.include_router(cuts.router, prefix="/cuts", tags=["cuts"])


@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError):
    """Turn business-rule violations from app/repo/ into HTTP error responses."""
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.get("/")
async def root():
    """Root endpoint for basic API status verification."""
    return {"message": "Welcome to WMS API"}

@app.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Health check endpoint to verify database connectivity.
    Executes a simple SELECT query to ensure the database pool is healthy.
    """
    await db.execute(text("SELECT 1"))
    return {"status": "ok"}
