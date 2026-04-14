from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
	PROJECT_NAME: str = "BachStudio Backend"
	API_PREFIX: str = "/api/v1"
	DEBUG: bool = False

	SUPABASE_URL: str = Field(default="https://example.supabase.co")
	SUPABASE_ANON_KEY: str = Field(default="example-anon-key")
	SUPABASE_JWT_SECRET: str = Field(default="change-me")

	JWT_ALGORITHM: str = "HS256"
	JWT_EXPIRE_MINUTES: int = 60

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
