import json
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
	PROJECT_NAME: str = "BachStudio Backend"
	API_PREFIX: str = "/api/v1"
	DEBUG: bool = False
	CORS_ORIGINS: list[str] = [
		"http://localhost:5173",
		"http://127.0.0.1:5173",
		"http://localhost:3000",
		"http://127.0.0.1:3000",
	]

	AI_PREFER_RMVPE: bool = True
	AI_RMVPE_MODEL_PATH: str | None = None
	AI_CONFIDENCE_THRESHOLD: float = 0.30
	AI_MIN_NOTE_DURATION_BEATS: float = 0.0625
	AI_MAX_FRAME_GAP_MS: float = 140.0
	AI_MAX_PITCH_JUMP_SEMITONES: float = 0.75
	AI_SNAP_TO_SCALE: bool = True
	AI_SCALE_SNAP_MAX_SEMITONES: float = 1.0
	AI_MAX_UPLOAD_AUDIO_SECONDS: float = 300.0
	AI_MAX_REALTIME_AUDIO_SECONDS: float = 300.0

	SUPABASE_URL: str = Field(default="https://example.supabase.co")
	SUPABASE_ANON_KEY: str = Field(default="example-anon-key")
	SUPABASE_JWT_SECRET: str = Field(default="change-me")

	JWT_ALGORITHM: str = "HS256"
	JWT_EXPIRE_MINUTES: int = 60

	@field_validator("DEBUG", mode="before")
	@classmethod
	def parse_debug(cls, value: bool | str) -> bool:
		if isinstance(value, bool):
			return value
		normalized = value.strip().lower()
		if normalized in {"1", "true", "yes", "on", "debug", "development", "dev"}:
			return True
		if normalized in {"0", "false", "no", "off", "release", "production", "prod"}:
			return False
		return bool(value)

	@field_validator("CORS_ORIGINS", mode="before")
	@classmethod
	def parse_cors_origins(cls, value: list[str] | str) -> list[str]:
		if isinstance(value, list):
			return value
		try:
			parsed = json.loads(value)
			if isinstance(parsed, list):
				return [str(origin) for origin in parsed]
		except json.JSONDecodeError:
			pass
		return [origin.strip() for origin in value.split(",") if origin.strip()]

	model_config = SettingsConfigDict(
		env_file=".env",
		env_file_encoding="utf-8",
		case_sensitive=False,
		extra="ignore",
	)


@lru_cache
def get_settings() -> Settings:
	return Settings()


settings = get_settings()
