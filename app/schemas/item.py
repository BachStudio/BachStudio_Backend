from pydantic import BaseModel, ConfigDict, Field


class ItemBase(BaseModel):
	title: str = Field(min_length=1, max_length=120)
	description: str | None = Field(default=None, max_length=500)


class ItemCreate(ItemBase):
	pass


class ItemUpdate(BaseModel):
	title: str | None = Field(default=None, min_length=1, max_length=120)
	description: str | None = Field(default=None, max_length=500)


class ItemResponse(ItemBase):
	id: str
	owner_id: str

	model_config = ConfigDict(from_attributes=True)

