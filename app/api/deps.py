from typing import Any

from fastapi import Depends, Header, HTTPException, status
from supabase import Client

from app.core.security import extract_bearer_token
from app.core.supabase import get_supabase_client


def get_supabase() -> Client:
	return get_supabase_client()


def _to_dict(value: Any) -> dict[str, Any]:
	if value is None:
		return {}

	if isinstance(value, dict):
		return value

	if hasattr(value, "model_dump"):
		return value.model_dump()

	if hasattr(value, "dict"):
		return value.dict()

	return {
		"id": getattr(value, "id", None),
		"email": getattr(value, "email", None),
		"app_metadata": getattr(value, "app_metadata", None),
		"user_metadata": getattr(value, "user_metadata", None),
	}


def get_current_user(
	authorization: str | None = Header(default=None),
	supabase: Client = Depends(get_supabase),
) -> dict[str, Any]:
	token = extract_bearer_token(authorization)
	if not token:
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="Authorization header is missing or invalid",
		)

	try:
		try:
			response = supabase.auth.get_user(token)
		except TypeError:
			response = supabase.auth.get_user(jwt=token)
	except Exception as exc:
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="Invalid or expired token",
		) from exc

	user = _to_dict(getattr(response, "user", None))
	user_id = user.get("id")
	if not user_id:
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="Invalid or expired token",
		)

	return {
		"sub": str(user_id),
		"email": user.get("email"),
		"user": user,
	}

