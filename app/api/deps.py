from typing import Any

from fastapi import Header, HTTPException, status
from supabase import Client

from app.core.security import extract_bearer_token, verify_access_token
from app.core.supabase import get_supabase_client


def get_supabase() -> Client:
	return get_supabase_client()


def get_current_user(authorization: str | None = Header(default=None)) -> dict[str, Any]:
	token = extract_bearer_token(authorization)
	if not token:
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="Authorization header is missing or invalid",
		)

	try:
		payload = verify_access_token(token)
	except ValueError as exc:
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="Invalid or expired token",
		) from exc

	return payload

