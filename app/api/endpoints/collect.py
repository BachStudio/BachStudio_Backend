from fastapi import APIRouter, Depends, status, HTTPException
from typing import List
from uuid import UUID
from app.api import deps
from app.schemas.collect import Collect, CollectCreate, CollectUpdate
from app.services.collect import CollectService

router = APIRouter()

@router.get("/", response_model=List[Collect])
async def list_collects(
    user_id: str = Depends(deps.get_current_user),
    db = Depends(deps.get_supabase)
):
    service = CollectService(db)
    return await service.get_collects(user_id)

@router.post("/", response_model=Collect, status_code=status.HTTP_201_CREATED)
async def create_collect(
    collect_in: CollectCreate,
    user_id: str = Depends(deps.get_current_user),
    db = Depends(deps.get_supabase)
):
    service = CollectService(db)
    return await service.create_collect(collect_in, user_id)

@router.get("/{collect_id}", response_model=Collect)
async def get_collect(
    collect_id: UUID,
    user_id: str = Depends(deps.get_current_user),
    db = Depends(deps.get_supabase)
):
    service = CollectService(db)
    return await service.get_collect(collect_id, user_id)

@router.put("/{collect_id}", response_model=Collect)
async def update_collect(
    collect_id: UUID,
    collect_update: CollectUpdate,
    user_id: str = Depends(deps.get_current_user),
    db = Depends(deps.get_supabase)
):
    service = CollectService(db)
    return await service.update_collect(collect_id, collect_update, user_id)

@router.delete("/{collect_id}")
async def delete_collect(
    collect_id: UUID,
    user_id: str = Depends(deps.get_current_user),
    db = Depends(deps.get_supabase)
):
    service = CollectService(db)
    return await service.delete_collect(collect_id, user_id)