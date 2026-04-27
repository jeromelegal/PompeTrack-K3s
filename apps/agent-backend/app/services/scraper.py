from __future__ import annotations

import io
import logging
from typing import Any
from urllib.parse import urlparse

import httpx
import trafilatura
from bs4 import BeautifulSoup
from pypdf import PdfReader

from app.core.config import Settings
from app.utils.network import is_url_allowed

logger = logging.getLogger(__name__)


class ScraperService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def fetch(self, url: str) -> dict[str, Any]:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("only http/https URLs are allowed")

        if not is_url_allowed(url, allow_private=self.settings.allow_private_network_scraping):
            raise ValueError("URL is blocked by safe network policy")

        async with httpx.AsyncClient(
            timeout=self.settings.http_timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": "local-agentic-stack/0.1"},
        ) as client:
            response = await client.get(url)
            response.raise_for_status()

        content_type = response.headers.get("content-type", "").lower()
        title = ""
        text = ""

        if "application/pdf" in content_type or url.lower().endswith(".pdf"):
            reader = PdfReader(io.BytesIO(response.content))
            pages: list[str] = []
            for page in reader.pages[:20]:
                pages.append(page.extract_text() or "")
            text = "\n".join(pages)
        else:
            html = response.text
            text = trafilatura.extract(html, include_links=True, include_images=False) or ""
            if not text:
                soup = BeautifulSoup(html, "html.parser")
                title = soup.title.text.strip() if soup.title and soup.title.text else ""
                text = soup.get_text("\n", strip=True)
            if not title:
                soup = BeautifulSoup(html, "html.parser")
                title = soup.title.text.strip() if soup.title and soup.title.text else ""

        text = text.strip()[: self.settings.max_scrape_chars]
        logger.info("scrape completed", extra={"url": url, "chars": len(text)})
        return {
            "url": url,
            "title": title,
            "content": text,
            "content_type": content_type,
        }
