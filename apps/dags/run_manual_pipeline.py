from __future__ import annotations
import json
import os
from datetime import datetime, timedelta, timezone
from airflow import DAG
from airflow.sdk import task
from airflow.providers.http.operators.http import HttpOperator
from airflow.operators.python import PythonOperator
from libs.medplum_header_operator import MedplumHeaderOperator 
from airflow.models.xcom_arg import XComArg
 

BUCKET = "raw-manual"

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
    dag_id="manual_minio_watch_and_run",
    start_date=datetime(2026, 1, 27, tzinfo=timezone.utc),
    schedule="*/5 * * * *",
    catchup=False,
    max_active_runs=1,
    default_args={
        "retries": 1,
        "retry_delay": timedelta(minutes=1),
    },
    tags=["manual", "minio", "ingestion"],
) as dag:
    
    get_ingestion_headers_task = MedplumHeaderOperator(
        task_id="get_ingestion_headers_task",
        scope=["object:list"],
    )

    list_objects = HttpOperator(
        task_id="list_objects",
        http_conn_id="ingestion_api",
        endpoint=f"/bucket/object-list/{BUCKET}",
        method="GET",
        headers=XComArg(get_ingestion_headers_task),
        log_response=True,
        do_xcom_push=True,
    )
    
    @task.short_circuit()
    def has_files(response_text: str) -> bool:
        return len(extract_objects(response_text)) > 0

    get_worker_headers_task = MedplumHeaderOperator(
        task_id="get_worker_headers_task",
        scope=["airflow:manual"],
    )

    run_worker = HttpOperator(
        task_id="run_worker_manual",
        http_conn_id="worker_health",
        endpoint="/run/manual",
        method="GET",
        headers=XComArg(get_worker_headers_task),
        log_response=True,
        # response_check=lambda r: r.ok and r.json().get("status") == "success",
    )

    get_ingestion_headers_task >> list_objects >> has_files(list_objects.output) >> get_worker_headers_task >> run_worker