from fastapi import FastAPI
from app.api.endpoints.router import api_router
from app.core.config import settings

print("🔴 현재 등록된 Supabase URL:", repr(settings.SUPABASE_URL))

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_PREFIX}/openapi.json"
)

# router.py에서 묶어둔 모든 엔드포인트를 한 번에 등록합니다.
app.include_router(api_router, prefix=settings.API_PREFIX)

@app.get("/", tags=["health"])
def root() -> dict[str, str]:
	return {"message": "BachStudio Backend is running"}

@app.get("/api/v1/health")
def health_check():
    return {"status": "ok"}

@app.get(f"{settings.API_PREFIX}/health", tags=["health"])
def health() -> dict[str, str]:
	return {"status": "ok"}

