from typing import Any
from fastapi import Request, Depends, HTTPException, status
from fastapi.security import HTTPBearer # 👈 스웨거 UI에 입력 칸을 만들기 위해 추가
from supabase import Client

from app.core.security import extract_bearer_token
from app.core.supabase import get_supabase_client

# 스웨거 UI와 연동할 보안 스키마를 선언합니다 (자동으로 인증 칸/자물쇠를 만들어 줌)
security = HTTPBearer(auto_error=False)

def get_supabase() -> Client:
    return get_supabase_client()


def _to_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    return {
        "id": getattr(value, "id", None),
        "email": getattr(value, "email", None),
        "app_metadata": getattr(value, "app_metadata", None),
        "user_metadata": getattr(value, "user_metadata", None),
    }


def get_current_user(
    request: Request,
    auth_credentials: Any = Depends(security), # 👈 이 줄이 들어가야 스웨거 UI에 입력 칸이 생깁니다!
    supabase: Client = Depends(get_supabase),
) -> dict[str, Any]:
    
    authorization = request.headers.get("Authorization")
    
    if not authorization and auth_credentials:
        authorization = f"Bearer {auth_credentials.credentials}"
        
    if not authorization:
        authorization = request.query_params.get("authorization")
        
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header is missing or invalid",
        )

    token = None
    if " " in authorization:
        try:
            token_type, token_val = authorization.split(" ", 1)
            if token_type.lower() == "bearer":
                token = token_val
        except ValueError:
            pass
            
    if not token:
        token = extract_bearer_token(authorization) or authorization

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header is missing or invalid",
        )

    try:
        try:
            response = supabase.auth.get_user(token)
        except TypeError:
            response = supabase.auth.get_user(jwt=token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc

    user = _to_dict(getattr(response, "user", None))
    user_id = user.get("id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    return str(user_id)