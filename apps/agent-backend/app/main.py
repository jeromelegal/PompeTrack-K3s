from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, coach, health, ingest, openai_compat, reminders
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.dependencies import get_services


settings = get_settings()
configure_logging(settings.log_level)

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

allow_origins = [origin.strip() for origin in settings.allow_origins.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(openai_compat.router)
app.include_router(ingest.router)
app.include_router(admin.router)
app.include_router(coach.router)
app.include_router(reminders.router)


@app.on_event("startup")
async def startup_event() -> None:
    services = get_services()
    services.state_store.init_db()
    services.ensure_directories()
    await services.agentic.startup()


@app.on_event("shutdown")
async def shutdown_event() -> None:
    services = get_services()
    await services.agentic.shutdown()
