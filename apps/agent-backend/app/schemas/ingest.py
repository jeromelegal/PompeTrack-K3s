from pydantic import BaseModel, Field


class PathIngestRequest(BaseModel):
    paths: list[str] = Field(default_factory=list)


class RagSearchRequest(BaseModel):
    query: str
    k: int = 5
