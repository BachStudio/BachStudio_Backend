from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from supabase import Client

from app.api.deps import get_current_user, get_supabase
from app.core.config import settings

router = APIRouter(prefix="", tags=["auth"])


class SignupRequest(BaseModel):
	email: EmailStr
	password: str = Field(min_length=8, max_length=128)
	name: str | None = Field(default=None, min_length=1, max_length=100)


class LoginRequest(BaseModel):
	email: EmailStr
	password: str = Field(min_length=8, max_length=128)


class AuthUserResponse(BaseModel):
	id: str
	email: str


class TokenResponse(BaseModel):
	access_token: str | None = None
	refresh_token: str | None = None
	expires_in: int | None = None
	token_type: str = "bearer"
	user: AuthUserResponse
	message: str | None = None


class GoogleOAuthUrlResponse(BaseModel):
	url: str


def _serialize_user(raw_user: Any) -> AuthUserResponse:
	if raw_user is None:
		raise HTTPException(
			status_code=status.HTTP_502_BAD_GATEWAY,
			detail="Auth provider did not return user information",
		)

	if isinstance(raw_user, dict):
		user_data = raw_user
	elif hasattr(raw_user, "model_dump"):
		user_data = raw_user.model_dump()
	else:
		user_data = {
			"id": getattr(raw_user, "id", None),
			"email": getattr(raw_user, "email", None),
		}

	user_id = user_data.get("id")
	email = user_data.get("email")
	if not user_id or not email:
		raise HTTPException(
			status_code=status.HTTP_502_BAD_GATEWAY,
			detail="Auth provider returned incomplete user information",
		)

	return AuthUserResponse(id=str(user_id), email=str(email))


def _build_token_response(auth_response: Any, message: str | None = None) -> TokenResponse:
	session = getattr(auth_response, "session", None)

	return TokenResponse(
		access_token=getattr(session, "access_token", None) if session else None,
		refresh_token=getattr(session, "refresh_token", None) if session else None,
		expires_in=getattr(session, "expires_in", None) if session else None,
		user=_serialize_user(getattr(auth_response, "user", None)),
		message=message,
	)


def _extract_oauth_url(oauth_response: Any) -> str | None:
	if oauth_response is None:
		return None

	if isinstance(oauth_response, str):
		return oauth_response

	response_url = getattr(oauth_response, "url", None)
	if isinstance(response_url, str) and response_url:
		return response_url

	if isinstance(oauth_response, dict):
		payload = oauth_response
	elif hasattr(oauth_response, "model_dump"):
		payload = oauth_response.model_dump()
	else:
		payload = {}

	if isinstance(payload, dict):
		for key in ("url", "provider_url"):
			value = payload.get(key)
			if isinstance(value, str) and value:
				return value

		data = payload.get("data")
		if isinstance(data, dict):
			for key in ("url", "provider_url"):
				value = data.get(key)
				if isinstance(value, str) and value:
					return value

	return None


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, supabase: Client = Depends(get_supabase)) -> TokenResponse:
	signup_payload: dict[str, Any] = {
		"email": str(payload.email),
		"password": payload.password,
	}
	if payload.name:
		signup_payload["options"] = {"data": {"name": payload.name}}

	try:
		auth_response = supabase.auth.sign_up(signup_payload)
		# 예시 (auth.py 내부의 회원가입 예외 처리 부분)
	except Exception as exc:
		print("🔴 회원가입 실제 에러 발생:", str(exc))  # 터미널에서 확인하기 위함
		raise HTTPException(
        	status_code=status.HTTP_400_BAD_REQUEST,
        	detail=f"Signup failed: {str(exc)}"  # 클라이언트 응답에도 상세 에러 포함
    	)

	message = None
	if getattr(auth_response, "session", None) is None:
		message = "Signup succeeded. Verify your email before logging in."

	return _build_token_response(auth_response, message=message)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, supabase: Client = Depends(get_supabase)) -> TokenResponse:
	try:
		auth_response = supabase.auth.sign_in_with_password(
			{"email": str(payload.email), "password": payload.password}
		)
	except Exception as exc:
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="Invalid email or password",
		) from exc

	if getattr(auth_response, "session", None) is None:
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="Login failed. Check credentials or email verification status.",
		)

	return _build_token_response(auth_response)


@router.get("/login/google", response_model=GoogleOAuthUrlResponse)
def login_google(supabase: Client = Depends(get_supabase)) -> GoogleOAuthUrlResponse:
	oauth_payload: dict[str, Any] = {"provider": "google"}
	if settings.GOOGLE_OAUTH_REDIRECT_URL:
		oauth_payload["options"] = {"redirect_to": settings.GOOGLE_OAUTH_REDIRECT_URL}

	try:
		try:
			oauth_response = supabase.auth.sign_in_with_oauth(oauth_payload)
		except TypeError:
			oauth_kwargs: dict[str, Any] = {"provider": "google"}
			if oauth_payload.get("options"):
				oauth_kwargs["options"] = oauth_payload["options"]
			oauth_response = supabase.auth.sign_in_with_oauth(**oauth_kwargs)
	except Exception as exc:
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail="Google OAuth login initialization failed",
		) from exc

	oauth_url = _extract_oauth_url(oauth_response)
	if not oauth_url:
		raise HTTPException(
			status_code=status.HTTP_502_BAD_GATEWAY,
			detail="Google OAuth URL was not returned by auth provider",
		)

	return GoogleOAuthUrlResponse(url=oauth_url)


@router.get("/validate")
def validate_token(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
	return {"valid": True, "user": current_user}
