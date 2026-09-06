from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from src.schemas.enums import IdempotencyStatus


class IdempotencyKeyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    key: str
    status: IdempotencyStatus
    expires_at: datetime
