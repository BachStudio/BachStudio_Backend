from functools import lru_cache

from supabase import Client, create_client

from app.core.config import settings


@lru_cache
def get_supabase_client() -> Client:
	return create_client(settings.SUPABASE_URL, settings.SUPABASE_PUBLISHABLE_KEY)


from supabase import Client
from fastapi import HTTPException
from app.schemas.project import ProjectCreate

def get_projects(supabase: Client, user_id: str):
    """현재 로그인한 사용자의 모든 프로젝트를 조회합니다."""
    try:
        response = supabase.table("projects").select("*").eq("owner_id", user_id).execute()
        return response.data
    except Exception as e:
        # DB 에러를 명시적으로 처리합니다.
        raise HTTPException(status_code=500, detail=f"프로젝트 목록 조회 실패: {str(e)}")

def create_project(supabase: Client, project_in: ProjectCreate, user_id: str):
    """새로운 프로젝트를 생성합니다."""
    data = project_in.model_dump()
    data["owner_id"] = user_id
    
    try:
        response = supabase.table("projects").insert(data).execute()
        if not response.data:
            raise HTTPException(status_code=400, detail="프로젝트를 생성하지 못했습니다.")
        return response.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"프로젝트 생성 에러: {str(e)}")

def delete_project(supabase: Client, project_id: str, user_id: str):
    """특정 프로젝트를 삭제합니다. 본인 소유만 삭제 가능합니다."""
    try:
        # 소유권 검증(owner_id)을 포함하여 삭제
        response = supabase.table("projects").delete().eq("id", project_id).eq("owner_id", user_id).execute()
        
        # Supabase python client는 삭제된 행이 없으면 빈 배열을 반환합니다.
        if not response.data:
            raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없거나 삭제할 권한이 없습니다.")
        return response.data[0]
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"프로젝트 삭제 에러: {str(e)}")