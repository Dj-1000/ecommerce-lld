from typing import Annotated

from fastapi import APIRouter, Depends

from app.auth.dependencies import get_current_user
from app.users.models import User

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me")
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
):
    return {
        "id": current_user.id,
        "email": current_user.email,
    }