from __future__ import annotations

import io
import mimetypes
import uuid
from pathlib import Path
from typing import Any

from langchain_ollama import OllamaEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from trafilatura import extract
from bs4 import BeautifulSoup

from app.core.config import Settings


class RAGService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = QdrantClient(url=self.settings.qdrant_url, timeout=self.settings.http_timeout_seconds)
        self.embeddings = OllamaEmbeddings(
            model=self.settings.embedding_model,
            base_url=self.settings.ollama_base_url,
        )
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=150,
        )

    def ping(self) -> bool:
        try:
            return bool(self.client.get_collections())
        except Exception:  # noqa: BLE001
            return False

    def _ensure_collection(self, vector_size: int) -> None:
        if self.client.collection_exists(self.settings.qdrant_collection):
            return
        self.client.create_collection(
            collection_name=self.settings.qdrant_collection,
            vectors_config=qmodels.VectorParams(size=vector_size, distance=qmodels.Distance.COSINE),
        )

    def _extract_text_from_bytes(self, filename: str, payload: bytes) -> tuple[str, dict[str, Any]]:
        suffix = Path(filename).suffix.lower()
        mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

        if suffix in {".txt", ".md"}:
            text = payload.decode("utf-8", errors="ignore")
        elif suffix in {".html", ".htm"}:
            html = payload.decode("utf-8", errors="ignore")
            text = extract(html, include_links=True, include_images=False) or ""
            if not text:
                soup = BeautifulSoup(html, "html.parser")
                text = soup.get_text("\n", strip=True)
        elif suffix == ".pdf":
            reader = PdfReader(io.BytesIO(payload))
            pages = [(page.extract_text() or "") for page in reader.pages[:100]]
            text = "\n".join(pages)
        else:
            raise ValueError(f"unsupported file type: {suffix or filename}")

        return text.strip(), {"mime_type": mime_type, "filename": filename}

    def _ingest_text(self, text: str, source: str, metadata: dict[str, Any]) -> int:
        chunks = self.splitter.split_text(text)
        if not chunks:
            return 0

        vectors = self.embeddings.embed_documents(chunks)
        if not vectors:
            return 0

        self._ensure_collection(len(vectors[0]))

        points: list[qmodels.PointStruct] = []
        for index, (chunk, vector) in enumerate(zip(chunks, vectors, strict=False)):
            payload = {
                "text": chunk,
                "source": source,
                "chunk_index": index,
                **metadata,
            }
            points.append(
                qmodels.PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vector,
                    payload=payload,
                )
            )

        self.client.upsert(collection_name=self.settings.qdrant_collection, points=points)
        return len(points)

    def ingest_uploads(self, files: list[Any]) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        total_chunks = 0
        self.settings.upload_dir.mkdir(parents=True, exist_ok=True)

        for upload in files:
            raw = upload.file.read()
            target = self.settings.upload_dir / (upload.filename or f"upload-{uuid.uuid4().hex}")
            target.write_bytes(raw)
            text, metadata = self._extract_text_from_bytes(upload.filename or target.name, raw)
            count = self._ingest_text(text, source=target.name, metadata=metadata)
            total_chunks += count
            results.append({"file": upload.filename, "chunks": count})

        return {"ingested_files": results, "total_chunks": total_chunks}

    def ingest_workspace_paths(self, paths: list[str]) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        total_chunks = 0
        root = self.settings.workspace_root.resolve()

        for relative_path in paths:
            path = (root / relative_path).resolve()
            if root not in path.parents and path != root:
                raise ValueError(f"path escapes workspace root: {relative_path}")
            if not path.exists() or not path.is_file():
                raise ValueError(f"path not found: {relative_path}")

            raw = path.read_bytes()
            text, metadata = self._extract_text_from_bytes(path.name, raw)
            count = self._ingest_text(text, source=str(path.relative_to(root)), metadata=metadata)
            total_chunks += count
            results.append({"path": str(path.relative_to(root)), "chunks": count})

        return {"ingested_paths": results, "total_chunks": total_chunks}

    def search(self, query: str, k: int | None = None) -> dict[str, Any]:
        limit = min(k or self.settings.max_rag_results, self.settings.max_rag_results)
        if not self.client.collection_exists(self.settings.qdrant_collection):
            return {
                "query": query,
                "results": [],
                "warning": f"collection `{self.settings.qdrant_collection}` does not exist",
            }

        vector = self.embeddings.embed_query(query)
        response = self.client.query_points(
            collection_name=self.settings.qdrant_collection,
            query=vector,
            limit=limit,
            with_payload=True,
        )

        points = getattr(response, "points", []) or []
        hits: list[dict[str, Any]] = []
        for point in points:
            payload = point.payload or {}
            hits.append(
                {
                    "id": str(point.id),
                    "score": float(point.score),
                    "source": payload.get("source", ""),
                    "chunk_index": payload.get("chunk_index"),
                    "text": payload.get("text", ""),
                    "mime_type": payload.get("mime_type", ""),
                }
            )

        return {"query": query, "results": hits}
