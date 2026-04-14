from typing import Any

from fastapi import APIRouter, Depends, status
from supabase import Client

from app.api.deps import get_current_user, get_supabase
from app.schemas.item import ItemCreate, ItemResponse
from app.services import item as item_service

router = APIRouter(prefix="/items", tags=["items"])


@router.get("/")
def list_items(supabase: Client = Depends(get_supabase)) -> list[dict[str, Any]]:
	return item_service.list_items(supabase)


@router.post("/", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
def create_item(
	payload: ItemCreate,
	supabase: Client = Depends(get_supabase),
	current_user: dict[str, Any] = Depends(get_current_user),
) -> ItemResponse:
	owner_id = str(current_user.get("sub", "anonymous"))
	item_data = item_service.create_item(supabase, payload, owner_id=owner_id)
	return ItemResponse.model_validate(item_data)

