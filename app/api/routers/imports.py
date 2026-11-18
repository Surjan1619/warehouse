"""Receiving goods from a supplier's specification (an Excel file)."""
import json
from typing import List

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import get_db
from app.core.errors import DomainError
from app.models.Alchemy_models import User
from app.repo import document_import as repo
from app.repo.spec_parser import MAX_FILE_BYTES
from app.schemas.document_import import DocumentImportRead, ImportPreview, ImportResult

router = APIRouter()


async def _read(file: UploadFile) -> bytes:
    # Read one byte more than allowed to tell a too large file without reading all of it
    data = await file.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise DomainError("The file is too large", status_code=422)
    return data


def _types(text: str | None) -> dict[int, int]:
    """'{"12": 3}' -> {12: 3}: the type for a product created from Excel row 12."""
    if not text:
        return {}
    try:
        raw = json.loads(text)
        return {int(line): int(type_id) for line, type_id in raw.items() if type_id is not None}
    except (ValueError, TypeError, AttributeError):
        raise DomainError("Bad product types", status_code=422) from None


@router.post("/preview", response_model=ImportPreview)
async def preview(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    """Read the document and tell what it would put into stock. Nothing is changed."""
    return await repo.preview_import(db, await _read(file), file.filename)


@router.post("/", response_model=ImportResult, status_code=201)
async def confirm(
    file: UploadFile = File(...),
    location_id: int | None = Form(None),
    product_types: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Put the document into stock in one transaction. The same file as for the
    preview is sent again; a document already in stock is refused with 409.
    """
    return await repo.confirm_import(
        db, await _read(file), file.filename, current_user.id,
        location_id=location_id, product_type_ids=_types(product_types),
    )


@router.get("/", response_model=List[DocumentImportRead])
async def history(db: AsyncSession = Depends(get_db)):
    """Documents put into stock, the latest first."""
    return await repo.list_imports(db)
