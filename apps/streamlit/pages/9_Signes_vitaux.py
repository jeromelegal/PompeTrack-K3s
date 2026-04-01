import streamlit as st
from datetime import date
import json
from utils.minio_requests import upload_manual_file
from utils.processing import process_weekly_data

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

st.markdown(
    """
    <div style="display:flex;align-items:center;gap:18px">
      <img src="https://images.unsplash.com/photo-1526256262350-7da7584cf5eb?auto=format&fit=crop&w=1200&q=60"
           style="height:72px;border-radius:12px;object-fit:cover"/>
      <div>
        <h2 style="margin:0">Tableau de saisie — Suivi santé</h2>
        <div class="muted"> • Entrées hebdomadaires • </div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

def save_weekly(data: dict):
    """Sauvegarde hebdo : envoi vers minio avec upload_file."""
    st.success("Envoi données hebdomadaires vers Minio. ✅")
    st.json(data)
    bytes_data = json.dumps(data, default=str, ensure_ascii=False).encode("utf-8")
    
    result = upload_manual_file(bytes_data)
    st.success(f"Envoi Minio : {result}")
    
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown("<div class='section-title'>📅 Données hebdomadaires</div>", unsafe_allow_html=True)
st.markdown("<div class='muted'>Remplir les mesures prises cette semaine</div>", unsafe_allow_html=True)
st.write("")


with st.form("form_weekly"):
    date_week = st.date_input("Date de la mesure 📆", value=date.today())
    weight = st.number_input("Poids (kg) ⚖️", min_value=20.0, max_value=300.0, value=75.0, step=0.1, format="%.1f")
    
    col_bp1, col_bp2 = st.columns(2)
    with col_bp1:
        heart_rate = st.number_input("Fréquence cardiaque (bpm) ❤️", min_value=20, max_value=220, value=70, step=1)
        oxymetry = st.number_input("Oxymétrie (%) ", min_value=0, max_value=100, value=95, step=1)
    with col_bp2:
        systolic = st.number_input("Tension systolique (mmHg) 🩺", min_value=60, max_value=250, value=120, step=1)
        diastolic = st.number_input("Tension diastolique (mmHg) 🩺", min_value=30, max_value=150, value=80, step=1)
    symptoms = st.text_area("Journal de symptômes 📝", placeholder="Décris ici l'évolution, les triggers, médicaments pris, etc.", height=120)

    st.write("")
    submitted_weekly = st.form_submit_button("Valider les données hebdo ✅")

if submitted_weekly:
    weekly_payload = process_weekly_data(
        weight=weight,
        heart_rate=heart_rate,
        oxymetry=oxymetry,
        systolic=systolic,
        diastolic=diastolic,
        symptoms=symptoms,
    )

    save_weekly(weekly_payload)

st.markdown('</div>', unsafe_allow_html=True)