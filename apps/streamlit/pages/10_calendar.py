import streamlit as st
from libs.google_auth import init_auth, logout
from libs.calendar_service import (
    sync_events_from_google,
    create_event,
    update_event,
    remove_event,
    get_events_for_calendar,
)
from libs.db_service import init_db, get_event_by_google_id
from streamlit_calendar import calendar
from datetime import datetime
import pytz

PARIS_TZ = pytz.timezone("Europe/Paris")

# Configuration
st.set_page_config(
    page_title="Google Calendar App",
    page_icon="📅",
    layout="wide",
)

# Init DB
init_db()

# Authentication
if not init_auth():
    st.stop()

# Header
col1, col2 = st.columns([8, 1])
with col1:
    st.title("📅 Mon Google Calendar")
with col2:
    if st.button("🚪 Déconnexion"):
        logout()

# Synchronisation
with st.spinner("Synchronisation avec Google Calendar..."):
    if "synced" not in st.session_state:
        count = sync_events_from_google()
        st.session_state["synced"] = True
        st.success(f"{count} événements synchronisés !")

if st.button("🔄 Synchroniser"):
    count = sync_events_from_google()
    st.success(f"{count} événements synchronisés !")
    st.rerun()

# Calendar
st.markdown("## 📆 Calendrier")

calendar_options = {
    "initialView": "dayGridMonth",
    "headerToolbar": {
        "left": "prev,next today",
        "center": "title",
        "right": "dayGridMonth,timeGridWeek,timeGridDay",
    },
    "editable": False,
    "selectable": True,
    "locale": "fr",
}

events = get_events_for_calendar()

calendar_result = calendar(
    events=events,
    options=calendar_options,
    key="main_calendar",
)

selected_event_id = None

if calendar_result.get("eventClick"):
    selected_event_id = calendar_result["eventClick"]["event"]["id"]
    st.session_state["selected_event_id"] = selected_event_id

if calendar_result.get("select"):
    selected_start = calendar_result["select"]["start"]
    selected_end = calendar_result["select"]["end"]
    st.session_state["new_event_start"] = selected_start
    st.session_state["new_event_end"] = selected_end
    st.session_state["show_create_form"] = True

# Create Event
if st.session_state.get("show_create_form"):
    st.markdown("## ➕ Créer un événement")

    with st.form("create_form"):
        title = st.text_input("Titre", value="")
        description = st.text_area("Description", value="")

        start_default = datetime.fromisoformat(
            st.session_state.get("new_event_start", datetime.now().isoformat())
        ).replace(tzinfo=None)
        end_default = datetime.fromisoformat(
            st.session_state.get("new_event_end", datetime.now().isoformat())
        ).replace(tzinfo=None)

        start_date = st.date_input("Date de début", value=start_default.date())
        start_time = st.time_input("Heure de début", value=start_default.time())
        end_date = st.date_input("Date de fin", value=end_default.date())
        end_time = st.time_input("Heure de fin", value=end_default.time())

        submitted = st.form_submit_button("✅ Créer")
        cancelled = st.form_submit_button("❌ Annuler")

        if submitted:
            start_dt = PARIS_TZ.localize(datetime.combine(start_date, start_time))
            end_dt = PARIS_TZ.localize(datetime.combine(end_date, end_time))
            create_event(title, description, start_dt, end_dt)
            st.session_state["show_create_form"] = False
            st.success("Événement créé !")
            st.rerun()

        if cancelled:
            st.session_state["show_create_form"] = False
            st.rerun()

# Event Editor
if st.session_state.get("selected_event_id"):
    event_id = st.session_state["selected_event_id"]
    event = get_event_by_google_id(event_id)

    if event:
        st.markdown("## ✏️ Modifier / Supprimer un événement")

        with st.form("edit_form"):
            title = st.text_input("Titre", value=event["title"])
            description = st.text_area("Description", value=event["description"] or "")

            start_dt = event["start_datetime"].astimezone(PARIS_TZ)
            end_dt = event["end_datetime"].astimezone(PARIS_TZ)

            start_date = st.date_input("Date de début", value=start_dt.date())
            start_time = st.time_input("Heure de début", value=start_dt.time())
            end_date = st.date_input("Date de fin", value=end_dt.date())
            end_time = st.time_input("Heure de fin", value=end_dt.time())

            col1, col2, col3 = st.columns(3)
            with col1:
                update_btn = st.form_submit_button("💾 Mettre à jour")
            with col2:
                delete_btn = st.form_submit_button("🗑️ Supprimer")
            with col3:
                cancel_btn = st.form_submit_button("❌ Annuler")

            if update_btn:
                new_start = PARIS_TZ.localize(datetime.combine(start_date, start_time))
                new_end = PARIS_TZ.localize(datetime.combine(end_date, end_time))
                update_event(event_id, title, description, new_start, new_end)
                st.session_state["selected_event_id"] = None
                st.success("Événement mis à jour !")
                st.rerun()

            if delete_btn:
                remove_event(event_id)
                st.session_state["selected_event_id"] = None
                st.success("Événement supprimé !")
                st.rerun()

            if cancel_btn:
                st.session_state["selected_event_id"] = None
                st.rerun()
