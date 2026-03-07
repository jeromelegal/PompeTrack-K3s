from googleapiclient.discovery import build
from libs.google_auth import get_credentials
from libs.db_service import upsert_event, delete_event, get_all_events
from datetime import datetime, timezone
import pytz


def get_calendar_service():
    """Retourne le service Google Calendar."""
    creds = get_credentials()
    return build("calendar", "v3", credentials=creds)


def sync_events_from_google():
    """
    Récupère les événements Google Calendar (30 jours passés / 90 jours futurs)
    et les synchronise dans la base de données.
    """
    service = get_calendar_service()

    now = datetime.now(timezone.utc)
    time_min = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    time_min = time_min.replace(day=max(1, now.day - 30))
    time_max = time_min.replace(day=now.day + 90) if now.day + 90 <= 28 else now.replace(month=now.month + 3)

    # Appel API Google Calendar
    events_result = service.events().list(
        calendarId="primary",
        timeMin=time_min.isoformat(),
        timeMax=time_max.isoformat(),
        maxResults=500,
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    google_events = events_result.get("items", [])

    for event in google_events:
        google_event_id = event["id"]
        title = event.get("summary", "Sans titre")
        description = event.get("description", "")

        # Gestion des événements full-day vs datetime
        start = event["start"].get("dateTime", event["start"].get("date"))
        end = event["end"].get("dateTime", event["end"].get("date"))

        start_dt = parse_datetime(start)
        end_dt = parse_datetime(end)

        upsert_event(google_event_id, title, description, start_dt, end_dt)

    return len(google_events)


def create_event(title, description, start_dt, end_dt):
    """Crée un événement dans Google Calendar et le synchronise en DB."""
    service = get_calendar_service()

    event_body = {
        "summary": title,
        "description": description,
        "start": {"dateTime": start_dt.isoformat(), "timeZone": "Europe/Paris"},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": "Europe/Paris"},
    }

    created_event = service.events().insert(
        calendarId="primary",
        body=event_body,
    ).execute()

    upsert_event(
        created_event["id"],
        title,
        description,
        start_dt,
        end_dt,
    )

    return created_event["id"]


def update_event(google_event_id, title, description, start_dt, end_dt):
    """Met à jour un événement dans Google Calendar et en DB."""
    service = get_calendar_service()

    event_body = {
        "summary": title,
        "description": description,
        "start": {"dateTime": start_dt.isoformat(), "timeZone": "Europe/Paris"},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": "Europe/Paris"},
    }

    service.events().update(
        calendarId="primary",
        eventId=google_event_id,
        body=event_body,
    ).execute()

    upsert_event(google_event_id, title, description, start_dt, end_dt)


def remove_event(google_event_id):
    """Supprime un événement dans Google Calendar et en DB."""
    service = get_calendar_service()

    service.events().delete(
        calendarId="primary",
        eventId=google_event_id,
    ).execute()

    delete_event(google_event_id)


def get_events_for_calendar():
    """
    Retourne les événements formatés pour streamlit-calendar.
    """
    events = get_all_events()
    calendar_events = []

    for event in events:
        calendar_events.append({
            "id": event["google_event_id"],
            "title": event["title"],
            "start": event["start_datetime"].isoformat(),
            "end": event["end_datetime"].isoformat(),
            "description": event["description"] or "",
        })

    return calendar_events


def parse_datetime(dt_str):
    """Parse une date ou datetime en objet datetime avec timezone."""
    if "T" in dt_str:
        dt = datetime.fromisoformat(dt_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    else:
        # Événement full-day : on met minuit UTC
        dt = datetime.strptime(dt_str, "%Y-%m-%d")
        return dt.replace(tzinfo=timezone.utc)
