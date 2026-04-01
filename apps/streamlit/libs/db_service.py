import psycopg2
import os
from datetime import datetime

# DB config
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "pompetrack-core-postgresql"),
    "port": os.getenv("DB_PORT", "5432"),
    "database": os.getenv("DB_NAME", "pompetrack"),
    "user": os.getenv("DB_USER", "pompetrack-user"),
    "password": os.getenv("DB_PASSWORD"),
}

# Function to get a database connection
def get_connection():
    return psycopg2.connect(**DB_CONFIG)

# Function to initialize the database
def init_db():
    """
    Creates the events table if it doesn't exist.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id SERIAL PRIMARY KEY,
                    google_event_id VARCHAR(255) UNIQUE NOT NULL,
                    title VARCHAR(255) NOT NULL,
                    description TEXT,
                    start_datetime TIMESTAMPTZ NOT NULL,
                    end_datetime TIMESTAMPTZ NOT NULL,
                    last_synced_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
        conn.commit()

# Function to upsert an event
def upsert_event(google_event_id, title, description, start_datetime, end_datetime):
    """
    Inserts or updates an event.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO events (google_event_id, title, description, start_datetime, end_datetime, last_synced_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
                ON CONFLICT (google_event_id)
                DO UPDATE SET
                    title = EXCLUDED.title,
                    description = EXCLUDED.description,
                    start_datetime = EXCLUDED.start_datetime,
                    end_datetime = EXCLUDED.end_datetime,
                    last_synced_at = NOW()
            """, (google_event_id, title, description, start_datetime, end_datetime))
        conn.commit()

# Function to delete an event
def delete_event(google_event_id):
    """
    Deletes an event.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM events WHERE google_event_id = %s
            """, (google_event_id,))
        conn.commit()

# Function to get all events
def get_all_events():
    """
    Returns all events.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT google_event_id, title, description, start_datetime, end_datetime
                FROM events
                ORDER BY start_datetime ASC
            """)
            rows = cur.fetchall()

    events = []
    for row in rows:
        events.append({
            "google_event_id": row[0],
            "title": row[1],
            "description": row[2],
            "start_datetime": row[3],
            "end_datetime": row[4],
        })
    return events

# Function to get an event
def get_event_by_google_id(google_event_id):
    """
    Returns an event by google_event_id.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT google_event_id, title, description, start_datetime, end_datetime
                FROM events WHERE google_event_id = %s
            """, (google_event_id,))
            row = cur.fetchone()

    if row:
        return {
            "google_event_id": row[0],
            "title": row[1],
            "description": row[2],
            "start_datetime": row[3],
            "end_datetime": row[4],
        }
    return None
