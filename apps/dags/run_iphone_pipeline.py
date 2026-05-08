from __future__ import annotations
import json
import os
from datetime import datetime, timedelta, timezone
from airflow import DAG
from airflow.sdk import task
from airflow.providers.http.operators.http import HttpOperator
from airflow.providers.standard.operators.python import PythonOperator
from libs.medplum_header_operator import MedplumHeaderOperator  
from airflow.models.xcom_arg import XComArg


BUCKET = "raw-iphone"

# Extract the objects from the response
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

# Dag process :
# 1. Get the ingestion headers
# 2. List the objects in the bucket
# 3. Run the ingestion pipeline

with DAG(
    dag_id="iphone_minio_watch_and_run",
    start_date=datetime(2026, 1, 27, tzinfo=timezone.utc),
    schedule="* */1 * * *",
    catchup=False,
    max_active_runs=1,
    default_args={
        "retries": 1,
        "retry_delay": timedelta(minutes=1),
    },
    tags=["iphone", "minio", "ingestion"],
) as dag:
    
    get_ingestion_headers_task = MedplumHeaderOperator(
        task_id="get_ingestion_headers_task",
        scope=["object:list"],
    )

    list_objects = HttpOperator(
        task_id="list_objects",
        http_conn_id="ingestion",
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
        scope=["airflow:iphone"],
    )
    
    run_worker = HttpOperator(
        task_id="run_worker_iphone",
        http_conn_id="worker_fhir",
        endpoint="/run/iphone",
        method="GET",
        headers=XComArg(get_worker_headers_task),
        log_response=True,
        # response_check=lambda r: r.ok and r.json().get("status") == "success",
    )
    
    get_logs_headers_task = MedplumHeaderOperator(
        task_id="get_logs_headers_task",
        scope=["fhir:logs"],
    )
    
    run_transfer_logs = HttpOperator(
        task_id="run_transfer_logs",
        http_conn_id="worker_fhir",
        endpoint="/run/logs",
        method="GET",
        headers=XComArg(get_logs_headers_task),
        log_response=True,
    )

    get_ingestion_headers_task >> list_objects >> has_files(list_objects.output) >> get_worker_headers_task >> run_worker >> get_logs_headers_task >> run_transfer_logs