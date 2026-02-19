from fastapi import FastAPI, UploadFile, File, Body, Depends, Form, Query, HTTPException
from datetime import datetime, timezone
import json
import uuid
import logging
from libs.security_medplum import require_scopes
from utils.api_minio import upload_file, get_object_json, bucket_create, bucket_list_objects, move_object, get_raw_object, object_delete

# Configuration
logger = logging.getLogger("api-ingestion")
logging.basicConfig(level=logging.INFO)

BUCKET_RAW_IPHONE = "raw-iphone"
BUCKET_RAW_MANUAL = "raw-manual"
BUCKET_RAW_SPIROMETER = "raw-spirometer"
BUCKET_PROCESSED_FHIR = "processed-fhir"
BUCKET_PROCESSED_DF = "processed-df"
BUCKET_SQLITE_RAW_SPIROMETER = "raw-db-spirometer"
SQLITE_HEADER = b"SQLite format 3\x00"

app = FastAPI(title="Health Ingest")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

# def api_key_dep(scopes):
#     return require_api_key(scopes=scopes)

# Global endpoints
@app.get("/")
def root():
    return {"message": "API-Ingestion ready."}

@app.get("/healthz")
async def healthz():
    return {"status": "ok", "time": now_iso()}


# Helper ingest 
def _ingest_json(payload: dict, bucket: str, device: dict):
    if not payload:
        raise HTTPException(status_code=400, detail="empty payload")
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    response = upload_file(data, bucket, object_name=None)

    if not response.get("ok"):
        raise HTTPException(status_code=500, detail=response.get("error", "upload failed"))

    return {"status": "ok", "bytes": len(data), "device": device.get("device")}

def _ingest_bytes(data: bytes, bucket: str, device: dict, object_name: str | None = None):
    if not data:
        raise HTTPException(status_code=400, detail="empty payload")
    if len(data) < 16 or data[:16] != SQLITE_HEADER:
        raise HTTPException(status_code=400, detail="not a valid SQLite3 database file")
    
    response = upload_file(data, bucket, object_name=None)
    if not response.get("ok"):
        raise HTTPException(status_code=500, detail=response.get("error", "upload failed"))
    return {"status": "ok", "bytes": len(data), "device": device.get("device")}

# Iphone json ingest endpoint
@app.post("/ingest/iphone")
async def ingest_iphone(
    payload: dict = Body(...),
    device=Depends(require_scopes(["ingest:iphone"])),
):
    return _ingest_json(payload, BUCKET_RAW_IPHONE, device)

# Manual json ingest endpoint
@app.post("/ingest/manual")
async def ingest_manual(
    payload: dict = Body(...),
    device=Depends(require_scopes(["ingest:manual"])),
):
    return _ingest_json(payload, BUCKET_RAW_MANUAL, device)

# Spirometer json ingest endpoint
@app.post("/ingest/spirometer")
async def ingest_spirometer(
    payload: dict = Body(...),
    device=Depends(require_scopes(["ingest:spirometer"])),
):
    return _ingest_json(payload, BUCKET_RAW_SPIROMETER, device)

@app.post("/ingest/sqlite")
async def ingest_sqlite(
    file: UploadFile = File(...),
    device=Depends(require_scopes(["ingest:sqlite"])),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="missing filename")
    if not file.filename.lower().endswith(".db"):
        raise HTTPException(status_code=400, detail="file must be a .db")
    data = await file.read()

    object_name = file.filename
    return _ingest_bytes(data, BUCKET_SQLITE_RAW_SPIROMETER, device, object_name=object_name)

# FHIR json ingest endpoint
@app.post("/ingest/fhir")
async def ingest_fhir(
    payload: dict = Body(...),
    device=Depends(require_scopes(["ingest:fhir"])),
):
    return _ingest_json(payload, BUCKET_PROCESSED_FHIR, device)


# Generic ingest endpoint
@app.post("/ingest/generic/{bucket}")
async def ingest_generic(
    bucket: str,
    file: UploadFile = File(...),
    metadata: str | None = Form(None),
    object_name: str | None = Query(None),
    device=Depends(require_scopes(["ingest:generic"])),
):
    try:
        data = await file.read()

        key = object_name or file.filename or str(uuid.uuid4())

        meta_dict = None
        if metadata:
            try:
                meta_dict = json.loads(metadata)
                if not isinstance(meta_dict, dict):
                    raise ValueError
                meta_dict = {str(k): str(v) for k, v in meta_dict.items()}
            except Exception:
                raise HTTPException(status_code=400, detail="invalid metadata JSON")

        response = upload_file(data, bucket=bucket, object_name=key, metadata=meta_dict)

        if not response.get("ok"):
            raise HTTPException(status_code=500, detail=response.get("error", "upload failed"))

        return {
            "status": "ok",
            "size": len(data),
            "device": device.get("device"),
            "filename": key,
            "metadata": meta_dict,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("ingest_generic error")
        raise HTTPException(status_code=500, detail=str(e))


# Dataframe ingest endpoint
@app.post("/ingest/dataframe")
async def ingest_dataframe(
    file: UploadFile = File(...),
    device=Depends(require_scopes(["ingest:df"])),
):
    data = await file.read()
    object_name = str(uuid.uuid4())

    response = upload_file(data, bucket=BUCKET_PROCESSED_DF, object_name=object_name)
    if not response.get("ok"):
        raise HTTPException(status_code=500, detail=response.get("error", "upload failed"))

    return {
        "status": "ok",
        "size": len(data),
        "device": device.get("device"),
        "filename": object_name,
    }


# Download raw object endpoint
@app.get("/download/{bucket}/{object_name}")
async def download_object(
    bucket: str,
    object_name: str,
    device=Depends(require_scopes(["download:object"])),
):
    return get_raw_object(bucket, object_name)

# Json object download endpoint
@app.get("/object/json/{bucket}/{object_name}")
async def get_json_object(
    bucket: str,
    object_name: str,
    device=Depends(require_scopes(["download:json"])),
):
    try:
        return get_object_json(bucket, object_name)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )

# Bucket creation endpoint
@app.post("/bucket/create/{bucket}")
async def bucket_creation(
    bucket: str,
    device=Depends(require_scopes(["bucket:create"])),
):
    if not bucket_create(bucket_name=bucket):
        raise HTTPException(status_code=500, detail="bucket creation failed")

    return {"status": "ok", "device": device.get("device"), "bucket_name": bucket}

# Objects list from a bucket
@app.get("/bucket/object-list/{bucket}")
async def bucket_object_list(
    bucket: str,
    device=Depends(require_scopes(["object:list"])),
):
    return bucket_list_objects(bucket)


# Move object from bucket1 to bucket2
@app.post("/object/move/{object_name}/{source_bucket}/{destination_bucket}")
async def move_object_endpoint(
    object_name: str = None,
    source_bucket: str = None,
    destination_bucket: str = None,
    device=Depends(require_scopes(["object:move"])),
):
    if not move_object(object_name, source_bucket, destination_bucket):
        raise HTTPException(status_code=500, detail="move failed")

    return {"status": "ok"}

# Delete object from bucket
@app.post("/object/delete/{bucket_name}/{object_name}")
async def delete_object_endpoint(
    object_name: str,
    source_bucket: str,
    device=Depends(require_scopes(["object:delete"])),
):
    if not object_delete(object_name, source_bucket):
        raise HTTPException(status_code=500, detail="move failed")

    return {"status": "ok"}
