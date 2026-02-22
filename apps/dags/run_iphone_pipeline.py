from __future__ import annotations
import json
import os
from datetime import datetime, timedelta, timezone
from airflow import DAG
from airflow.sdk import task
from airflow.providers.http.operators.http import HttpOperator


BUCKET = "raw-iphone"
TOKEN = os.getenv("TOKEN", "")
if not TOKEN:
    raise RuntimeError("TOKEN absent des variables d'environnement")

HEADERS = {"Authorization": f"Bearer {TOKEN}", "Accept": "application/json"}

def extract_objects(response_text: str) -> list:
    try:
        data = json.loads(response_text)
    except json.JSONDecodeError:
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("objects"), list):
        return data["objects"]
    return []

with DAG(
    dag_id="iphone_minio_watch_and_run",
    start_date=datetime(2026, 1, 27, tzinfo=timezone.utc),
    schedule="*/5 * * * *",
    catchup=False,
    max_active_runs=1,
    default_args={
        "retries": 1,
        "retry_delay": timedelta(minutes=1),
    },
    tags=["iphone", "minio", "ingestion"],
) as dag:

    list_objects = HttpOperator(
        task_id="list_objects",
        http_conn_id="ingestion_api",
        endpoint=f"/bucket/object-list/{BUCKET}",
        method="GET",
        headers=HEADERS,
        log_response=True,
        do_xcom_push=True,
    )
    
    @task.short_circuit()
    def has_files(response_text: str) -> bool:
        return len(extract_objects(response_text)) > 0

    run_worker = HttpOperator(
        task_id="run_worker_iphone",
        http_conn_id="worker_health",
        endpoint="/run/iphone",
        method="GET",
        headers=HEADERS,
        log_response=True,
        # response_check=lambda r: r.ok and r.json().get("status") == "success",
    )

    list_objects >> has_files(list_objects.output) >> run_worker