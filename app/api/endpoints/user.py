from typing import Any

from fastapi import APIRouter, Depends
from supabase import Client

from app.api.deps import get_current_user, get_supabase
from app.schemas.user import UserResponse
from app.services import user as user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me")
def read_me(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
	return current_user


@router.get("/{user_id}", response_model=UserResponse)
def read_user(
	user_id: str,
	supabase: Client = Depends(get_supabase),
	current_user: dict[str, Any] = Depends(get_current_user),
) -> UserResponse:
	_ = current_user
	user_data = user_service.get_user_by_id(supabase, user_id)
	return UserResponse.model_validate(user_data)

