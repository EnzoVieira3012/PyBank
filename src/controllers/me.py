from typing import Annotated

from fastapi import APIRouter, Depends

from src.deps import get_current_user
from src.models.user import User
from src.schemas.user import UserOut

router = APIRouter(prefix="/api/v1", tags=["me"])

CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> User:
    return user
