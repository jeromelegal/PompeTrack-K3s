from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)


class WebSearchService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def search(self, query: str, k: int | None = None) -> list[dict[str, Any]]:
        limit = min(k or self.settings.max_web_results, self.settings.max_web_results)
        url = f"{self.settings.searxng_base_url.rstrip('/')}/search"
        params = {
            "q": query,
            "format": "json",
            "categories": "general",
            "language": "auto",
            "pageno": 1,
        }
        async with httpx.AsyncClient(timeout=self.settings.http_timeout_seconds, follow_redirects=True) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
        payload = response.json()
        logger.info(
                "searx raw payload",
                extra={
                    "query": query,
                    "number_of_results": payload.get("number_of_results"),
                    "results_len": len(payload.get("results", []) or []),
                },
            )
        results = payload.get("results", [])[:limit]
        cleaned: list[dict[str, Any]] = []
        for item in results:
            cleaned.append(
                {
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "content": item.get("content", ""),
                    "engine": item.get("engine", ""),
                    "publishedDate": item.get("publishedDate", ""),
                }
            )
        logger.info("web search completed", extra={"query": query, "results": len(cleaned)})
        return cleaned

    async def ping(self) -> bool:
        url = self.settings.searxng_base_url.rstrip("/")
        try:
            async with httpx.AsyncClient(
                timeout=min(3.0, self.settings.http_timeout_seconds),
                follow_redirects=True,
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("searxng ping failed", extra={"error": str(exc), "url": url})
            return False
