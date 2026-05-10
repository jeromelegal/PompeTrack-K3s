from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from app.dependencies import get_services
from app.medplum.health_coach import (
    build_daily_health_features,
    build_conclusion_traces,
    build_medical_export_markdown,
    build_structured_review,
    evaluate_alert_rules,
    generate_daily_health_review,
    generate_weekly_health_review,
    run_synthetic_coach_evaluation,
)
from app.medplum.health_tools import (
    create_health_summary,
    get_health_timeline,
    get_recent_manual_monthly,
    get_recent_medication,
    get_recent_metrics,
    get_recent_spirometry,
    get_recent_stateofminds,
    get_recent_symptoms,
    get_recent_workouts,
)
from app.reminders import create_daily_reminder, delete_reminder, list_reminders


mcp = FastMCP("pompetrack-agent-tools")


def _limit(value: int | None, default: int, maximum: int) -> int:
    if value is None:
        return default
    return max(1, min(value, maximum))


@mcp.tool()
async def web_search(query: str, limit: int | None = None) -> dict[str, Any]:
    """Search the web through the configured SearXNG instance."""
    services = get_services()
    k = _limit(limit, services.settings.max_web_results, services.settings.max_web_results)
    results = await services.websearch.search(query=query, k=k)
    return {"query": query, "results": results}


@mcp.tool()
async def scrape_url(url: str) -> dict[str, Any]:
    """Fetch and extract readable text from an HTTP or HTTPS URL."""
    services = get_services()
    return await services.scraper.fetch(url)


@mcp.tool()
def rag_search(query: str, limit: int | None = None) -> dict[str, Any]:
    """Search the local Qdrant-backed document index."""
    services = get_services()
    k = _limit(limit, services.settings.max_rag_results, services.settings.max_rag_results)
    return services.rag.search(query=query, k=k)


@mcp.tool()
def workspace_list(path: str = ".") -> dict[str, Any]:
    """List files available in the read-only agent workspace."""
    services = get_services()
    return {"path": path, "items": services.workspace.list_files(path)}


@mcp.tool()
def workspace_read(path: str) -> dict[str, Any]:
    """Read a UTF-8 text file from the read-only agent workspace."""
    services = get_services()
    return services.workspace.read_file(path)


@mcp.tool()
def recent_metrics(days: int | None = None) -> dict[str, Any]:
    """Fetch recent simplified FHIR metric observations from Medplum."""
    return {"days": _limit(days, 30, 90), "items": get_recent_metrics(days=_limit(days, 30, 90))}


@mcp.tool()
def recent_medication(days: int | None = None) -> dict[str, Any]:
    """Fetch recent medication intake history from Medplum."""
    return {"days": _limit(days, 30, 90), "items": get_recent_medication(days=_limit(days, 30, 90))}


@mcp.tool()
def recent_symptoms(days: int | None = None) -> dict[str, Any]:
    """Fetch recent symptoms from Medplum."""
    return {"days": _limit(days, 30, 90), "items": get_recent_symptoms(days=_limit(days, 30, 90))}


@mcp.tool()
def recent_stateofminds(days: int | None = None) -> dict[str, Any]:
    """Fetch recent state-of-mind observations from Medplum."""
    return {"days": _limit(days, 30, 90), "items": get_recent_stateofminds(days=_limit(days, 30, 90))}


@mcp.tool()
def recent_workouts(days: int | None = None) -> dict[str, Any]:
    """Fetch recent workouts from Medplum."""
    return {"days": _limit(days, 30, 90), "items": get_recent_workouts(days=_limit(days, 30, 90))}


@mcp.tool()
def recent_spirometry(days: int | None = None) -> dict[str, Any]:
    """Fetch recent spirometry observations from Medplum."""
    return {"days": _limit(days, 30, 90), "items": get_recent_spirometry(days=_limit(days, 30, 90))}


@mcp.tool()
def recent_manual_monthly(days: int | None = None) -> dict[str, Any]:
    """Fetch recent monthly manual observations from Medplum."""
    return {"days": _limit(days, 30, 90), "items": get_recent_manual_monthly(days=_limit(days, 30, 90))}


@mcp.tool()
def health_timeline(days: int | None = None) -> dict[str, Any]:
    """Build a combined health timeline from Medplum data."""
    return get_health_timeline(days=_limit(days, 14, 90))


@mcp.tool()
def health_summary(days: int | None = None) -> dict[str, Any]:
    """Build a compact health summary from Medplum data."""
    return create_health_summary(days=_limit(days, 30, 90))


@mcp.tool()
def daily_health_features(days: int | None = None) -> dict[str, Any]:
    """Compute deterministic health coach features before LLM synthesis."""
    return build_daily_health_features(days=_limit(days, 30, 90))


@mcp.tool()
async def generate_health_review(
    days: int | None = None,
    store: bool = True,
    history_limit: int | None = None,
) -> dict[str, Any]:
    """Generate a health coach review with the configured LLM."""
    return await generate_daily_health_review(
        days=_limit(days, 30, 90),
        store=store,
        history_limit=_limit(history_limit, 7, 14),
    )


@mcp.tool()
async def generate_weekly_health_review_tool(
    days: int | None = None,
    store: bool = True,
    history_limit: int | None = None,
) -> dict[str, Any]:
    """Generate a weekly health coach review focused on slow trends."""
    return await generate_weekly_health_review(
        days=_limit(days, 90, 90),
        store=store,
        history_limit=_limit(history_limit, 7, 14),
    )


@mcp.tool()
def health_reviews(limit: int | None = None) -> dict[str, Any]:
    """List previously generated health coach reviews."""
    services = get_services()
    services.state_store.init_db()
    k = _limit(limit, 10, 50)
    return {"limit": k, "items": services.state_store.list_health_reviews(limit=k)}


@mcp.tool()
def latest_health_review() -> dict[str, Any]:
    """Return the latest generated health coach review."""
    services = get_services()
    services.state_store.init_db()
    review = services.state_store.get_latest_health_review()
    return {"item": review}


@mcp.tool()
def health_coach_alerts(days: int | None = None) -> dict[str, Any]:
    """Evaluate configurable deterministic health coach alerts."""
    features = build_daily_health_features(days=_limit(days, 30, 90))
    return evaluate_alert_rules(features)


@mcp.tool()
def health_coach_trace(days: int | None = None) -> dict[str, Any]:
    """Show which data supports current health coach conclusions."""
    features = build_daily_health_features(days=_limit(days, 30, 90))
    structured = build_structured_review(features=features, review_history=[])
    return {"items": build_conclusion_traces(features, structured)}


@mcp.tool()
def medical_visit_export_markdown(days: int | None = None) -> dict[str, Any]:
    """Generate a Markdown summary for a medical appointment."""
    k = _limit(days, 30, 90)
    return {"days": k, "markdown": build_medical_export_markdown(build_daily_health_features(days=k), days=k)}


@mcp.tool()
def health_coach_synthetic_evaluation() -> dict[str, Any]:
    """Run deterministic synthetic evaluations for the health coach."""
    return run_synthetic_coach_evaluation()


@mcp.tool()
def create_daily_telegram_reminder(text: str, time_of_day: str, user_id: str | None = None) -> dict[str, Any]:
    """Create a persistent daily Telegram reminder. time_of_day must be HH:MM."""
    item = create_daily_reminder(
        text=text,
        time_of_day=time_of_day,
        user_id=user_id or "telegram:automation",
    )
    return {"item": item}


@mcp.tool()
def telegram_reminders(user_id: str | None = None, active_only: bool = True) -> dict[str, Any]:
    """List persistent Telegram reminders."""
    return {"items": list_reminders(user_id=user_id, active_only=active_only, limit=50)}


@mcp.tool()
def delete_telegram_reminder(reminder_id: str, user_id: str | None = None) -> dict[str, Any]:
    """Delete a persistent Telegram reminder by id."""
    item = delete_reminder(reminder_id, user_id=user_id)
    return {"deleted": item is not None, "item": item}


if __name__ == "__main__":
    mcp.run()
