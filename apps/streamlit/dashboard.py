import streamlit as st
import json
import requests
from utils.common import is_admin
from libs.minio_requests import upload_iphone_json, upload_object_into_bucket

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
c1, c2 = st.columns(2)

st.info("Sélectionne une page dans le menu à gauche pour commencer.")

st.markdown("---")
st.subheader("Ingestion des données :")

b1, b2, b3 = st.columns(3)

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
        if st.button("Envoyer JSON"):
            try:
                r = upload_iphone_json(uploaded_iphone)
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
        if st.button("Envoyer CSV"):
            try:
                csv_text = uploaded_spirometer.getvalue().decode("utf-8")
                r = upload_object_into_bucket(file_path=csv_text, bucket="raw-spirometer")
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
        if st.button("Envoyer DB"):
            try:
                r = upload_object_into_bucket(file_path=uploaded_sqlite, bucket="raw-db-spirometer")
            except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as e:
                st.error(str(e))
            except requests.RequestException as e:
                st.error(f"Erreur réseau: {e}")
            else:
                show_response(r)

    
st.markdown("---")
st.caption("Copyright - PHYLCERO©")