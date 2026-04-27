import asyncio
import time
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, Depends
from fastapi.responses import ORJSONResponse, StreamingResponse

from app.api.security import require_api_key
from app.dependencies import get_services
from app.schemas.openai import ChatCompletionRequest
from app.utils.sse import sse_chunk, sse_done

router = APIRouter(prefix="/v1", tags=["openai-compatible"])


@router.get("/models", dependencies=[Depends(require_api_key)])
async def list_models() -> dict:
    services = get_services()
    return await services.agentic.openai_models_response()


@router.post("/chat/completions", dependencies=[Depends(require_api_key)])
async def chat_completions(request: ChatCompletionRequest):
    services = get_services()
    model_name = request.model or services.settings.default_chat_model

    if request.stream:
        return StreamingResponse(
            _stream_chat(request=request, model_name=model_name),
            media_type="text/event-stream",
        )

    result = await services.agentic.run_once(
        messages=[message.model_dump() for message in request.messages],
        selected_model=model_name,
        session_id=request.session_id,
        user_id=request.user,
    )
    now = int(time.time())
    return ORJSONResponse(
        {
            "id": result["run_id"],
            "object": "chat.completion",
            "created": now,
            "model": model_name,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": result["content"],
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
        }
    )


async def _stream_chat(
    request: ChatCompletionRequest,
    model_name: str,
) -> AsyncGenerator[str, None]:
    services = get_services()
    created = int(time.time())
    chunk_id = f"chatcmpl-{uuid.uuid4().hex}"

    yield sse_chunk(
        {
            "id": chunk_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model_name,
            "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
        }
    )

    async for text in services.agentic.run_streaming_text(
        messages=[message.model_dump() for message in request.messages],
        selected_model=model_name,
        session_id=request.session_id,
        user_id=request.user,
    ):
        if not text:
            continue
        yield sse_chunk(
            {
                "id": chunk_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model_name,
                "choices": [{"index": 0, "delta": {"content": text}, "finish_reason": None}],
            }
        )
        await asyncio.sleep(0)

    yield sse_chunk(
        {
            "id": chunk_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model_name,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        }
    )
    yield sse_done()
