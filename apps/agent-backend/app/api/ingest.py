from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.concurrency import run_in_threadpool

from app.api.security import require_api_key
from app.dependencies import get_services
from app.schemas.ingest import PathIngestRequest, RagSearchRequest

router = APIRouter(prefix="/api/v1", tags=["ingest"])


@router.post("/ingest/files", dependencies=[Depends(require_api_key)])
async def ingest_files(files: list[UploadFile] = File(...)) -> dict:
    services = get_services()
    return await run_in_threadpool(services.rag.ingest_uploads, files)


@router.post("/ingest/paths", dependencies=[Depends(require_api_key)])
async def ingest_paths(request: PathIngestRequest) -> dict:
    services = get_services()
    return await run_in_threadpool(services.rag.ingest_workspace_paths, request.paths)


@router.post("/rag/search", dependencies=[Depends(require_api_key)])
async def rag_search(request: RagSearchRequest) -> dict:
    services = get_services()
    return await run_in_threadpool(services.rag.search, request.query, request.k)
