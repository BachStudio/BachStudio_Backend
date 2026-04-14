from fastapi import APIRouter

from app.api.endpoints import auth, item, user

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(user.router)
api_router.include_router(item.router)

