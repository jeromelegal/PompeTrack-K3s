import sqlite3
import requests
import os
from libs.minio_requests import get_object_list, download_db_object_to_tmp, move_object, delete_object_on_minio
import logging
from pathlib import Path
from typing import Optional

logging.basicConfig(
    level=logging.INFO
)

logger = logging.getLogger("Worke-Sqlite")

BUCKET_DB_RAW = "raw-db-spirometer"
BUCKET_PROCESSED = "processed-db"
DEVICE = os.getenv("DEVICE", "worker-sqlite")
SPIROMETER_INGEST_URL = os.getenv("SPIROMETER_INGEST_URL", "http://ingestion/ingest/spirometer")
TOKEN = os.getenv("TOKEN", "token")

if not TOKEN:
    raise RuntimeError("TOKEN manquant")

# TEST_content indices
TEST_DATE_IDX = 2
TEST_TIME_IDX = 3
TEST_ID_IDX = 7

# FVC_INFO indices
FVC_IDX = {
    "test_id": 0,
    "FVC": 2,
    "FEV1": 5,
    "FEV1_FVC": 6,
    "FEV6": 10,
    "PEF": 12,
    "FEF25": 13,
    "FEF50": 14,
    "FEF75": 15,
    "FEF2575": 16,
}
        
def _create_instance(name, date, value, unit) -> dict:
    return  {
        "name": name,
        "data": [
            {
                "qty": value,
                "date": date
            }
        ],
        "units": unit
    }

def is_sqlite_db(path: str) -> bool:
    """
    Verify if object is sqlite db
    """
    try:
        with open(path, "rb") as f:
            header = f.read(16)
        return header == b"SQLite format 3\x00"
    except OSError:
        return False
        
def postprocess_move_and_cleanup(
    local_path: str,
    object_name: str,
    raw_bucket: str,
    processed_bucket: str,
) -> None:
    response = move_object(
        object_name=object_name,
        source_bucket=raw_bucket,
        destination_bucket=processed_bucket,
    )
    if not response.get("ok"):
        logger.error(f"Move KO for object : {object_name}")
        return
    # Move OK 
    try:
        os.remove(local_path)
        logger.info("Move OK")
    except OSError as e:
        logger.warning(f"Move OK but local remove error on object :{object_name}")


def process_db_to_json(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Aw retrieve
    cur.execute("SELECT * FROM TEST_content")
    tests = cur.fetchall()

    cur.execute("SELECT * FROM FVC_INFO")
    fvc_rows = cur.fetchall()

    # Index FVC_INFO par test_id
    fvc_by_test_id = {
        row[FVC_IDX["test_id"]]: row
        for row in fvc_rows
    }

    instances = []
    
    for test in tests:
        test_id = test[TEST_ID_IDX]

        if test_id not in fvc_by_test_id:
            continue

        fvc = fvc_by_test_id[test_id]

        date = test[TEST_DATE_IDX] + "T" + test[TEST_TIME_IDX]
        instances.append(_create_instance("FVC", date, fvc[FVC_IDX["FVC"]], "L"))
        instances.append(_create_instance("FEV1", date, fvc[FVC_IDX["FEV1"]], "L"))
        instances.append(_create_instance("FEV1_FVC", date, fvc[FVC_IDX["FEV1_FVC"]], "%"))
        instances.append(_create_instance("FEV6", date, fvc[FVC_IDX["FEV6"]], "L"))
        instances.append(_create_instance("PEF", date, fvc[FVC_IDX["PEF"]], "L/s"))
        instances.append(_create_instance("FEF25", date, fvc[FVC_IDX["FEF25"]], "L/s"))
        instances.append(_create_instance("FEF50", date, fvc[FVC_IDX["FEF50"]], "L/s"))
        instances.append(_create_instance("FEF75", date, fvc[FVC_IDX["FEF75"]], "L/s"))
        instances.append(_create_instance("FEF2575", date, fvc[FVC_IDX["FEF2575"]], "L/s"))

    conn.close()
    json_file = {"metrics": instances}
    #print(f"JSON généré : {json_file}")
    
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    try:
        response = requests.post(
            SPIROMETER_INGEST_URL, 
            json=json_file, 
            headers=headers, 
            timeout=20
            )
        response.raise_for_status()
        # print("Succès :", response.json())
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"Erreur lors de l’envoi : {e}")
        return False
            

def pipeline_sqlite_to_json(
    raw_bucket: str = BUCKET_DB_RAW,
    processed_bucket: str = BUCKET_PROCESSED,
    tmp_dir: str = "/tmp",
) -> None:
    """
    1. retrieve objects list in bucket
    2. download localy
    3.1 verify sqlite file -> processing sqlite->json->POST (process_db_to_json)
    3.2 if not sqlite => delete localy and on minio
    4. if OK -> move raw->processed, delete local if move OK
    """
    objects = get_object_list(raw_bucket)
    if not objects:
        logger.info(f"No objects on bucket : {raw_bucket}")
        return

    for object_name in objects:
        local_path = download_db_object_to_tmp(raw_bucket, object_name, tmp_dir=tmp_dir)
        if not local_path:
            continue

        # Id not-sqlite => log + delete local + delete on minio + continue
        if not is_sqlite_db(local_path):
            logger.error(f"Not sqlite object: {local_path}. Delete localy end on bucket")
            try:
                os.remove(local_path)
                delete_object_on_minio(bucket=raw_bucket, object_name=object_name)
            except OSError:
                pass
            continue

        # Processing sqlite to json
        try:
            ok = process_db_to_json(local_path)
        except Exception as e:
            logger.exception(f"Error on processing object : {local_path}")
            continue
        if not ok:
            logger.error(f"Processing returns False on {local_path}")
            continue

        # Move + delete localy only if move OK
        postprocess_move_and_cleanup(
            local_path=local_path,
            object_name=object_name,
            raw_bucket=raw_bucket,
            processed_bucket=processed_bucket,
        )


if __name__ == "__main__":
    pipeline_sqlite_to_json()
