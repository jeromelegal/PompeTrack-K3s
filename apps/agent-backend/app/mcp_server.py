from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from app.dependencies import get_services


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


if __name__ == "__main__":
    mcp.run()
