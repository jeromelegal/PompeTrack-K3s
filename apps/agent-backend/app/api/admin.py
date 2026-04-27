from fastapi import APIRouter, Depends, HTTPException

from app.api.security import require_api_key
from app.dependencies import get_services

router = APIRouter(prefix="/api/v1", tags=["admin"])


@router.get("/runs", dependencies=[Depends(require_api_key)])
async def list_runs(limit: int = 20) -> list[dict]:
    services = get_services()
    return services.state_store.list_runs(limit=limit)


@router.get("/runs/{run_id}", dependencies=[Depends(require_api_key)])
async def get_run(run_id: str) -> dict:
    services = get_services()
    run = services.state_store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return run
