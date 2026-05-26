from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProjectData(BaseModel):
	projectName: str = Field(min_length=1, max_length=120)
	bpm: int | float = Field(gt=0, le=400)
	tracks: list[dict[str, Any]] = Field(default_factory=list)
	timestamp: int = Field(ge=0)

	model_config = ConfigDict(extra="allow")

	@field_validator("projectName")
	@classmethod
	def normalize_project_name(cls, value: str) -> str:
		name = value.strip()
		if not name:
			raise ValueError("projectName must not be empty")
		return name

	@field_validator("tracks", mode="before")
	@classmethod
	def validate_tracks(cls, value: Any) -> list[dict[str, Any]]:
		if value is None:
			return []
		if not isinstance(value, list):
			raise ValueError("tracks must be a list")
		return value
