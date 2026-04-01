from googleapiclient.discovery import build
from libs.google_auth import get_credentials
from libs.db_service import upsert_event, delete_event, get_all_events
from datetime import datetime, timezone, timedelta
import pytz

# Function to get the Calendar API service
def get_calendar_service():
    """Returns an authorized Calendar API service."""
    creds = get_credentials()
    return build("calendar", "v3", credentials=creds)

# Function to sync events from Google Calendar
def sync_events_from_google():
    """
    Retrieves events from Google Calendar and synchronizes them with the database.
    """
    service = get_calendar_service()

    now = datetime.now(timezone.utc)
    time_day = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    time_min = time_day.replace(day=max(1, now.day - 30))
    time_max = time_day + timedelta(days=90)

    # Call API Google Calendar
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

        # Parse start and end dates
        start = event["start"].get("dateTime", event["start"].get("date"))
        end = event["end"].get("dateTime", event["end"].get("date"))

        start_dt = parse_datetime(start)
        end_dt = parse_datetime(end)

        upsert_event(google_event_id, title, description, start_dt, end_dt)

    return len(google_events)

# Function to create an event
def create_event(title, description, start_dt, end_dt):
    """
    Creates an event in Google Calendar.
    """
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

# Function to update an event
def update_event(google_event_id, title, description, start_dt, end_dt):
    """
    Updates an event in Google Calendar and in DB.
    """
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

# Function to remove an event
def remove_event(google_event_id):
    """
    Deletes an event from Google Calendar and from DB.
    """
    service = get_calendar_service()

    service.events().delete(
        calendarId="primary",
        eventId=google_event_id,
    ).execute()

    delete_event(google_event_id)

# Function to get events
def get_events_for_calendar():
    """
    Returns a list of events for the calendar.
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

# Function to parse datetime
def parse_datetime(dt_str):
    """
    Parse a datetime string.
    """
    if "T" in dt_str:
        dt = datetime.fromisoformat(dt_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    else:
        # If no timezone is specified, assume UTC
        dt = datetime.strptime(dt_str, "%Y-%m-%d")
        return dt.replace(tzinfo=timezone.utc)
