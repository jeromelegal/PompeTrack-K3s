from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class PlannerPlan(BaseModel):
    objective_summary: str
    tasks: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)
    research_strategy: str = ""


class ResearchPlan(BaseModel):
    web_queries: list[str] = Field(default_factory=list)
    rag_queries: list[str] = Field(default_factory=list)
    urls_to_scrape: list[str] = Field(default_factory=list)
    workspace_reads: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ToolAction(BaseModel):
    tool: Literal["web_search", "scrape_url", "rag_search", "workspace_list", "workspace_read"]
    input: dict[str, Any] = Field(default_factory=dict)
    reason: str = ""

    @model_validator(mode="after")
    def validate_and_normalize_input(self):
        data = dict(self.input or {})

        if self.tool in {"web_search", "rag_search"}:
            query = data.get("query") or data.get("q") or data.get("search")
            query = str(query or "").strip()
            if not query:
                raise ValueError(f"{self.tool} requires a non-empty input.query")
            self.input = {"query": query}
            return self

        if self.tool == "scrape_url":
            url = data.get("url") or data.get("link")
            url = str(url or "").strip()
            if not url:
                raise ValueError("scrape_url requires a non-empty input.url")
            self.input = {"url": url}
            return self

        if self.tool == "workspace_read":
            path = str(data.get("path") or "").strip()
            if not path:
                raise ValueError("workspace_read requires a non-empty input.path")
            self.input = {"path": path}
            return self

        if self.tool == "workspace_list":
            path = str(data.get("path") or ".").strip() or "."
            self.input = {"path": path}
            return self

        return self


class ExecutorPlan(BaseModel):
    actions: list[ToolAction] = Field(default_factory=list)
    synthesis_focus: str = ""


class CriticReview(BaseModel):
    status: Literal["continue", "done", "failed"]
    reasoning: str
    missing_info: list[str] = Field(default_factory=list)
    final_answer: str = ""
    confidence: float = 0.0