import streamlit as st
from datetime import date
import json
from utils.minio_requests import upload_manual_file
from utils.processing import process_weekly_data, process_monthly_data

# ----- Styles (simple card look) -----
st.markdown(
    """
    <style>
    .card {
        background: linear-gradient(180deg, rgba(255,255,255,0.95), rgba(250,250,250,0.95));
        padding: 18px;
        border-radius: 12px;
        box-shadow: 0 6px 20px rgba(0,0,0,0.06);
        border: 1px solid rgba(0,0,0,0.06);
    }
    .section-title {
        font-size: 18px;
        font-weight: 700;
    }
    .muted {
        color: #6c757d;
        font-size: 13px;
    }
    .small {
        font-size: 13px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ----- Header -----
st.markdown(
    """
    <div style="display:flex;align-items:center;gap:18px">
      <img src="https://images.unsplash.com/photo-1526256262350-7da7584cf5eb?auto=format&fit=crop&w=1200&q=60"
           style="height:72px;border-radius:12px;object-fit:cover"/>
      <div>
        <h2 style="margin:0">Tableau de saisie — Suivi santé</h2>
        <div class="muted"> • Entrées mensuelles • </div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.write("")  # petit espacement

# --- Helper stubs (à remplacer par tes fonctions réelles) ---
def save_weekly(data: dict):
    """Sauvegarde hebdo : envoi vers minio avec upload_file."""
    st.success("Envoi données hebdomadaires vers Minio. ✅")
    st.json(data)
    bytes_data = json.dumps(data, default=str, ensure_ascii=False).encode("utf-8")
    
    result = upload_manual_file(bytes_data)
    st.success(f"Envoi Minio : {result}")
    
def save_monthly(data: dict):
    """Sauvegarde mensuelle : envoi vers minio avec upload_file."""
    st.success("Envoi données mensuelles vers Minio). ✅")
    st.json(data)
    bytes_data = json.dumps(data, default=str, ensure_ascii=False).encode("utf-8")
    
    result = upload_manual_file(bytes_data)
    st.success(f"Envoi Minio : {result}")



# ------------------------
# Colonne DROITE : Mensuel
# ------------------------

st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown("<div class='section-title'>📏 Données mensuelles</div>", unsafe_allow_html=True)
st.markdown("<div class='muted'>Mesures en cm : jambes, tour de taille, hanches, cou</div>", unsafe_allow_html=True)
st.write("")

with st.form("form_monthly"):
    date_month = st.date_input("Date de la mesure mensuelle 📆", value=date.today())
    col_legs = st.columns(2)
    with col_legs[0]:
        calf_left = st.number_input("Mollet gauche (cm) 🦵 L", min_value=10.0, max_value=150.0, value=35.0, step=0.1, format="%.1f")
        thigh_left = st.number_input("Cuisse gauche (cm) 🦵 L", min_value=10.0, max_value=200.0, value=55.0, step=0.1, format="%.1f")
    with col_legs[1]:
        calf_right = st.number_input("Mollet droit (cm) 🦵 R", min_value=10.0, max_value=150.0, value=35.0, step=0.1, format="%.1f")
        thigh_right = st.number_input("Cuisse droite (cm) 🦵 R", min_value=10.0, max_value=200.0, value=55.0, step=0.1, format="%.1f")

    col_core = st.columns(2)
    with col_core[0]:
        waist = st.number_input("Tour de taille (cm) ⚖️", min_value=30.0, max_value=200.0, value=85.0, step=0.1, format="%.1f")
        hips = st.number_input("Hanches (cm) 🍑", min_value=30.0, max_value=250.0, value=95.0, step=0.1, format="%.1f")
    with col_core[1]:
        neck = st.number_input("Cou (cm) 👤", min_value=20.0, max_value=60.0, value=38.0, step=0.1, format="%.1f")

    comments = st.text_area("Commentaire (optionnel) 🗒️", placeholder="Ex : changements liés à rééducation, chirurgie, compression...", height=120)

    st.write("")
    submitted_monthly = st.form_submit_button("Valider les données mensuelles 📥")

if submitted_monthly:
    monthly_payload = process_monthly_data(
        calf_left=calf_left,
        calf_right=calf_right,
        thigh_left=thigh_left,
        thigh_right=thigh_right,
        waist=waist,
        hips=hips,
        neck=neck,
        comments=comments,
    )
    save_monthly(monthly_payload)

st.markdown('</div>', unsafe_allow_html=True)  # fin card

st.markdown("---")
st.caption("Copyright - PHYLCERO©")
