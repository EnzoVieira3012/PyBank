from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID | None
    account_id: UUID | None
    action: str
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    ip: str | None
    correlation_id: str | None
    created_at: datetime
