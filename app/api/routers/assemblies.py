from typing import List

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.Alchemy_models import User
from app.repo import assembly as repo
from app.schemas.assembly import AssemblyCreate, AssemblyPlan, AssemblyPlanRequest, AssemblyRead

router = APIRouter()


@router.post("/plan", response_model=AssemblyPlan)
async def plan(plan_in: AssemblyPlanRequest, db: AsyncSession = Depends(get_db)):
    """
    Preview an assembly: which stock items the pieces are cut from, what is
    left over, and whether there is enough of every product. Nothing is changed.
    """
    return await repo.plan_assembly(
        db,
        materials=[line.model_dump() for line in plan_in.materials],
        products=[line.model_dump() for line in plan_in.products],
    )


@router.post("/", response_model=AssemblyRead, status_code=201)
async def create(
    assembly_in: AssemblyCreate,
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Finish an assembly: make the planned cuts and take the goods out of stock
    in one transaction. A repeated submit with the same `client_key` changes
    nothing and returns the assembly saved the first time (status 200).
    """
    assembly, created = await repo.create_assembly(
        db,
        client_key=assembly_in.client_key,
        cuts=[cut.model_dump() for cut in assembly_in.cuts],
        products=[line.model_dump() for line in assembly_in.products],
        name=assembly_in.name,
        note=assembly_in.note,
        user_id=current_user.id,
    )
    if not created:
        response.status_code = 200
    return AssemblyRead.of(assembly)


@router.get("/", response_model=List[AssemblyRead])
async def list_assemblies(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Finished assemblies, newest first."""
    return [AssemblyRead.of(a) for a in await repo.list_assemblies(db, limit=limit, offset=offset)]


@router.get("/{assembly_id}", response_model=AssemblyRead)
async def get_assembly(assembly_id: int, db: AsyncSession = Depends(get_db)):
    """One assembly with its cuts and the goods taken out for it."""
    return AssemblyRead.of(await repo.get_assembly(db, assembly_id))
