from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.core.db import get_db
from app.models.Alchemy_models import User
from app.repo import maintenance
from app.schemas.maintenance import ClearRequest, ClearResult

# Clearing data is for admins only, and needs their password on top of the token
router = APIRouter(dependencies=[Depends(require_admin)])


@router.post("/clear", response_model=ClearResult)
async def clear(
    clear_in: ClearRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """
    Delete the chosen groups of data in one transaction. Users are kept.
    A wrong password is 403 (not 401, so the admin is not logged out);
    the catalog without the stock, or nothing chosen, is 422.
    """
    deleted = await maintenance.clear_database(
        db, admin, clear_in.password, stock=clear_in.stock, journal=clear_in.journal, catalog=clear_in.catalog
    )
    return {"deleted": deleted}
