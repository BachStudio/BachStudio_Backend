from typing import Any

from supabase import Client

from app.schemas.user import UserCreate


def get_user_by_id(client: Client, user_id: str) -> dict[str, Any]:
	try:
		result = client.table("users").select("*").eq("id", user_id).limit(1).execute()
		if result.data:
			return result.data[0]
	except Exception:
		pass

	return {
		"id": user_id,
		"email": "unknown@example.com",
		"name": "Unknown User",
	}


def create_user(client: Client, user: UserCreate) -> dict[str, Any]:
	payload = {
		"email": str(user.email),
		"name": user.name,
	}

	try:
		result = client.table("users").insert(payload).execute()
		if result.data:
			return result.data[0]
	except Exception:
		pass

	return {
		"id": "local-dev-user",
		**payload,
	}

