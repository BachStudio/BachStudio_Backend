from pydantic import BaseModel, Field
from typing import List, Optional, Any
from datetime import datetime
from uuid import UUID

class ProjectBase(BaseModel):
    name: str = Field(..., description="프로젝트 이름")
    bpm: float = Field(120.0, description="프로젝트 BPM")
    tracks: Optional[List[Any]] = Field(default=[], description="트랙 정보 목록")

class ProjectCreate(ProjectBase):
    pass

class ProjectResponse(ProjectBase):
    id: UUID
    owner_id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

#트랙 데이터는 유연하게 저장하기 위해 리스트 형태로 받습니다. (Supabase JSONB와 매핑)