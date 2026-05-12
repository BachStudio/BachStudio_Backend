from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
	PROJECT_NAME: str = "BachStudio Backend"
	API_PREFIX: str = "/api/v1"
	DEBUG: bool = False

	SUPABASE_URL: str = Field(default="https://example.supabase.co")
	SUPABASE_PUBLISHABLE_KEY: str = Field(
		default="example-publishable-key",
		validation_alias=AliasChoices("SUPABASE_PUBLISHABLE_KEY", "SUPABASE_ANON_KEY"),
	)
	SUPABASE_SECRET_KEY: str = Field(
		default="example-secret-key",
		validation_alias=AliasChoices("SUPABASE_SECRET_KEY", "SUPABASE_SERVICE_ROLE_KEY"),
	)

	GOOGLE_CLIENT_ID: str = Field(default="")
	GOOGLE_CLIENT_SECRET: str = Field(default="")
	GOOGLE_OAUTH_REDIRECT_URL: str = Field(default="")

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

