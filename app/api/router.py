from fastapi import APIRouter

from app.api.endpoints import auth, item, user, project

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(user.router, prefix="/users", tags=["users"])
api_router.include_router(item.router, prefix="/items", tags=["items"])

api_router.include_router(project.router, prefix="/projects", tags=["projects"])