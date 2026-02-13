import streamlit as st 
from PIL import Image
from datetime import datetime 
import json 
from streamlit_image_coordinates import streamlit_image_coordinates 
from utils.processing import process_pain_map
from utils.minio_requests import upload_manual_file
from utils.pain_map_utils import draw_markers_on_image, load_font, assign_zone

st.set_page_config(page_title="Pain Map — Affichage immédiat", layout="centered") 
st.title("Carte de douleur") 
st.write("Cliquez sur la silhouette pour ajouter des points de douleur.") 

# ----- Config ----- 
IMAGE_PATH = "/app/pages/images/body.png" 
MAX_DISPLAY_HEIGHT = 900 
MARKER_RADIUS_PX = 8 
LABEL_OFFSET_PX = 10 
FONT_SIZE = 14 
DEFAULT_ZONE_LIST = [ 
                     "Tête", "Cou", "Épaule gauche", "Épaule droite", "Poitrine", "Abdomen", 
                     "Haut du dos", "Bas du dos", "Bras gauche (sup)", "Bras droit (sup)", 
                     "Avant-bras gauche", "Avant-bras droit", "Main gauche", "Main droite", 
                     "Hanche gauche", "Hanche droite", "Cuisse gauche", "Cuisse droite", 
                     "Genou gauche", "Genou droit", "Tibia gauche", "Tibia droit", 
                     "Pied gauche", "Pied droit", "Tête (arrière)", "Cervicales", 
                     "Épaule gauche (arrière)", "Épaule droite (arrière)",
                     "Bras gauche (arrière)", "Bras droit (arrière)", 
                     "Bras gauche (arrière)", "Bras droit (arrière)",
                     "Avant-bras gauche (arrière)", "Avant-bras droit (arrière)",
                     "Main gauche (arrière)", "Main droite (arrière)",
                     "Fesse gauche", "Fesse droite", "Cuisse gauche (arrière)", 
                     "Cuisse droite (arrière)", "Mollet gauche", "Mollet droit",
                     "Pied gauche (dessous)", "Pied droit (dessous)"] 


# ----- Session State -----
if "confirmed_markers" not in st.session_state:
    st.session_state.confirmed_markers = []
if "pending_markers" not in st.session_state:
    st.session_state.pending_markers = []
if "next_id" not in st.session_state:
    st.session_state.next_id = 1
if "last_click" not in st.session_state:
    st.session_state.last_click = None

# ----- Load Image -----
try:
    pil_img = Image.open(IMAGE_PATH).convert("RGBA")
    w, h = pil_img.size
    if h > MAX_DISPLAY_HEIGHT:
        scale = MAX_DISPLAY_HEIGHT / h
        pil_img = pil_img.resize((int(w*scale), int(h*scale)))
except Exception as e:
    st.error(f"Erreur chargement image : {e}")
    pil_img = None

# ----- Display Image + Handle Clicks -----
font = load_font(FONT_SIZE)
annotated_img = draw_markers_on_image(pil_img, st.session_state.confirmed_markers, st.session_state.pending_markers, font=font)

# Utiliser un bouton pour valider le clic (évite les rafraîchissements intempestifs)
click_container = st.empty()
coords = streamlit_image_coordinates(annotated_img, key="img_coords")

if coords and st.session_state.last_click != coords:
    st.session_state.last_click = coords
    rel_x = coords.get("relative_x", coords.get("x", 0) / w if w else 0)
    rel_y = coords.get("relative_y", coords.get("y", 0) / h if h else 0)
    rel_x, rel_y = round(float(rel_x), 4), round(float(rel_y), 4)
    zone = assign_zone(rel_x, rel_y)
    st.session_state.pending_markers.append({
        "id": st.session_state.next_id,
        "x_norm": rel_x,
        "y_norm": rel_y,
        "zone": zone,
        "intensity": 5,
        "note": "",
        "created_at": datetime.utcnow().isoformat() + "Z",
    })
    st.session_state.next_id += 1
    st.rerun()  # Rafraîchir UNIQUEMENT après un nouveau clic

# ----- Confirm/Cancel Pending Markers -----
if st.session_state.pending_markers:
    st.subheader(f"{len(st.session_state.pending_markers)} point(s) temporaire(s)")
    for i, m in enumerate(st.session_state.pending_markers):
        #st.write(f"Point {m['id']} : {m.get('zone', 'Zone inconnue')} (x={m['x_norm']}, y={m['y_norm']})")
        cols = st.columns([3,1,1])
        zone_choice = cols[0].selectbox(f"Zone {m['id']}", options=DEFAULT_ZONE_LIST, index=DEFAULT_ZONE_LIST.index(m["zone"]) if m["zone"] in DEFAULT_ZONE_LIST else 0, key=f"zone_{m['id']}")
        intensity = cols[1].slider(f"Intensité", 0, 10, value=5, key=f"intensity_{m['id']}")
        if cols[2].button(f"Confirmer", key=f"confirm_{m['id']}"):
            m.update({"zone": zone_choice, "intensity": intensity})
            st.session_state.confirmed_markers.append(m)
            st.session_state.pending_markers.remove(m)
            st.rerun()  # Rafraîchir après confirmation

    if st.button("Annuler tous les points temporaires"):
        st.session_state.pending_markers = []
        st.rerun()  # Rafraîchir après annulation

# ----- Display Confirmed Markers -----
st.subheader("Marqueurs confirmés")
if not st.session_state.confirmed_markers:
    st.info("Aucun marqueur confirmé.")
else:
    for i, m in enumerate(st.session_state.confirmed_markers):
        with st.expander(f"#{m['id']} — {m.get('zone')} (Intensité: {m.get('intensity')})"):
            cols = st.columns([2,1,1])
            zone = cols[0].selectbox("Zone", options=DEFAULT_ZONE_LIST, index=DEFAULT_ZONE_LIST.index(m["zone"]), key=f"edit_zone_{m['id']}")
            intensity = cols[1].slider("Intensité", 0, 10, value=m.get("intensity", 5), key=f"edit_intensity_{m['id']}")
            note = cols[2].text_input("Note", value=m.get("note", ""), key=f"edit_note_{m['id']}")
            st.session_state.confirmed_markers[i].update({"zone": zone, "intensity": intensity, "note": note})
            if st.button(f"Supprimer {m['id']}", key=f"delete_{m['id']}"):
                st.session_state.confirmed_markers.remove(m)
                st.rerun()  # Rafraîchir après suppression

# ----- Export JSON -----
if st.session_state.confirmed_markers:
    pains = [{
        "zone": m.get("zone"),
        "intensity": m.get("intensity"),
        "note": m.get("note", ""),
        "date": m.get("created_at")
    } for m in st.session_state.confirmed_markers]
    
    payload = process_pain_map(pains)
    if st.button("Exporter JSON ✅"):
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

st.markdown("---")
st.caption("Copyright - PHYLCERO©")