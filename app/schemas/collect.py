from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID
from typing import Optional

class CollectBase(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: Optional[str] = Field(default=None, max_length=500)

class CollectCreate(CollectBase):
    pass

class CollectUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=120)
    description: Optional[str] = Field(default=None, max_length=500)

class Collect(CollectBase):
    id: UUID
    owner_id: str

    model_config = ConfigDict(from_attributes=True)