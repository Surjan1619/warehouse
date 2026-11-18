from pydantic import BaseModel, Field


class ClearRequest(BaseModel):
    # The administrator's own password: a stolen token alone cannot wipe the data
    password: str = Field(..., min_length=1, max_length=200)
    # Stock items, cuts, assemblies, orders, piece goods and their movements
    stock: bool = False
    # The activity journal
    journal: bool = False
    # Materials, storage locations and product types; only together with the stock
    catalog: bool = False


class ClearResult(BaseModel):
    # Number of deleted rows per table
    deleted: dict[str, int]
