from typing import Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, EmailStr, Field
from supabase import Client

from app.api.deps import get_current_user, get_supabase
from app.core.security import create_access_token
from app.schemas.user import UserCreate, UserResponse
from app.services import google_auth
from app.services import user as user_service

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
	email: EmailStr
	password: str = Field(min_length=8, max_length=128)


class TokenResponse(BaseModel):
	access_token: str
	token_type: str = "bearer"
	user: dict[str, Any] | None = None


class GoogleAuthUrlResponse(BaseModel):
	authorization_url: str
	state: str


class GoogleCallbackRequest(BaseModel):
	code: str = Field(min_length=1)
	state: str | None = None
	redirectUri: str | None = None


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


@router.get("/google/login", response_model=GoogleAuthUrlResponse)
def google_login(state: str | None = None) -> GoogleAuthUrlResponse:
	return GoogleAuthUrlResponse.model_validate(google_auth.build_google_authorization_url(state))


@router.get("/google/url", response_model=GoogleAuthUrlResponse)
def google_url(state: str | None = None) -> GoogleAuthUrlResponse:
	return google_login(state)


@router.post("/google/callback", response_model=TokenResponse)
def google_callback(
	payload: GoogleCallbackRequest,
	supabase: Client = Depends(get_supabase),
) -> TokenResponse:
	userinfo = google_auth.exchange_google_code(payload.code, payload.redirectUri)
	user = google_auth.upsert_google_user(supabase, userinfo)
	subject = str(user.get("id") or userinfo.get("sub") or userinfo["email"])
	token = create_access_token(
		subject=subject,
		extra_claims={
			"email": str(userinfo["email"]),
			"name": str(userinfo.get("name") or user.get("name") or ""),
			"provider": "google",
			"google_sub": str(userinfo.get("sub") or ""),
		},
	)
	return TokenResponse(
		access_token=token,
		user={
			"id": subject,
			"email": str(userinfo["email"]),
			"name": str(userinfo.get("name") or user.get("name") or ""),
			"picture": userinfo.get("picture"),
			"provider": "google",
		},
	)


@router.get("/validate")
def validate_token(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
	return {"valid": True, "user": current_user}
