from __future__ import annotations

import secrets
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException, status
from supabase import Client

from app.core.config import settings


GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
GOOGLE_SCOPES = ("openid", "email", "profile")


def build_google_authorization_url(state: str | None = None) -> dict[str, str]:
	ensure_google_oauth_configured()
	clean_state = state or secrets.token_urlsafe(24)
	query = urlencode(
		{
			"client_id": settings.GOOGLE_CLIENT_ID,
			"redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URL,
			"response_type": "code",
			"scope": " ".join(GOOGLE_SCOPES),
			"access_type": "offline",
			"prompt": "select_account",
			"state": clean_state,
		}
	)
	return {
		"authorization_url": f"{GOOGLE_AUTH_URL}?{query}",
		"state": clean_state,
	}


def exchange_google_code(code: str, redirect_uri: str | None = None) -> dict[str, Any]:
	ensure_google_oauth_configured()
	if not code.strip():
		raise HTTPException(
			status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
			detail="Google authorization code is required",
		)

	payload = {
		"code": code,
		"client_id": settings.GOOGLE_CLIENT_ID,
		"client_secret": settings.GOOGLE_CLIENT_SECRET,
		"redirect_uri": redirect_uri or settings.GOOGLE_OAUTH_REDIRECT_URL,
		"grant_type": "authorization_code",
	}
	try:
		with httpx.Client(timeout=10.0) as client:
			token_response = client.post(GOOGLE_TOKEN_URL, data=payload)
			token_response.raise_for_status()
			tokens = token_response.json()
			user_response = client.get(
				GOOGLE_USERINFO_URL,
				headers={"Authorization": f"Bearer {tokens['access_token']}"},
			)
			user_response.raise_for_status()
			userinfo = user_response.json()
	except httpx.HTTPStatusError as exc:
		detail = parse_google_error(exc.response)
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail=f"Google login failed: {detail}",
		) from exc
	except (httpx.RequestError, KeyError, ValueError) as exc:
		raise HTTPException(
			status_code=status.HTTP_502_BAD_GATEWAY,
			detail="Could not complete Google login",
		) from exc

	email = userinfo.get("email")
	if not email:
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="Google account did not return an email address",
		)
	if userinfo.get("email_verified") is False:
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="Google email is not verified",
		)

	return userinfo


def upsert_google_user(client: Client, userinfo: dict[str, Any]) -> dict[str, Any]:
	google_sub = str(userinfo.get("sub") or "")
	email = str(userinfo["email"])
	name = str(userinfo.get("name") or email.split("@", 1)[0])
	avatar_url = userinfo.get("picture")

	payload = {
		"email": email,
		"name": name,
		"provider": "google",
		"provider_id": google_sub,
		"avatar_url": avatar_url,
	}
	try:
		result = client.table("users").upsert(payload, on_conflict="email").execute()
		if result.data:
			return result.data[0]
	except Exception:
		pass

	minimal_payload = {
		"email": email,
		"name": name,
	}
	try:
		result = client.table("users").upsert(minimal_payload, on_conflict="email").execute()
		if result.data:
			return result.data[0]
	except Exception:
		pass

	return {
		"id": google_sub or email,
		**payload,
	}


def ensure_google_oauth_configured() -> None:
	if settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET and settings.GOOGLE_OAUTH_REDIRECT_URL:
		return
	raise HTTPException(
		status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
		detail="Google OAuth is not configured",
	)


def parse_google_error(response: httpx.Response) -> str:
	try:
		body = response.json()
	except ValueError:
		return response.text or response.reason_phrase
	if isinstance(body, dict):
		return str(body.get("error_description") or body.get("error") or response.reason_phrase)
	return response.reason_phrase
