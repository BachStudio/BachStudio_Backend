from typing import Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, EmailStr, Field
from supabase import Client

from app.api.deps import get_current_user, get_supabase
from app.core.security import create_access_token
from app.schemas.user import UserCreate, UserResponse
from app.services import user as user_service

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
	email: EmailStr
	password: str = Field(min_length=8, max_length=128)


class TokenResponse(BaseModel):
	access_token: str
	token_type: str = "bearer"


@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: UserCreate, supabase: Client = Depends(get_supabase)) -> UserResponse:
	created_user = user_service.create_user(supabase, payload)
	return UserResponse.model_validate(created_user)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest) -> TokenResponse:
	token = create_access_token(
		subject=str(payload.email),
		extra_claims={"email": str(payload.email)},
	)
	return TokenResponse(access_token=token)


@router.get("/validate")
def validate_token(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
	return {"valid": True, "user": current_user}

