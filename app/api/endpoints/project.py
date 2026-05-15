from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from supabase import Client

from app.api.deps import get_supabase, get_current_user
from app.schemas.project import ProjectResponse, ProjectCreate
from app.services import project as project_service

router = APIRouter()

@router.get("/", response_model=List[ProjectResponse])
def get_user_projects(
    supabase: Client = Depends(get_supabase),
    current_user: dict = Depends(get_current_user)
):
    """내 프로젝트 목록을 조회합니다."""
    return project_service.get_projects(supabase, current_user["sub"])

@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_new_project(
    project_in: ProjectCreate,
    supabase: Client = Depends(get_supabase),
    current_user: dict = Depends(get_current_user)
):
    """새 프로젝트를 저장합니다."""
    return project_service.create_project(supabase, project_in, current_user["sub"])

@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_existing_project(
    project_id: str,
    supabase: Client = Depends(get_supabase),
    current_user: dict = Depends(get_current_user)
):
    """프로젝트를 삭제합니다."""
    project_service.delete_project(supabase, project_id, current_user["sub"])
    return None # 204 No Content는 본문을 반환하지 않음