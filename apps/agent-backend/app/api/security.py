from fastapi import Header, HTTPException

from app.core.config import get_settings


async def require_api_key(authorization: str | None = Header(default=None)) -> None:
    settings = get_settings()
    if not settings.backend_api_key:
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    if token != settings.backend_api_key:
        raise HTTPException(status_code=403, detail="invalid bearer token")
