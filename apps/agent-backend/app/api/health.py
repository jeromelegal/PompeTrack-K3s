from fastapi import APIRouter

from app.dependencies import get_services

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    services = get_services()
    return await services.agentic.healthcheck()
