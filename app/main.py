from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.endpoints import humming
from app.api.router import api_router
from app.core.config import settings

app = FastAPI(
	title=settings.PROJECT_NAME,
	debug=settings.DEBUG,
)

app.add_middleware(
	CORSMiddleware,
	allow_origins=settings.CORS_ORIGINS,
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_PREFIX)
app.include_router(humming.router, prefix="/api")


@app.get("/", tags=["health"])
def root() -> dict[str, str]:
	return {"message": "BachStudio Backend is running"}


@app.get(f"{settings.API_PREFIX}/health", tags=["health"])
def health() -> dict[str, str]:
	return {"status": "ok"}
