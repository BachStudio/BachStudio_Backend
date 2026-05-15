from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import List, Optional, Any

class CollectBase(BaseModel):
    name: str
    bpm: int = 120
    tracks: List[Any] = []

class CollectCreate(CollectBase):
    pass

class CollectUpdate(BaseModel):
    name: Optional[str] = None
    bpm: Optional[int] = None
    tracks: Optional[List[Any]] = None

class Collect(CollectBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    owner_id: str
    created_at: datetime
    updated_at: datetime