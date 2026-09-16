from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.config import settings

# Create an asynchronous SQLAlchemy engine using the database URL from settings
engine = create_async_engine(settings.DATABASE_URL, echo=True)

# Create an asynchronous session factory
# expire_on_commit=False prevents issues with object attributes expiring after commit
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def get_db():
    """
    Dependency function to provide a database session.
    Automatically closes the session after the request finishes.
    """
    async with async_session() as session:
        yield session
