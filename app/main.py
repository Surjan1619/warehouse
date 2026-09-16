from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.api.routers import auth, products
from app.core.db import get_db

# Initialize the FastAPI application instance
app = FastAPI(title="Warehouse Management System")

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
