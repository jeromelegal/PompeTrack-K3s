import streamlit as st
import json
import requests
import pandas as pd
import os
from utils.common import is_admin, load_data, DEFAULT_LOOKBACK_DAYS

INGEST_BASE_URL = "http://ingestion/"
TOKEN = os.getenv("TOKEN", "token")

ENDPOINTS = {
    "iphone": {
        "url": "http://ingestion/ingest/iphone",
        "type": ["json"],
        "kind": "json_dict",
    },
    "spirometer": {
        "url": "http://ingestion/ingest/spirometer",
        "type": ["csv"],
        "kind": "csv_bytes",
    },
    "sqlite": {
    "url": "http://ingestion/ingest/sqlite",
    "type": ["db"],
    "kind": "file_multipart",
    },
}

st.set_page_config("Dashboard Santé", layout="wide")

# =========================
# ADMIN LOGIN
# =========================
st.sidebar.title("Accès")

if not is_admin():
    pwd = st.sidebar.text_input("Mot de passe ADMIN", type="password")
    if pwd == "admin123":
        st.session_state.admin = True
        st.success("Mode ADMIN activé")
        st.rerun()
else:
    st.sidebar.success("ADMIN activé")
    if st.sidebar.button("Désactiver ADMIN"):
        st.session_state.admin = False
        st.rerun()

# =========================
# PAGE CONTENT
# =========================
st.title("📊 Dashboard Santé")

st.markdown("""
Ce tableau de bord permet de visualiser :
- métriques iPhone
- workouts et état d’esprit
- spirométrie
- mesures manuelles

Les données sont chargées **uniquement à l’ouverture des pages**.
""")

# =========================
# SUMMARY
# =========================
st.subheader("Résumé rapide")

use_mock = is_admin()

# metrics = load_data("spirometer", DEFAULT_LOOKBACK_DAYS, use_mock)
# som = load_data("stateofminds", DEFAULT_LOOKBACK_DAYS, use_mock)

c1, c2 = st.columns(2)

# if metrics is not None:
#     c1.metric(
#         "Dernière activité",
#         metrics["timestamp"].max().date()
#     )

# if som is not None:
#     c2.metric(
#         "Humeur moyenne",
#         f"{som['mood_score'].mean():.2f} / 10"
#     )

st.info("Sélectionne une page dans le menu à gauche pour commencer.")

st.markdown("---")
st.subheader("Ingestion des données :")

b1, b2, b3 = st.columns(3)

def post_to_ingestion(kind: str, url: str, token: str, uploaded_file) -> requests.Response:
    """
    kind:
      - 'json_dict'  -> envoie JSON (dict) avec requests.post(json=...)
      - 'csv_bytes'  -> envoie fichier CSV brut (multipart/form-data) OU texte brut (voir ci-dessous)
    """
    headers_auth = {"Authorization": f"Bearer {token}"}

    if kind == "json_dict":
        raw = uploaded_file.getvalue()
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Le JSON doit être un objet (racine = { ... }).")

        headers = {**headers_auth, "Accept": "application/json"}
        return requests.post(url, json=payload, headers=headers, timeout=30)

    if kind == "csv_bytes":
        csv_text = uploaded_file.getvalue().decode("utf-8")
        headers = {**headers_auth, "Content-Type": "text/csv", "Accept": "application/json"}
        return requests.post(url, data=csv_text.encode("utf-8"), headers=headers, timeout=60)
    
    if kind == "file_multipart":
        files = {
            "file": (uploaded_file.name, uploaded_file.getvalue(), "application/octet-stream")
        }
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        return requests.post(url, files=files, headers=headers, timeout=120)
    raise ValueError(f"kind inconnu: {kind}")

def show_response(r: requests.Response):
    st.write("Status:", r.status_code)
    ct = (r.headers.get("content-type") or "").lower()
    if "application/json" in ct:
        try:
            st.json(r.json())
        except ValueError:
            st.write(r.text)
    else:
        st.write(r.text)
    if r.ok:
        st.success("Ingestion OK ✅")
    else:
        st.error("Ingestion KO ❌")

with b1:
    uploaded_iphone = st.file_uploader("Fichier JSON iPhone", type=["json"], accept_multiple_files=False)
    if uploaded_iphone is not None:
        st.info(f"Fichier: {uploaded_iphone.name} ({uploaded_iphone.size} bytes)")
        cfg = ENDPOINTS["iphone"]
        if st.button("Envoyer JSON"):
            try:
                r = post_to_ingestion(cfg["kind"], cfg["url"], TOKEN, uploaded_iphone)
            except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as e:
                st.error(str(e))
            except requests.RequestException as e:
                st.error(f"Erreur réseau: {e}")
            else:
                show_response(r)

with b2:
    uploaded_spirometer = st.file_uploader("Fichier CSV Spirometer", type=["csv"], accept_multiple_files=False)
    if uploaded_spirometer is not None:
        st.info(f"Fichier: {uploaded_spirometer.name} ({uploaded_spirometer.size} bytes)")
        cfg = ENDPOINTS["spirometer"]
        if st.button("Envoyer CSV"):
            try:
                r = post_to_ingestion(cfg["kind"], cfg["url"], TOKEN, uploaded_spirometer)
            except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as e:
                st.error(str(e))
            except requests.RequestException as e:
                st.error(f"Erreur réseau: {e}")
            else:
                show_response(r)
                
with b3:
    uploaded_sqlite = st.file_uploader("Fichier DB Sqlite", type=["db"], accept_multiple_files=False)
    if uploaded_sqlite is not None:
        st.info(f"Fichier: {uploaded_sqlite.name} ({uploaded_sqlite.size} bytes)")
        cfg = ENDPOINTS["sqlite"]
        if st.button("Envoyer DB"):
            try:
                r = post_to_ingestion(cfg["kind"], cfg["url"], TOKEN, uploaded_sqlite)
            except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as e:
                st.error(str(e))
            except requests.RequestException as e:
                st.error(f"Erreur réseau: {e}")
            else:
                show_response(r)

    
st.markdown("---")
st.caption("Copyright - PHYLCERO©")