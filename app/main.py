from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import settings

app = FastAPI(
	title=settings.PROJECT_NAME,
	debug=settings.DEBUG,
)

app.include_router(api_router, prefix=settings.API_PREFIX)


@app.get("/", tags=["health"])
def root() -> dict[str, str]:
	return {"message": "BachStudio Backend is running"}


@app.get(f"{settings.API_PREFIX}/health", tags=["health"])
def health() -> dict[str, str]:
	return {"status": "ok"}

