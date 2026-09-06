from uuid import UUID

from pydantic import BaseModel

from src.schemas.common import PageMeta
from src.schemas.transaction import TransactionOut


class StatementOut(BaseModel):
    account_id: UUID
    items: list[TransactionOut]
    meta: PageMeta