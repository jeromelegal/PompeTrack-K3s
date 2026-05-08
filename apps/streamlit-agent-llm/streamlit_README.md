# Streamlit admin UI for the local agentic backend

## Files
- `streamlit_admin.py`
- `streamlit_requirements.txt`

## What it adds
This Streamlit app exposes the backend features that Open WebUI does not surface directly:

- backend healthcheck (`/health`)
- models list (`/v1/models`)
- upload ingestion (`/api/v1/ingest/files`)
- workspace-path ingestion (`/api/v1/ingest/paths`)
- RAG search (`/api/v1/rag/search`)
- runs list and run detail (`/api/v1/runs`, `/api/v1/runs/{run_id}`)
- direct local workspace browsing/reading/uploading
- direct Qdrant inspection
- direct SQLite inspection for `app.sqlite` and LangGraph checkpoints

## Recommended environment variables
- `BACKEND_BASE_URL=http://backend:8000`
- `BACKEND_API_KEY=local-agentic-dev-key`
- `WORKSPACE_ROOT=/workspace`
- `DATA_DIR=/data`
- `STATE_DB_PATH=/data/app.sqlite`
- `CHECKPOINT_DB_PATH=/data/langgraph-checkpoints.sqlite`
- `QDRANT_URL=http://qdrant:6333`
- `QDRANT_COLLECTION=documents`

## Run locally
```bash
pip install -r streamlit_requirements.txt
streamlit run streamlit_admin.py
```

## Typical Docker Compose service
```yaml
streamlit-admin:
  image: python:3.12-slim
  working_dir: /app
  command: bash -lc "pip install -r /app/streamlit_requirements.txt && streamlit run /app/streamlit_admin.py --server.port=8501 --server.address=0.0.0.0"
  volumes:
    - ./streamlit_admin.py:/app/streamlit_admin.py:ro
    - ./streamlit_requirements.txt:/app/streamlit_requirements.txt:ro
    - ./workspace:/workspace
    - ./data:/data
  environment:
    BACKEND_BASE_URL: http://backend:8000
    BACKEND_API_KEY: local-agentic-dev-key
    WORKSPACE_ROOT: /workspace
    DATA_DIR: /data
    STATE_DB_PATH: /data/app.sqlite
    CHECKPOINT_DB_PATH: /data/langgraph-checkpoints.sqlite
    QDRANT_URL: http://qdrant:6333
    QDRANT_COLLECTION: documents
  ports:
    - "8501:8501"
  depends_on:
    - backend
    - qdrant
```

## Notes
- the app intentionally stays read-only for SQLite and Qdrant inspection
- it writes files only into `WORKSPACE_ROOT`
- it reuses the backend's existing API key authentication for HTTP endpoints
