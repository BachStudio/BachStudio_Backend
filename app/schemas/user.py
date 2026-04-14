from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
	email: EmailStr
	name: str = Field(min_length=1, max_length=100)


class UserCreate(UserBase):
	password: str = Field(min_length=8, max_length=128)


class UserResponse(UserBase):
	id: str

	model_config = ConfigDict(from_attributes=True)

