from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field
from supabase import Client

from app.api.deps import get_current_user, get_supabase
from app.core.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


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


class GoogleIdTokenLoginRequest(BaseModel):
	id_token: str = Field(min_length=20, max_length=8192)
	nonce: str | None = Field(default=None, min_length=1, max_length=255)


class GoogleCodeExchangeRequest(BaseModel):
	auth_code: str = Field(min_length=8, max_length=4096)


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


def _sign_in_with_google_id_token(
	supabase: Client,
	id_token: str,
	nonce: str | None = None,
) -> Any:
	payload: dict[str, Any] = {"provider": "google", "token": id_token}
	if nonce:
		payload["nonce"] = nonce

	try:
		return supabase.auth.sign_in_with_id_token(payload)
	except TypeError:
		return supabase.auth.sign_in_with_id_token(**payload)


def _exchange_google_auth_code(supabase: Client, auth_code: str) -> Any:
	payload: dict[str, Any] = {"auth_code": auth_code}

	try:
		return supabase.auth.exchange_code_for_session(payload)
	except TypeError:
		try:
			return supabase.auth.exchange_code_for_session(auth_code=auth_code)
		except TypeError:
			return supabase.auth.exchange_code_for_session(auth_code)


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
	except Exception as exc:
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail="Signup failed",
		) from exc

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


@router.post("/login/google/id-token", response_model=TokenResponse)
def login_google_with_id_token(
	payload: GoogleIdTokenLoginRequest,
	supabase: Client = Depends(get_supabase),
) -> TokenResponse:
	if not hasattr(supabase.auth, "sign_in_with_id_token"):
		raise HTTPException(
			status_code=status.HTTP_501_NOT_IMPLEMENTED,
			detail="Current Supabase SDK does not support Google ID token sign-in",
		)

	try:
		auth_response = _sign_in_with_google_id_token(
			supabase=supabase,
			id_token=payload.id_token,
			nonce=payload.nonce,
		)
	except Exception as exc:
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="Google ID token login failed",
		) from exc

	if getattr(auth_response, "session", None) is None:
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="Google ID token login failed. Check token validity.",
		)

	return _build_token_response(auth_response)


@router.post("/login/google/code", response_model=TokenResponse)
def login_google_with_auth_code(
	payload: GoogleCodeExchangeRequest,
	supabase: Client = Depends(get_supabase),
) -> TokenResponse:
	if not hasattr(supabase.auth, "exchange_code_for_session"):
		raise HTTPException(
			status_code=status.HTTP_501_NOT_IMPLEMENTED,
			detail="Current Supabase SDK does not support auth code exchange",
		)

	try:
		auth_response = _exchange_google_auth_code(supabase=supabase, auth_code=payload.auth_code)
	except Exception as exc:
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="Google auth code exchange failed",
		) from exc

	if getattr(auth_response, "session", None) is None:
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="Google auth code exchange failed. Check code validity.",
		)

	return _build_token_response(auth_response)


@router.get("/login/google/callback", response_model=TokenResponse)
def login_google_callback(
	code: str = Query(min_length=8, max_length=4096),
	supabase: Client = Depends(get_supabase),
) -> TokenResponse:
	if not hasattr(supabase.auth, "exchange_code_for_session"):
		raise HTTPException(
			status_code=status.HTTP_501_NOT_IMPLEMENTED,
			detail="Current Supabase SDK does not support auth code exchange",
		)

	try:
		auth_response = _exchange_google_auth_code(supabase=supabase, auth_code=code)
	except Exception as exc:
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="Google auth code exchange failed",
		) from exc

	if getattr(auth_response, "session", None) is None:
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="Google auth code exchange failed. Check code validity.",
		)

	return _build_token_response(auth_response)


@router.get("/validate")
def validate_token(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
	return {"valid": True, "user": current_user}
