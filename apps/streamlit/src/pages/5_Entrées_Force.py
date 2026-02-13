import streamlit as st
from datetime import datetime, date
import json
from utils.minio_requests import upload_manual_file
from utils.processing import process_force_data
from utils.strength_utils import compute_trials_stats, safe_float, flag_asymmetry, interpret_fatigue

st.set_page_config(page_title="Enregistrement Force", layout="wide", initial_sidebar_state="expanded")

# --- Styles légers ---
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
    .center {
        display:flex;
        justify-content:center;
        align-items:center;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown("<div style='display:flex;align-items:center;gap:14px'><h2 style='margin:0'>Saisie — Force musculaire</h2></div>", unsafe_allow_html=True)
st.write("Enregistre tes mesures au dynamomètre. Trois essais par côté, on calcule max/moy/fatigue index et on envoie le JSON sur Minio.")

# --- Layout : deux colonnes équilibrées ---
st.markdown('<div class="card">', unsafe_allow_html=True)
col_left, col_right = st.columns(2)

with col_left:
    st.markdown("<div class='section-title'>🦵 Quadriceps (jambe)</div>", unsafe_allow_html=True)
    st.markdown("<div class='muted'>Saisir 3 essais pour chaque côté (en kgf ou unité du dynamomètre)</div>", unsafe_allow_html=True)
    # Mode (push/pull) pour quadriceps
    q_mode = st.selectbox("Mode Quadriceps", options=["Pousser (push)", "Tirer (pull)"], index=0, key="q_mode")
    st.markdown("**Quadriceps Gauche**")
    ql1 = st.number_input("Essai 1 (QG)", min_value=0.0, max_value=2000.0, value=0.0, step=0.1, format="%.1f", key="ql1")
    ql2 = st.number_input("Essai 2 (QG)", min_value=0.0, max_value=2000.0, value=0.0, step=0.1, format="%.1f", key="ql2")
    ql3 = st.number_input("Essai 3 (QG)", min_value=0.0, max_value=2000.0, value=0.0, step=0.1, format="%.1f", key="ql3")
    st.write("")  # espace
    st.markdown("**Quadriceps Droite**")
    qr1 = st.number_input("Essai 1 (QD)", min_value=0.0, max_value=2000.0, value=0.0, step=0.1, format="%.1f", key="qr1")
    qr2 = st.number_input("Essai 2 (QD)", min_value=0.0, max_value=2000.0, value=0.0, step=0.1, format="%.1f", key="qr2")
    qr3 = st.number_input("Essai 3 (QD)", min_value=0.0, max_value=2000.0, value=0.0, step=0.1, format="%.1f", key="qr3")

with col_right:
    st.markdown("<div class='section-title'>✋ Poigne (grip)</div>", unsafe_allow_html=True)
    st.markdown("<div class='muted'>Saisir 3 essais pour chaque côté (en kgf ou unité du dynamomètre)</div>", unsafe_allow_html=True)
    # Mode pour poigne (habituellement traction)
    g_mode = st.selectbox("Mode Poigne", options=["Pousser (push)", "Tirer (pull)"], index=1, key="g_mode")
    st.markdown("**Poigne Gauche**")
    gl1 = st.number_input("Essai 1 (PG)", min_value=0.0, max_value=1000.0, value=0.0, step=0.1, format="%.1f", key="gl1")
    gl2 = st.number_input("Essai 2 (PG)", min_value=0.0, max_value=1000.0, value=0.0, step=0.1, format="%.1f", key="gl2")
    gl3 = st.number_input("Essai 3 (PG)", min_value=0.0, max_value=1000.0, value=0.0, step=0.1, format="%.1f", key="gl3")
    st.write("")  # espace
    st.markdown("**Poigne Droite**")
    gr1 = st.number_input("Essai 1 (PD)", min_value=0.0, max_value=1000.0, value=0.0, step=0.1, format="%.1f", key="gr1")
    gr2 = st.number_input("Essai 2 (PD)", min_value=0.0, max_value=1000.0, value=0.0, step=0.1, format="%.1f", key="gr2")
    gr3 = st.number_input("Essai 3 (PD)", min_value=0.0, max_value=1000.0, value=0.0, step=0.1, format="%.1f", key="gr3")

st.markdown("---")

# Meta et soumission (centré)
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown("<div class='section-title'>🔖 Métadonnées & Enregistrement</div>", unsafe_allow_html=True)
st.write("Date et heure de la session — l'heure est obligatoire et toujours enregistrée.")
with st.form("submit_form", clear_on_submit=False):
    measurement_date = st.date_input("Date de la mesure", value=date.today())
    # L'heure n'est plus optionnelle : on force un time_input et on l'enregistre toujours.
    measurement_time = st.time_input("Heure de la mesure (HH:MM)", value=datetime.now().time().replace(microsecond=0))
    operator = st.text_input("Opérateur / Observateur (optionnel)", placeholder="Ex: Moi, ou Nom du kiné")
    rpe = st.slider("RPE (échelle d'effort perçu, 0-10)", min_value=0, max_value=10, value=4)
    strength_notes = st.text_area("Commentaires / conditions (ex: fatigé, médicament, matin/après-midi, protocole modifié)", height=120)
    st.write("")  # espace
    submitted = st.form_submit_button("Enregistrer la mesure ✅")

if submitted:
    # Normaliser les essais : considérer 0.0 comme non-saisi -> None (si tu préfères garder 0, adapte ici)
    ql_trials = [safe_float(v) if v != 0 else None for v in (ql1, ql2, ql3)]
    qr_trials = [safe_float(v) if v != 0 else None for v in (qr1, qr2, qr3)]
    gl_trials = [safe_float(v) if v != 0 else None for v in (gl1, gl2, gl3)]
    gr_trials = [safe_float(v) if v != 0 else None for v in (gr1, gr2, gr3)]

    ql_stats = compute_trials_stats(ql_trials)
    qr_stats = compute_trials_stats(qr_trials)
    gl_stats = compute_trials_stats(gl_trials)
    gr_stats = compute_trials_stats(gr_trials)

    # asymétrie
    q_ratio, q_flag, q_msg = flag_asymmetry(ql_stats['max'], qr_stats['max'])
    g_ratio, g_flag, g_msg = flag_asymmetry(gl_stats['max'], gr_stats['max'])

    # payload JSON
    measures = (
        f"Infos détaillées :\n"
        f"Quadriceps gauche : {ql_trials}, {ql_stats}\n"
        f"Quadriceps droits : {qr_trials}, {qr_stats}\n"
        f"Assymétrie quadriceps : {q_msg}\n"
        f"Grip gauche : {gl_trials}, {gl_stats}\n"
        f"Grip droit : {gr_trials}, {gr_stats}\n"
        f"Assymétrie poigne : {g_msg}\n"
    )
    
    payload = process_force_data(
            quadriceps_left=ql_stats["mean"],
            quadriceps_right=qr_stats["mean"],
            grip_right=gr_stats["mean"],
            grip_left=gl_stats["mean"],
            rpe=int(rpe),
            strength_notes=strength_notes + "\n" + measures,
        )

    # Upload vers Minio
    try:
        bytes_data = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        result = upload_manual_file(bytes_data)
        st.success("Mesure enregistrée et envoyée. ✅")
        st.json(payload)
        st.success(f"Minio response: {result}")
    except Exception as e:
        st.error(f"Erreur lors de l'envoi : {e}")
        st.json(payload)

st.markdown('</div>', unsafe_allow_html=True)

    
st.markdown("---")
st.caption("Copyright - PHYLCERO©")