from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

import httpx
import streamlit as st
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels


DEFAULT_BACKEND_URL = os.getenv("BACKEND_BASE_URL", "http://localhost:8000")
DEFAULT_API_KEY = os.getenv("BACKEND_API_KEY", "local-agentic-dev-key")
DEFAULT_WORKSPACE_ROOT = Path(os.getenv("WORKSPACE_ROOT", "/workspace"))
DEFAULT_DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))
DEFAULT_QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
DEFAULT_QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "documents")
DEFAULT_STATE_DB_PATH = Path(os.getenv("STATE_DB_PATH", str(DEFAULT_DATA_DIR / "app.sqlite")))
DEFAULT_CHECKPOINT_DB_PATH = Path(
    os.getenv("CHECKPOINT_DB_PATH", str(DEFAULT_DATA_DIR / "langgraph-checkpoints.sqlite"))
)

TEXT_PREVIEW_SUFFIXES = {
    ".txt",
    ".md",
    ".py",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".log",
    ".csv",
    ".html",
    ".htm",
    ".sql",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
}


st.set_page_config(
    page_title="Local Agentic Stack Admin",
    page_icon="🧠",
    layout="wide",
)


@st.cache_resource(show_spinner=False)
def get_qdrant_client(qdrant_url: str) -> QdrantClient:
    return QdrantClient(url=qdrant_url, timeout=15.0)


class BackendClient:
    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}

    def get(self, path: str, **kwargs: Any) -> httpx.Response:
        with httpx.Client(timeout=60.0) as client:
            return client.get(f"{self.base_url}{path}", headers=self.headers, **kwargs)

    def post(self, path: str, **kwargs: Any) -> httpx.Response:
        with httpx.Client(timeout=180.0) as client:
            return client.post(f"{self.base_url}{path}", headers=self.headers, **kwargs)

    def download(self, path: str, **kwargs: Any) -> httpx.Response:
        with httpx.Client(timeout=180.0) as client:
            return client.get(f"{self.base_url}{path}", headers=self.headers, **kwargs)



def init_state() -> None:
    st.session_state.setdefault("backend_url", DEFAULT_BACKEND_URL)
    st.session_state.setdefault("api_key", DEFAULT_API_KEY)
    st.session_state.setdefault("workspace_root", str(DEFAULT_WORKSPACE_ROOT))
    st.session_state.setdefault("data_dir", str(DEFAULT_DATA_DIR))
    st.session_state.setdefault("qdrant_url", DEFAULT_QDRANT_URL)
    st.session_state.setdefault("qdrant_collection", DEFAULT_QDRANT_COLLECTION)
    st.session_state.setdefault("state_db_path", str(DEFAULT_STATE_DB_PATH))
    st.session_state.setdefault("checkpoint_db_path", str(DEFAULT_CHECKPOINT_DB_PATH))



def safe_resolve(base_dir: Path, relative_path: str) -> Path:
    base_dir = base_dir.resolve()
    target = (base_dir / relative_path).resolve()
    if target != base_dir and base_dir not in target.parents:
        raise ValueError("Path escapes base directory")
    return target



def read_json_response(response: httpx.Response) -> Any:
    response.raise_for_status()
    return response.json()



def sqlite_table_names(db_path: Path) -> list[str]:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
    return [row[0] for row in rows]



def sqlite_query(db_path: Path, query: str, params: tuple[Any, ...] = ()) -> tuple[list[str], list[tuple[Any, ...]]]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(query, params)
        rows = cur.fetchall()
        columns = [col[0] for col in (cur.description or [])]
    return columns, [tuple(row) for row in rows]



def render_table(columns: list[str], rows: list[tuple[Any, ...]], height: int = 320) -> None:
    table = [dict(zip(columns, row, strict=False)) for row in rows]
    st.dataframe(table, use_container_width=True, height=height)



def sidebar() -> tuple[BackendClient, Path, Path, Path, Path, str]:
    with st.sidebar:
        st.header("Configuration")
        st.text_input("Backend base URL", key="backend_url")
        st.text_input("API key", key="api_key", type="password")
        st.text_input("Workspace root", key="workspace_root")
        st.text_input("Data dir", key="data_dir")
        st.text_input("State SQLite path", key="state_db_path")
        st.text_input("Checkpoint SQLite path", key="checkpoint_db_path")
        st.text_input("Qdrant URL", key="qdrant_url")
        st.text_input("Qdrant collection", key="qdrant_collection")
        st.caption(
            "Astuce: si Streamlit tourne dans le même conteneur/projet que le backend, les chemins par défaut \n"
            "`/workspace` et `/data` peuvent être utilisés directement."
        )

    backend = BackendClient(st.session_state.backend_url, st.session_state.api_key)
    workspace_root = Path(st.session_state.workspace_root)
    data_dir = Path(st.session_state.data_dir)
    state_db_path = Path(st.session_state.state_db_path)
    checkpoint_db_path = Path(st.session_state.checkpoint_db_path)
    qdrant_collection = st.session_state.qdrant_collection
    return backend, workspace_root, data_dir, state_db_path, checkpoint_db_path, qdrant_collection



def tab_overview(backend: BackendClient, workspace_root: Path, state_db_path: Path, checkpoint_db_path: Path) -> None:
    st.subheader("Vue d'ensemble")
    c1, c2, c3, c4 = st.columns(4)

    health_payload: dict[str, Any] | None = None
    try:
        health_payload = read_json_response(backend.get("/health"))
        c1.metric("Backend", health_payload.get("status", "unknown"))
    except Exception as exc:  # noqa: BLE001
        c1.metric("Backend", "unreachable")
        st.warning(f"Healthcheck indisponible: {exc}")

    try:
        models_payload = read_json_response(backend.get("/v1/models"))
        model_count = len(models_payload.get("data", []))
        c2.metric("Modèles Ollama", model_count)
    except Exception:
        c2.metric("Modèles Ollama", "?")

    c3.metric("Workspace présent", "oui" if workspace_root.exists() else "non")
    c4.metric("SQLite runs", "oui" if state_db_path.exists() else "non")

    if health_payload is not None:
        with st.expander("Détail healthcheck", expanded=False):
            st.json(health_payload)

    if state_db_path.exists():
        try:
            cols, rows = sqlite_query(
                state_db_path,
                "SELECT status, COUNT(*) AS total FROM runs GROUP BY status ORDER BY total DESC",
            )
            st.markdown("### Statut des runs")
            if rows:
                render_table(cols, rows, height=180)
            else:
                st.info("Aucun run enregistré.")
        except Exception as exc:  # noqa: BLE001
            st.warning(f"Impossible de lire la base state SQLite: {exc}")

    if checkpoint_db_path.exists():
        with st.expander("Tables disponibles dans la base LangGraph checkpoints", expanded=False):
            try:
                st.write(sqlite_table_names(checkpoint_db_path))
            except Exception as exc:  # noqa: BLE001
                st.warning(f"Lecture checkpoint DB impossible: {exc}")



def tab_endpoints(backend: BackendClient) -> None:
    st.subheader("Fonctions backend non exposées par Open WebUI")

    cols = st.columns(2)
    with cols[0]:
        if st.button("Tester /health", use_container_width=True):
            try:
                st.json(read_json_response(backend.get("/health")))
            except Exception as exc:  # noqa: BLE001
                st.error(str(exc))

    with cols[1]:
        if st.button("Lister /v1/models", use_container_width=True):
            try:
                st.json(read_json_response(backend.get("/v1/models")))
            except Exception as exc:  # noqa: BLE001
                st.error(str(exc))

    st.markdown("### Recherche RAG via endpoint")
    rag_query = st.text_input("Query RAG", value="test")
    rag_k = st.slider("k", min_value=1, max_value=20, value=5)
    if st.button("Appeler /api/v1/rag/search", use_container_width=True):
        try:
            payload = {"query": rag_query, "k": rag_k}
            st.json(read_json_response(backend.post("/api/v1/rag/search", json=payload)))
        except Exception as exc:  # noqa: BLE001
            st.error(str(exc))

    st.markdown("### Runs via endpoints")
    limit = st.slider("Limit runs", 1, 200, 20)
    if st.button("Lister /api/v1/runs", use_container_width=True):
        try:
            st.json(read_json_response(backend.get("/api/v1/runs", params={"limit": limit})))
        except Exception as exc:  # noqa: BLE001
            st.error(str(exc))

    run_id = st.text_input("Run ID")
    if st.button("Lire /api/v1/runs/{run_id}", use_container_width=True, disabled=not run_id.strip()):
        try:
            st.json(read_json_response(backend.get(f"/api/v1/runs/{run_id.strip()}")))
        except Exception as exc:  # noqa: BLE001
            st.error(str(exc))


def _as_table(items: list[dict[str, Any]], keys: list[str]) -> list[dict[str, Any]]:
    return [{key: item.get(key) for key in keys} for item in items]


def tab_health_coach(backend: BackendClient) -> None:
    st.subheader("Coach santé")
    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        days = st.selectbox("Période", options=[30, 90], index=0, format_func=lambda value: f"{value} jours")
    with c2:
        history_limit = st.slider("Historique revues", 1, 20, 10)
    with c3:
        st.caption("Revue, tendances, watchlist, anomalies, historique, qualité données, exports, alertes et traçabilité.")

    try:
        dashboard = read_json_response(
            backend.get("/api/v1/health-coach/dashboard", params={"days": days, "review_limit": history_limit})
        )
    except Exception as exc:  # noqa: BLE001
        st.error(f"Coach santé indisponible: {exc}")
        return

    features = dashboard.get("features") or {}
    structured = dashboard.get("structuredReview") or {}
    latest = dashboard.get("latestReview") or {}
    alerts = dashboard.get("alerts") or {}
    counts = features.get("counts") or {}
    quality = features.get("dataQuality") or {}

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Confiance données", quality.get("level", "unknown"), quality.get("score"))
    m2.metric("Événements récents", sum(int(value or 0) for value in counts.values()))
    m3.metric("Alertes", len(alerts.get("alerts") or []))
    m4.metric("Dernière revue", latest.get("review_date") or "aucune")

    a1, a2, a3, a4 = st.columns(4)
    with a1:
        if st.button("Générer revue 30j", use_container_width=True):
            with st.spinner("Génération de la revue quotidienne..."):
                st.json(read_json_response(backend.post("/api/v1/health-coach/daily-review", params={"days": 30})))
    with a2:
        if st.button("Générer bilan 90j", use_container_width=True):
            with st.spinner("Génération du bilan hebdomadaire..."):
                st.json(read_json_response(backend.post("/api/v1/health-coach/weekly-review", params={"days": 90})))
    with a3:
        if st.button("Évaluer alertes", use_container_width=True):
            st.json(read_json_response(backend.post("/api/v1/health-coach/alerts/evaluate", params={"days": days})))
    with a4:
        if st.button("Tests synthétiques", use_container_width=True):
            st.json(read_json_response(backend.get("/api/v1/health-coach/evaluation")))

    t1, t2, t3, t4, t5, t6 = st.tabs(
        ["Dernière revue", "Tendances", "Watchlist", "Historique", "Traçabilité", "Exports"]
    )

    with t1:
        if latest:
            st.markdown(f"### {latest.get('review_date')} - {latest.get('status')}")
            st.write(latest.get("review_text") or "Revue sans texte.")
            with st.expander("Synthèse structurée"):
                st.json(latest.get("structuredReview") or structured)
        else:
            st.info("Aucune revue stockée pour l'instant.")
        st.markdown("### Qualité des données")
        st.json(quality)

    with t2:
        st.markdown("### Mesures")
        st.dataframe(_as_table(features.get("metricTrends") or [], ["label", "recentAverage", "previousAverage", "delta", "unit", "count"]), use_container_width=True, height=240)
        st.markdown("### Spirométrie")
        st.dataframe(_as_table(features.get("spirometryTrends") or [], ["label", "recentAverage", "previousAverage", "delta", "unit", "count"]), use_container_width=True, height=220)
        st.markdown("### Humeur")
        st.dataframe(_as_table(features.get("stateOfMindTrends") or [], ["label", "recentAverage", "previousAverage", "delta", "unit", "count"]), use_container_width=True, height=220)

    with t3:
        st.markdown("### Watchlist personnalisée")
        st.dataframe(_as_table(features.get("personalWatchlist") or [], ["label", "status", "severity", "recentCount", "latestDate", "reason"]), use_container_width=True, height=240)
        st.markdown("### Anomalies")
        st.dataframe(_as_table(features.get("anomalies") or [], ["severity", "source", "label", "direction", "delta", "reason"]), use_container_width=True, height=240)
        st.markdown("### Alertes configurables")
        st.dataframe(_as_table(alerts.get("alerts") or [], ["severity", "ruleId", "label", "reason"]), use_container_width=True, height=220)

    with t4:
        reviews = dashboard.get("reviews") or []
        st.dataframe(_as_table(reviews, ["review_date", "period_days", "status", "model", "review_id", "created_at"]), use_container_width=True, height=320)
        review_id = st.text_input("Review ID à inspecter", value="")
        if st.button("Charger la revue", use_container_width=True, disabled=not review_id.strip()):
            st.json(read_json_response(backend.get(f"/api/v1/health-coach/reviews/{review_id.strip()}")))

    with t5:
        traces = structured.get("traceability") or []
        st.dataframe(_as_table(traces, ["id", "conclusion", "source", "count", "periodDays", "wording"]), use_container_width=True, height=320)
        with st.expander("Mode multi-agent spécialisé"):
            st.json(structured.get("specializedAgents") or {})

    with t6:
        export_days = st.radio("Fenêtre export", options=[30, 90], horizontal=True, format_func=lambda value: f"{value} jours")
        c_md, c_pdf = st.columns(2)
        with c_md:
            try:
                response = backend.download("/api/v1/health-coach/export/markdown", params={"days": export_days})
                response.raise_for_status()
                st.download_button("Télécharger Markdown", data=response.content, file_name=f"resume-sante-{export_days}j.md", mime="text/markdown", use_container_width=True)
            except Exception as exc:  # noqa: BLE001
                st.warning(f"Export Markdown indisponible: {exc}")
        with c_pdf:
            try:
                response = backend.download("/api/v1/health-coach/export/pdf", params={"days": export_days})
                response.raise_for_status()
                st.download_button("Télécharger PDF", data=response.content, file_name=f"resume-sante-{export_days}j.pdf", mime="application/pdf", use_container_width=True)
            except Exception as exc:  # noqa: BLE001
                st.warning(f"Export PDF indisponible: {exc}")



def tab_workspace(backend: BackendClient, workspace_root: Path) -> None:
    st.subheader("Workspace")
    st.caption("Cette vue ajoute l'upload dans `/workspace`, le listing et la lecture locale, puis l'ingestion via l'endpoint backend.")

    c1, c2 = st.columns([1, 1])

    with c1:
        st.markdown("### Upload dans le workspace")
        target_subdir = st.text_input("Sous-dossier cible", value=".")
        uploads = st.file_uploader(
            "Fichiers à copier dans le workspace",
            accept_multiple_files=True,
            type=None,
        )
        if st.button("Copier dans /workspace", use_container_width=True):
            try:
                target_dir = safe_resolve(workspace_root, target_subdir)
                target_dir.mkdir(parents=True, exist_ok=True)
                saved: list[str] = []
                for uploaded in uploads or []:
                    destination = target_dir / uploaded.name
                    destination.write_bytes(uploaded.getbuffer())
                    saved.append(str(destination.relative_to(workspace_root.resolve())))
                st.success(f"{len(saved)} fichier(s) copiés dans le workspace.")
                if saved:
                    st.json(saved)
            except Exception as exc:  # noqa: BLE001
                st.error(str(exc))

        st.markdown("### Ingestion par upload backend")
        ingest_uploads = st.file_uploader(
            "Uploader directement via /api/v1/ingest/files",
            accept_multiple_files=True,
            key="ingest_uploads",
        )
        if st.button("Ingest uploads", use_container_width=True):
            try:
                files = []
                for uploaded in ingest_uploads or []:
                    files.append(("files", (uploaded.name, uploaded.getvalue(), uploaded.type or "application/octet-stream")))
                st.json(read_json_response(backend.post("/api/v1/ingest/files", files=files)))
            except Exception as exc:  # noqa: BLE001
                st.error(str(exc))

        st.markdown("### Ingestion depuis le workspace")
        paths_text = st.text_area(
            "Chemins relatifs à ingérer (1 par ligne)",
            value="",
            height=120,
            placeholder="docs/notes.md\nmanual.pdf",
        )
        if st.button("Ingest workspace paths", use_container_width=True):
            try:
                paths = [line.strip() for line in paths_text.splitlines() if line.strip()]
                st.json(read_json_response(backend.post("/api/v1/ingest/paths", json={"paths": paths})))
            except Exception as exc:  # noqa: BLE001
                st.error(str(exc))

    with c2:
        st.markdown("### Contenu du workspace")
        browse_subdir = st.text_input("Lister à partir de", value=".", key="browse_subdir")
        if st.button("Rafraîchir le listing", use_container_width=True):
            st.session_state["refresh_workspace"] = True

        try:
            base = safe_resolve(workspace_root, browse_subdir)
            if not base.exists():
                st.info("Ce dossier n'existe pas encore.")
            else:
                items: list[dict[str, Any]] = []
                for p in sorted(base.rglob("*")):
                    rel = str(p.relative_to(workspace_root.resolve()))
                    items.append(
                        {
                            "path": rel,
                            "type": "dir" if p.is_dir() else "file",
                            "size": p.stat().st_size if p.is_file() else None,
                        }
                    )
                st.dataframe(items, use_container_width=True, height=380)
        except Exception as exc:  # noqa: BLE001
            st.error(str(exc))

        st.markdown("### Lecture d'un fichier du workspace")
        read_path = st.text_input("Chemin relatif du fichier", value="")
        if st.button("Lire le fichier", use_container_width=True, disabled=not read_path.strip()):
            try:
                path = safe_resolve(workspace_root, read_path.strip())
                if not path.exists() or not path.is_file():
                    raise FileNotFoundError(read_path)
                suffix = path.suffix.lower()
                if suffix in TEXT_PREVIEW_SUFFIXES:
                    st.code(path.read_text(encoding="utf-8", errors="ignore")[:20000])
                else:
                    st.info(f"Prévisualisation texte non supportée pour {suffix or 'ce type de fichier'}.")
                    st.write({"path": str(path), "size": path.stat().st_size})
            except Exception as exc:  # noqa: BLE001
                st.error(str(exc))



def tab_qdrant(qdrant_url: str, default_collection: str) -> None:
    st.subheader("Qdrant")
    client = get_qdrant_client(qdrant_url)

    try:
        collections = client.get_collections().collections
        collection_names = [c.name for c in collections]
    except Exception as exc:  # noqa: BLE001
        st.error(f"Connexion Qdrant impossible: {exc}")
        return

    c1, c2 = st.columns([1, 2])
    with c1:
        st.metric("Nombre de collections", len(collection_names))
        collection = st.selectbox(
            "Collection",
            options=collection_names or [default_collection],
            index=collection_names.index(default_collection) if default_collection in collection_names else 0,
        )
    with c2:
        st.write("Collections détectées")
        st.code("\n".join(collection_names) if collection_names else "Aucune collection")

    if not collection:
        return

    try:
        info = client.get_collection(collection)
        st.markdown("### Informations de collection")
        st.json(info.model_dump() if hasattr(info, "model_dump") else info)
    except Exception as exc:  # noqa: BLE001
        st.warning(f"Impossible de lire les infos de collection: {exc}")

    st.markdown("### Parcourir les points")
    limit = st.slider("Nombre de points", 1, 100, 20, key="qdrant_limit")
    source_filter = st.text_input("Filtrer par source exacte (payload.source)", value="")

    try:
        scroll_filter = None
        if source_filter.strip():
            scroll_filter = qmodels.Filter(
                must=[qmodels.FieldCondition(key="source", match=qmodels.MatchValue(value=source_filter.strip()))]
            )
        points, _ = client.scroll(
            collection_name=collection,
            scroll_filter=scroll_filter,
            with_payload=True,
            with_vectors=False,
            limit=limit,
        )
        rows = []
        for point in points:
            payload = point.payload or {}
            rows.append(
                {
                    "id": str(point.id),
                    "source": payload.get("source"),
                    "chunk_index": payload.get("chunk_index"),
                    "mime_type": payload.get("mime_type"),
                    "text_preview": str(payload.get("text", ""))[:500],
                }
            )
        st.dataframe(rows, use_container_width=True, height=360)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Scroll Qdrant impossible: {exc}")



def tab_sqlite(state_db_path: Path, checkpoint_db_path: Path) -> None:
    st.subheader("SQLite")

    db_choice = st.radio(
        "Base à explorer",
        options=["state", "checkpoint"],
        horizontal=True,
    )
    db_path = state_db_path if db_choice == "state" else checkpoint_db_path

    if not db_path.exists():
        st.warning(f"Base absente: {db_path}")
        return

    st.code(str(db_path))

    try:
        table_names = sqlite_table_names(db_path)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Impossible de lister les tables: {exc}")
        return

    st.markdown("### Tables")
    st.write(table_names)

    if db_choice == "state":
        st.markdown("### Sessions détectées dans runs")
        try:
            cols, rows = sqlite_query(
                db_path,
                """
                SELECT session_id,
                       COUNT(*) AS runs,
                       MIN(created_at) AS first_seen,
                       MAX(updated_at) AS last_seen
                FROM runs
                GROUP BY session_id
                ORDER BY last_seen DESC
                """,
            )
            render_table(cols, rows, height=240)
        except Exception as exc:  # noqa: BLE001
            st.warning(f"Lecture sessions impossible: {exc}")

        st.markdown("### Derniers runs")
        try:
            cols, rows = sqlite_query(
                db_path,
                """
                SELECT run_id, session_id, user_id, model, status, stop_reason, created_at, updated_at
                FROM runs
                ORDER BY created_at DESC
                LIMIT 100
                """,
            )
            render_table(cols, rows, height=320)
        except Exception as exc:  # noqa: BLE001
            st.warning(f"Lecture runs impossible: {exc}")

        run_id = st.text_input("Run ID à inspecter", value="", key="sqlite_run_id")
        if run_id.strip():
            try:
                cols, rows = sqlite_query(
                    db_path,
                    "SELECT * FROM runs WHERE run_id = ?",
                    (run_id.strip(),),
                )
                st.markdown("### Run")
                render_table(cols, rows, height=140)

                cols, rows = sqlite_query(
                    db_path,
                    "SELECT id, node, created_at, payload_json FROM trace_events WHERE run_id = ? ORDER BY id ASC",
                    (run_id.strip(),),
                )
                st.markdown("### Trace events")
                render_table(cols, rows, height=360)
            except Exception as exc:  # noqa: BLE001
                st.warning(f"Inspection run impossible: {exc}")

    st.markdown("### Requête SQL lecture seule")
    default_query = (
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        if db_choice == "checkpoint"
        else "SELECT run_id, session_id, status, created_at FROM runs ORDER BY created_at DESC LIMIT 20"
    )
    query = st.text_area("SQL", value=default_query, height=140)
    if st.button("Exécuter la requête SQL", use_container_width=True):
        normalized = query.strip().lower()
        forbidden = ("insert ", "update ", "delete ", "drop ", "alter ", "replace ", "create ", "attach ")
        if normalized.startswith(forbidden) or any(token in normalized for token in forbidden):
            st.error("Seules les requêtes SELECT/PRAGMA/WITH en lecture sont autorisées dans cette UI.")
        else:
            try:
                cols, rows = sqlite_query(db_path, query)
                render_table(cols, rows, height=360)
            except Exception as exc:  # noqa: BLE001
                st.error(str(exc))



def tab_api_docs() -> None:
    st.subheader("Fonctions couvertes")
    st.markdown(
        """
Cette interface ajoute ce qu'Open WebUI n'expose pas directement dans ton backend actuel :

- `GET /health`
- `GET /v1/models`
- `POST /api/v1/ingest/files`
- `POST /api/v1/ingest/paths`
- `POST /api/v1/rag/search`
- `GET /api/v1/runs`
- `GET /api/v1/runs/{run_id}`
- dashboard Coach santé, exports, alertes, traçabilité et évaluation synthétique
- upload manuel dans `/workspace`
- listing et lecture locale du `workspace`
- exploration directe de Qdrant
- exploration directe des bases SQLite (`app.sqlite` et `langgraph-checkpoints.sqlite`)

Ce qui n'est pas ajouté ici volontairement :

- un chat alternatif à Open WebUI
- l'écriture arbitraire dans Qdrant
- la modification SQL en écriture
- la suppression de fichiers
"""
    )



def main() -> None:
    init_state()
    backend, workspace_root, _data_dir, state_db_path, checkpoint_db_path, qdrant_collection = sidebar()

    st.title("🧠 Local Agentic Stack Admin")
    st.caption("UI Streamlit d'administration pour le backend FastAPI agentique")

    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(
        [
            "Vue d'ensemble",
            "Coach santé",
            "Endpoints backend",
            "Workspace & ingestion",
            "Qdrant",
            "SQLite",
            "Périmètre",
        ]
    )

    with tab1:
        tab_overview(backend, workspace_root, state_db_path, checkpoint_db_path)
    with tab2:
        tab_health_coach(backend)
    with tab3:
        tab_endpoints(backend)
    with tab4:
        tab_workspace(backend, workspace_root)
    with tab5:
        tab_qdrant(st.session_state.qdrant_url, qdrant_collection)
    with tab6:
        tab_sqlite(state_db_path, checkpoint_db_path)
    with tab7:
        tab_api_docs()


if __name__ == "__main__":
    main()
