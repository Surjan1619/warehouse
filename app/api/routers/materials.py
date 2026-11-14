from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.repo import stock
from app.schemas.stock import MaterialCreate, MaterialRead, MaterialUpdate

router = APIRouter()


@router.get("/", response_model=List[MaterialRead])
async def get_materials(db: AsyncSession = Depends(get_db)):
    """Fetch the catalogue of cuttable materials."""
    return await stock.get_all_materials(db)


@router.post("/", response_model=MaterialRead, status_code=201)
async def add_material(material_in: MaterialCreate, db: AsyncSession = Depends(get_db)):
    """Create a material."""
    return await stock.create_material(db, material_in.model_dump())


@router.patch("/{material_id}", response_model=MaterialRead)
async def edit_material(material_id: int, material_in: MaterialUpdate, db: AsyncSession = Depends(get_db)):
    """Update the given fields of a material."""
    return await stock.update_material(db, material_id, material_in.model_dump(exclude_unset=True))


@router.delete("/{material_id}")
async def remove_material(material_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a material that no stock item refers to."""
    await stock.delete_material(db, material_id)
    return {"message": "Material deleted"}
