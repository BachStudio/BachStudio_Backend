from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt

from app.core.config import settings


def create_access_token(subject: str, extra_claims: dict[str, Any] | None = None) -> str:
	now = datetime.now(timezone.utc)
	payload: dict[str, Any] = {
		"sub": subject,
		"iat": int(now.timestamp()),
		"exp": int((now + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)).timestamp()),
	}
	if extra_claims:
		payload.update(extra_claims)

	return jwt.encode(payload, settings.SUPABASE_JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def verify_access_token(token: str) -> dict[str, Any]:
	try:
		return jwt.decode(
			token,
			settings.SUPABASE_JWT_SECRET,
			algorithms=[settings.JWT_ALGORITHM],
		)
	except JWTError as exc:
		raise ValueError("Invalid or expired token") from exc


def extract_bearer_token(authorization_header: str | None) -> str | None:
	if not authorization_header:
		return None

	parts = authorization_header.strip().split()
	if len(parts) != 2 or parts[0].lower() != "bearer":
		return None

	return parts[1]
