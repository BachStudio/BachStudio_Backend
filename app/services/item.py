from typing import Any

from supabase import Client

from app.schemas.item import ItemCreate


def list_items(client: Client) -> list[dict[str, Any]]:
	try:
		result = client.table("items").select("*").execute()
		return result.data or []
	except Exception:
		return []


def create_item(client: Client, item: ItemCreate, owner_id: str) -> dict[str, Any]:
	payload = {
		"title": item.title,
		"description": item.description,
		"owner_id": owner_id,
	}

	try:
		result = client.table("items").insert(payload).execute()
		if result.data:
			return result.data[0]
	except Exception:
		pass

	return {
		"id": "local-dev-item",
		**payload,
	}

