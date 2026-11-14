from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.core.db import get_db
from app.repo.crud import get_all_locations, create_location
from app.schemas.product import LocationRead, LocationCreate

router = APIRouter()

@router.get("/", response_model=List[LocationRead])
async def get_locations(db: AsyncSession = Depends(get_db)):
    """Fetch all warehouse locations."""
    return await get_all_locations(db)

@router.post("/", response_model=LocationRead)
async def add_location(location_in: LocationCreate, db: AsyncSession = Depends(get_db)):
    """Create a new warehouse location."""
    return await create_location(db, name=location_in.name, capacity=location_in.capacity)
