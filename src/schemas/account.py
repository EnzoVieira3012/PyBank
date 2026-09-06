from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AccountCreate(BaseModel):
    user_id: UUID
    initial_balance: Decimal = Field(default=Decimal(0), ge=0, max_digits=18, decimal_places=2)


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    balance: Decimal
    created_at: datetime
