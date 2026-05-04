from fastapi import APIRouter, Depends, HTTPException

from app.api.security import require_api_key
from app.dependencies import get_services
from app.medplum.health_coach import build_daily_health_features, generate_daily_health_review

router = APIRouter(prefix="/api/v1/health-coach", tags=["health-coach"])


@router.get("/features", dependencies=[Depends(require_api_key)])
async def health_features(days: int = 30) -> dict:
    return build_daily_health_features(days=days)


@router.post("/daily-review", dependencies=[Depends(require_api_key)])
async def run_daily_review(days: int = 30, store: bool = True, history_limit: int = 7) -> dict:
    return await generate_daily_health_review(
        days=days,
        store=store,
        history_limit=history_limit,
    )


@router.get("/reviews", dependencies=[Depends(require_api_key)])
async def list_reviews(limit: int = 20) -> list[dict]:
    services = get_services()
    services.state_store.init_db()
    return services.state_store.list_health_reviews(limit=limit)


@router.get("/reviews/{review_id}", dependencies=[Depends(require_api_key)])
async def get_review(review_id: str) -> dict:
    services = get_services()
    services.state_store.init_db()
    review = services.state_store.get_health_review(review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="health review not found")
    return review
