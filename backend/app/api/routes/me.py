from fastapi import APIRouter

from app.auth import CurrentUser
from app.schemas import UserRead

router = APIRouter(prefix="/me", tags=["me"])


@router.get("", response_model=UserRead, summary="Current user")
async def get_me(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user)
