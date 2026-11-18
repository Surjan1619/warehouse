from fastapi import FastAPI, Depends, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.api.routers import activity, assemblies, auth, imports, maintenance, cuts, locations, materials, orders, products, stock_items, users
from app.core.errors import DomainError
from app.api.deps import get_current_user
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

# Register routers with the application.
# AuthMiddleware only checks the token signature. The get_current_user
# dependency also loads the user, so a deactivated or deleted account is
# rejected immediately instead of when its token expires.
authenticated = [Depends(get_current_user)]

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(users.router, prefix="/users", tags=["users"])  # admin only
app.include_router(activity.router, prefix="/activity", tags=["activity"])  # admin only
app.include_router(maintenance.router, prefix="/maintenance", tags=["maintenance"])  # admin only
app.include_router(products.router, prefix="/products", tags=["products"], dependencies=authenticated)
app.include_router(locations.router, prefix="/locations", tags=["locations"], dependencies=authenticated)
app.include_router(materials.router, prefix="/materials", tags=["materials"], dependencies=authenticated)
app.include_router(orders.router, prefix="/orders", tags=["orders"], dependencies=authenticated)
app.include_router(stock_items.router, prefix="/stock-items", tags=["stock items"], dependencies=authenticated)
app.include_router(cuts.router, prefix="/cuts", tags=["cuts"], dependencies=authenticated)
app.include_router(assemblies.router, prefix="/assemblies", tags=["assemblies"], dependencies=authenticated)
app.include_router(imports.router, prefix="/imports", tags=["imports"], dependencies=authenticated)


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
