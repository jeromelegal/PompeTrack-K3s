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

# Function to upsert medication
def upsert_medication(source_system, canonical_key, raw_name, normalized_name, 
                      medplum_medication_id, code_system, code_value, display, 
                      strength_value, strength_unit, dose_form, start_datetime, 
                      end_datetime
):
    """
    Inserts or updates a medication.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO medication_map
                (
                    source_system,
                    canonical_key,
                    raw_name,
                    normalized_name,
                    medplum_medication_id,
                    code_system,
                    code_value,
                    display,
                    strength_value,
                    strength_unit,
                    dose_form,
                    last_seen_at,
                    updated_at
                )
                VALUES
                (
                    %(source_system)s,
                    %(canonical_key)s,
                    %(raw_name)s,
                    %(normalized_name)s,
                    %(medplum_medication_id)s,
                    %(code_system)s,
                    %(code_value)s,
                    %(display)s,
                    %(strength_value)s,
                    %(strength_unit)s,
                    %(dose_form)s,
                    now(),
                    now()
                )
                ON CONFLICT (source_system, canonical_key)
                DO UPDATE SET
                    raw_name              = EXCLUDED.raw_name,
                    normalized_name       = EXCLUDED.normalized_name,
                    medplum_medication_id = EXCLUDED.medplum_medication_id,
                    code_system           = EXCLUDED.code_system,
                    code_value            = EXCLUDED.code_value,
                    display               = EXCLUDED.display,
                    strength_value        = EXCLUDED.strength_value,
                    strength_unit         = EXCLUDED.strength_unit,
                    dose_form             = EXCLUDED.dose_form,
                    last_seen_at          = now(),
                    updated_at            = now();
            """, (source_system, canonical_key, raw_name, normalized_name, 
                      medplum_medication_id, code_system, code_value, display, 
                      strength_value, strength_unit, dose_form, start_datetime, 
                      end_datetime))
        conn.commit()
        
# Function to delete a medication
def delete_event(canonical_key):
    """
    Deletes a medication.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM medication_map WHERE canonical_key = %s
            """, (canonical_key,))
        conn.commit()
        
# Function to get a medication
def get_medication_by_canonical_key(canonical_key):
    """
    Returns a medication by canonical_key.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT canonical_key, source_system, raw_name, normalized_name, 
                      medplum_medication_id, code_system, code_value, display, 
                      strength_value, strength_unit, dose_form, last_seen_at, 
                      updated_at
                FROM medication_map WHERE canonical_key = %s
            """, (canonical_key,))
            row = cur.fetchone()

    if row:
        return {
            "canonical_key": row[0],
            "source_system": row[1], 
            "raw_name": row[2], 
            "normalized_name": row[3], 
            "medplum_medication_id": row[4], 
            "code_system": row[5], 
            "code_value": row[6], 
            "display": row[7], 
            "strength_value": row[8], 
            "strength_unit": row[9], 
            "dose_form": row[10], 
            "last_seen_at": row[11], 
            "updated_at": row[12],
        }
    return None

# Function to get all medication
def get_all_medications():
    """
    Returns all medications.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT canonical_key, source_system, raw_name, normalized_name, 
                      medplum_medication_id, code_system, code_value, display, 
                      strength_value, strength_unit, dose_form, last_seen_at, 
                      updated_at
                FROM medication_map
            """)
            row = cur.fetchone()

    if row:
        return {
            "canonical_key": row[0],
            "source_system": row[1], 
            "raw_name": row[2], 
            "normalized_name": row[3], 
            "medplum_medication_id": row[4], 
            "code_system": row[5], 
            "code_value": row[6], 
            "display": row[7], 
            "strength_value": row[8], 
            "strength_unit": row[9], 
            "dose_form": row[10], 
            "last_seen_at": row[11], 
            "updated_at": row[12],
        }
    return None

# Function to get ids medication
def get_id_medication():
    """
    Returns id medication from source_system and canonical_key.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT medplum_medication_id, 
                      display
                FROM medication_map
                WHERE source_system = %(source_system)s
                AND canonical_key = %(canonical_key)s;
            """, (source_system, canonical_key))
            row = cur.fetchone()

    if row:
        return {
            "medplum_medication_id": row[0], 
            "display": row[1], 
        }
    return None