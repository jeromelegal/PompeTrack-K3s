import os
import json
import logging
from typing import Optional, Dict, Any, Union

import requests

from libs.get_medplum_token import get_token

logger = logging.getLogger(__name__)

# Base URL / endpoints
BASE_URL_MINIO_API = os.getenv("BASE_URL_MINIO_API", "http://ingestion").rstrip("/")

ENDPOINT_OBJECTS_LIST = os.getenv("ENDPOINT_OBJECTS_LIST", "/bucket/object-list/")
ENDPOINT_OBJECT_JSON = os.getenv("ENDPOINT_OBJECT_JSON", "/object/json/")
ENDPOINT_OBJECT_MOVE = os.getenv("ENDPOINT_OBJECT_MOVE", "/object/move/")
ENDPOINT_OBJECT_DELETE = os.getenv("ENDPOINT_OBJECT_DELETE", "/object/delete/")
ENDPOINT_INGEST_MANUAL = os.getenv("ENDPOINT_INGEST_MANUAL", "/ingest/manual")
ENDPOINT_GENERIC = os.getenv("ENDPOINT_GENERIC", "/ingest/generic/")
ENDPOINT_DOWNLOAD_GENERIC = os.getenv("ENDPOINT_DOWNLOAD_GENERIC", "/download/")
ENDPOINT_SPIROMETER = os.getenv("ENDPOINT_SPIROMETER", "/ingest/spirometer/")
ENDPOINT_IPHONE = os.getenv("ENDPOINT_IPHONE", "/ingest/iphone/")
ENDPOINT_INGEST_SQLITE = os.getenv("ENDPOINT_INGEST_SQLITE", "/ingest/sqlite/")
ENDPOINT_INGEST_MEDICATION = os.getenv("ENDPOINT_INGEST_MEDICATION", "/ingest/medication/")

DEFAULT_TIMEOUT = float(os.getenv("MINIO_API_TIMEOUT", "30"))

# Function to ensure leading slash
def _url(path: str) -> str:
    if not path.startswith("/"):
        path = "/" + path
    return BASE_URL_MINIO_API + path

# Function to add auth headers
def _auth_headers(scope: str, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Add auth headers."""
    token = get_token(scope)
    headers = {"Authorization": f"Bearer {token}"}
    if extra:
        headers.update(extra)
    return headers

# Function to get object list
def get_object_list(bucket: str, scope: str = "object:list") -> Optional[Any]:
    """Retrieve objects list in a bucket."""
    url = _url(ENDPOINT_OBJECTS_LIST + bucket)
    headers = _auth_headers(scope)

    try:
        resp = requests.get(url, headers=headers, timeout=DEFAULT_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        logger.error("get_object_list failed bucket=%s err=%s", bucket, e)
        return None
    except ValueError as e:
        logger.error("get_object_list non-JSON bucket=%s err=%s", bucket, e)
        return None

# Function to download json
def get_object_json(bucket: str, object_name: str, scope: str = "download:json") -> Any:
    """Download json file. Returns dict/list or [] on error."""
    url = _url(ENDPOINT_OBJECT_JSON + bucket + "/" + object_name)
    headers = _auth_headers(scope)

    try:
        resp = requests.get(url, headers=headers, timeout=DEFAULT_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        logger.error("get_object_json failed bucket=%s object=%s err=%s", bucket, object_name, e)
        return []
    except ValueError as e:
        logger.error("get_object_json non-JSON bucket=%s object=%s err=%s", bucket, object_name, e)
        return []

# Function to move object
def move_object(
    object_name: str,
    source_bucket: str,
    destination_bucket: str,
    scope: str = "object:move",
) -> Dict[str, Any]:
    """Move object from a bucket to another. Returns a structured result dict."""
    url = _url(ENDPOINT_OBJECT_MOVE + object_name + "/" + source_bucket + "/" + destination_bucket)
    headers = _auth_headers(scope)

    try:
        resp = requests.post(url, headers=headers, timeout=DEFAULT_TIMEOUT)
        status = resp.status_code

        if not resp.ok:
            try:
                data = resp.json()
                err = data.get("error") or data.get("detail") or str(data)
            except ValueError:
                err = resp.text.strip() or f"HTTP {status}"
            return {"ok": False, "error": err, "status_code": status, "data": None}

        try:
            data = resp.json()
        except ValueError:
            data = None

        return {"ok": True, "error": None, "status_code": status, "data": data}

    except requests.RequestException as e:
        return {"ok": False, "error": str(e), "status_code": 0, "data": None}

# Function to upload manual file
def upload_manual_file(object_name: Union[str, Dict[str, Any]], scope: str = "ingest:manual") -> Any:
    """
    Upload manual ingestion payload.
    """
    url = _url(ENDPOINT_INGEST_MANUAL)
    headers = _auth_headers(scope, extra={"Content-Type": "application/json"})

    try:
        resp = requests.post(url, data=object_name, headers=headers, timeout=DEFAULT_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        logger.error("upload_manual_file failed err=%s", e)
        raise
    except ValueError:
        return None
    
# Function to upload spirometer file
def upload_spirometer_file(object_name: Any, scope: str = "ingest:spirometer") -> Any:
    """Upload spirometer payload as JSON."""
    url = _url(ENDPOINT_SPIROMETER)
    headers = _auth_headers(scope, extra={"Content-Type": "application/json"})

    try:
        resp = requests.post(url, json=object_name, headers=headers, timeout=DEFAULT_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        logger.error("upload_spirometer_file failed err=%s", e)
        raise

# Function to upload iPhone JSON
def upload_iphone_json(object_file: Any, scope: str = "ingest:iphone") -> requests.Response:
    """
    Upload iPhone JSON.
    """
    url = _url(ENDPOINT_IPHONE)
    headers = _auth_headers(scope, extra={"Content-Type": "application/json"})

    raw = object_file.getvalue()
    payload = json.loads(raw.decode("utf-8"))

    if not isinstance(payload, dict):
        raise ValueError("Le JSON doit être un objet (racine = { ... }).")

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=DEFAULT_TIMEOUT)
        resp.raise_for_status()
        return resp
    except requests.RequestException as e:
        logger.error("upload_iphone_json failed err=%s", e)
        raise

# Function to upload Medication json
def upload_medication_json(json_file: Any, scope: str = "ingest:medication") -> requests.Response:
    """
    Upload Medication JSON.
    """
    url = _url(ENDPOINT_INGEST_MEDICATION)
    headers = _auth_headers(scope, extra={"Content-Type": "application/json"})

    if not isinstance(json_file, dict):
        raise ValueError("Le JSON doit être un objet (racine = { ... }).")

    try:
        resp = requests.post(url, json=json_file, headers=headers, timeout=DEFAULT_TIMEOUT)
        resp.raise_for_status()
        return resp
    except requests.RequestException as e:
        logger.error(f"upload_medication_json failed err={e}")
        raise

# Function to upload sqlite file
def upload_db_file(object_file: Any, scope: str = "ingest:sqlite") -> requests.Response:
    """
    Upload sqlite file (multipart).
    """
    url = _url(ENDPOINT_INGEST_SQLITE)
    headers = _auth_headers(scope, extra={"Accept": "application/json"})

    files = {"file": (object_file.name, object_file.getvalue(), "application/octet-stream")}

    try:
        resp = requests.post(url, files=files, headers=headers, timeout=120)
        resp.raise_for_status()
        return resp
    except requests.RequestException as e:
        logger.error("upload_db_file failed err=%s", e)
        raise

#
def upload_object_into_bucket(
    file_path: str,
    bucket: str,
    filename: Optional[str] = None,
    metadata: Optional[Dict[str, str]] = None,
    scope: str = "ingest:generic",
    timeout: float = 120,
) -> Optional[requests.Response]:
    """
    Upload generic file (multipart) with optional metadata form field.
    """
    url = _url(ENDPOINT_GENERIC + bucket)
    headers = _auth_headers(scope)

    try:
        with open(file_path, "rb") as f:
            file_name = filename or os.path.basename(file_path)
            files = {"file": (file_name, f, "application/octet-stream")}

            data: Dict[str, str] = {}
            if metadata:
                md = {str(k): str(v) for k, v in metadata.items()}
                data["metadata"] = json.dumps(md)

            resp = requests.post(url, headers=headers, files=files, data=data, timeout=timeout)
            resp.raise_for_status()
            return resp

    except requests.RequestException as e:
        logger.exception("upload_object_into_bucket failed url=%s err=%s", url, e)
        return None
    except OSError as e:
        logger.exception("upload_object_into_bucket file open failed file_path=%s err=%s", file_path, e)
        return None

# Function to download file
def get_object(bucket: str, object_name: str, scope: str = "download:object") -> bool:
    """Download file to /tmp/<object_name>."""
    url = _url(ENDPOINT_DOWNLOAD_GENERIC + bucket + "/" + object_name)
    headers = _auth_headers(scope)
    local_path = os.path.join("/tmp", object_name)

    try:
        resp = requests.get(url, headers=headers, timeout=DEFAULT_TIMEOUT)
        resp.raise_for_status()
        with open(local_path, "wb") as f:
            f.write(resp.content)
        logger.info("Downloaded to %s", local_path)
        return True
    except requests.RequestException as e:
        logger.error("get_object failed bucket=%s object=%s err=%s", bucket, object_name, e)
        return False
    except OSError as e:
        logger.error("get_object local write failed path=%s err=%s", local_path, e)
        return False

# Function to delete object
def delete_object_on_minio(bucket: str, object_name: str, scope: str = "object:delete") -> bool:
    """Delete object in a bucket (kept as GET because your API seems to do that)."""
    url = _url(ENDPOINT_OBJECT_DELETE + bucket + "/" + object_name)
    headers = _auth_headers(scope)

    try:
        resp = requests.get(url, headers=headers, timeout=DEFAULT_TIMEOUT)
        resp.raise_for_status()
        return True
    except requests.RequestException as e:
        logger.error("delete_object_on_minio failed bucket=%s object=%s err=%s", bucket, object_name, e)
        return False

# Function to download object
def download_db_object_to_tmp(
    bucket: str,
    object_name: str,
    tmp_dir: str = "/tmp",
    scope: str = "download:object",
) -> Optional[str]:
    """
    Download minio object and write it on tmp_dir in binary.
    Return local path or None.
    """
    url = _url(ENDPOINT_DOWNLOAD_GENERIC + bucket + "/" + object_name)
    headers = _auth_headers(scope)

    os.makedirs(tmp_dir, exist_ok=True)
    local_path = os.path.join(tmp_dir, f"{object_name}.db")

    try:
        with requests.get(url, headers=headers, stream=True, timeout=DEFAULT_TIMEOUT) as r:
            r.raise_for_status()
            with open(local_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        return local_path

    except requests.RequestException as e:
        logger.error("download_db_object_to_tmp failed bucket=%s object=%s err=%s", bucket, object_name, e)
        return None
    except OSError as e:
        logger.error("download_db_object_to_tmp local write failed path=%s err=%s", local_path, e)
        return None
