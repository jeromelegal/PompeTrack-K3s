from __future__ import annotations

import logging
from typing import Any, Type

import httpx
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from pydantic import BaseModel

from app.core.config import Settings

logger = logging.getLogger(__name__)


class OllamaService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def list_local_models(self) -> list[dict[str, Any]]:
        url = f"{self.settings.ollama_base_url.rstrip('/')}/api/tags"
        try:
            async with httpx.AsyncClient(timeout=self.settings.http_timeout_seconds) as client:
                response = await client.get(url)
                response.raise_for_status()
            payload = response.json()
            return payload.get("models", [])
        except Exception as exc:  # noqa: BLE001
            logger.warning("failed to list ollama models", extra={"error": str(exc), "url": url})
            return []

    async def ping(self) -> bool:
        models = await self.list_local_models()
        return isinstance(models, list)

    def build_chat_model(self, model_name: str, temperature: float | None = None) -> ChatOllama:
        return ChatOllama(
            model=model_name,
            base_url=self.settings.ollama_base_url,
            temperature=self.settings.model_temperature if temperature is None else temperature,
        )

    async def structured_invoke(
        self,
        model_name: str,
        schema: Type[BaseModel],
        system_prompt: str,
        user_prompt: str,
    ) -> BaseModel:
        model = self.build_chat_model(model_name).with_structured_output(schema, method="json_schema")
        return await model.ainvoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]
        )

    async def plain_invoke(
        self,
        model_name: str,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        model = self.build_chat_model(model_name)
        result = await model.ainvoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]
        )
        content = result.content
        if isinstance(content, list):
            return "\n".join(str(item) for item in content)
        return str(content)
