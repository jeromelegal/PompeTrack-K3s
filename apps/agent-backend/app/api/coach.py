from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException

from app.api.security import require_api_key
from app.dependencies import get_services
from app.medplum.health_coach import (
    build_daily_health_features,
    generate_daily_health_review,
    generate_weekly_health_review,
)

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


@router.post("/weekly-review", dependencies=[Depends(require_api_key)])
async def run_weekly_review(days: int = 90, store: bool = True, history_limit: int = 7) -> dict:
    return await generate_weekly_health_review(
        days=days,
        store=store,
        history_limit=history_limit,
    )


@router.get("/reviews", dependencies=[Depends(require_api_key)])
async def list_reviews(limit: int = 20) -> list[dict]:
    services = get_services()
    services.state_store.init_db()
    return services.state_store.list_health_reviews(limit=limit)


@router.get("/reviews/latest", dependencies=[Depends(require_api_key)])
async def get_latest_review() -> dict:
    services = get_services()
    services.state_store.init_db()
    review = services.state_store.get_latest_health_review()
    if review is None:
        raise HTTPException(status_code=404, detail="health review not found")
    return review


@router.get("/reviews/{review_id}", dependencies=[Depends(require_api_key)])
async def get_review(review_id: str) -> dict:
    services = get_services()
    services.state_store.init_db()
    review = services.state_store.get_health_review(review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="health review not found")
    return review


@router.get("/preferences/{user_id}", dependencies=[Depends(require_api_key)])
async def get_preferences(user_id: str) -> dict:
    services = get_services()
    return services.state_store.get_user_preferences(user_id)


@router.patch("/preferences/{user_id}", dependencies=[Depends(require_api_key)])
async def update_preferences(user_id: str, patch: dict[str, Any] = Body(...)) -> dict:
    services = get_services()
    return services.state_store.update_user_preferences(user_id, patch)


@router.post("/feedback", dependencies=[Depends(require_api_key)])
async def submit_feedback(payload: dict[str, Any] = Body(...)) -> dict:
    services = get_services()
    user_id = str(payload.get("userId") or "").strip()
    feedback_type = str(payload.get("feedbackType") or "").strip()
    if not user_id or not feedback_type:
        raise HTTPException(status_code=400, detail="userId and feedbackType are required")
    return services.state_store.add_review_feedback(
        user_id=user_id,
        feedback_type=feedback_type,
        review_id=payload.get("reviewId"),
        comment=payload.get("comment"),
    )
