import requests
import os
import logging
import time
import json
from typing import Optional, Dict
from libs.get_medplum_token import get_token

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


BASE_URL_MINIO_API = os.getenv("BASE_URL_MINIO_API", "http://ingestion")
ENDPOINT_OBJECTS_LIST = os.getenv("ENDPOINT_OBJECTS_LIST", "/bucket/object-list/")
ENDPOINT_OBJECT_JSON = os.getenv("ENDPOINT_OBJECT_JSON", "/object/json/")
ENDPOINT_OBJECT_MOVE = os.getenv("ENDPOINT_OBJECT_MOVE", "/object/move/")
ENDPOINT_OBJECT_DELETE = os.getenv("ENDPOINT_OBJECT_DELETE", "/object/delete/")
ENDPOINT_INGEST_MANUAL = os.getenv("ENDPOINT_INGEST_MANUAL", "/ingest/manual")
ENDPOINT_GENERIC = os.getenv("ENDPOINT_GENERIC", "/ingest/generic/")
ENDPOINT_DOWNLOAD_GENERIC = os.getenv("ENDPOINT_DOWNLOAD_GENERIC", "/download/")
ENDPOINT_SPIROMETER = os.getenv("ENDPOINT_SPIROMETER", "/ingest/spirometer/")
ENDPOINT_IPHONE = os.getenv("ENDPOINT_IPHONE", "/ingest/iphone/")


def get_object_list(bucket: str, scope=["object:list"]):
    """
    Retrieve objects list in a bucket.
    """
    token = get_token(scope)
    
    url = BASE_URL_MINIO_API + ENDPOINT_OBJECTS_LIST + bucket
    headers = {
        "Authorization": f"Bearer {token}",
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Erreur lors de la requête : {e}")
        return None
    
def get_object_json(bucket: str, 
                    object_name: str, 
                    scope=["download:json"]):
    """
    Download json file.
    """
    token = get_token(scope)
    
    url = BASE_URL_MINIO_API + ENDPOINT_OBJECT_JSON + bucket + "/" + object_name
    logger.info(f"URL used : {url}")
    headers = {
        "Authorization": f"Bearer {token}",
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        logger.info("Récupération d'un objet : OK")
        data = response.json()
        return data if data is not None else []
    except requests.exceptions.RequestException as e:
        logger.error(f"Erreur get_object_list bucket={bucket} err={e}")
        return []
    except ValueError as e:
        logger.error(f"Réponse non-JSON get_object_list bucket={bucket} err={e}")
        return []
    
def move_object(object_name: str, 
                source_bucket: str, 
                destination_bucket: str,
                scope=["object:move"]):
    """
    Move object from a bucket to an other.
    """
    token = get_token(scope)
    
    url = BASE_URL_MINIO_API + ENDPOINT_OBJECT_MOVE + object_name + "/" + source_bucket + "/" + destination_bucket
    headers = {
        "Authorization": f"Bearer {token}",
    }
    try:
        response = requests.post(url, headers=headers)
        status = response.status_code

        # Si HTTP non-2xx -> erreur
        if not response.ok:
            # on essaie de récupérer un message d'erreur JSON si présent
            err = None
            try:
                data = response.json()
                err = data.get("error") or data.get("detail") or str(data)
            except ValueError:
                err = response.text.strip() or f"HTTP {status}"
            return {"ok": False, "error": err, "status_code": status, "data": None}

        # HTTP 2xx -> OK, et on tente de parser JSON si présent
        data = None
        try:
            data = response.json()
        except ValueError:
            data = None

        return {"ok": True, "error": None, "status_code": status, "data": data}

    except requests.exceptions.RequestException as e:
        return {"ok": False, "error": str(e), "status_code": 0, "data": None}

def upload_manual_file(object_name: str, scope=["ingest:manual"]):
    """
    Upload an object to a bucket.
    """
    token = get_token(scope)
    url = BASE_URL_MINIO_API + ENDPOINT_INGEST_MANUAL
    logger.info(f"URL used : {url}")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"  # Ajout du content-type
    }
    
    try:
        #response = requests.post(url, json=object_name, headers=headers)
        response = requests.post(url, data=object_name, headers=headers)
        response.raise_for_status()
        logger.info("Upload d'un objet : OK")
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error on uploading : {e}")
        raise

def upload_spirometer_file(object_name: str, scope=["ingest:spirometer"]):
    """
    Upload an object to spirometer bucket.
    Returns the response JSON if successful, raises RequestException otherwise.
    """
    token = get_token(scope)
    url = BASE_URL_MINIO_API + ENDPOINT_SPIROMETER
    logger.info(f"URL used : {url}")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, json=object_name, headers=headers)
        response.raise_for_status()
        logger.info("Upload d'un objet : OK")
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error on uploading : {e}")
        raise 

def upload_iphone_json(object_name: str, scope=["ingest:iphone"])
    """
    Upload an object to iphone bucket.
    Returns the response JSON if successful, raises RequestException otherwise.
    """
    token = get_token(scope)
    url = BASE_URL_MINIO_API + ENDPOINT_IPHONE
    logger.info(f"URL used : {url}")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    raw = object_name.getvalue()
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        logger.warning(f"Not a JSON file : {object_name}")
        raise ValueError("Le JSON doit être un objet (racine = { ... }).")
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        logger.info("Upload d'un objet : OK")
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error on uploading : {e}")
        raise 

    
def upload_object_into_bucket(
    file_path: str,
    bucket: str,
    filename: Optional[str] = None,
    metadata: Optional[Dict[str, str]] = None,
    scope=["ingest:generic"],
    timeout=120
):
    """
    Upload an object to the API endpoint expecting multipart/form-data with field 'file'
    and optional form field 'metadata' (JSON string).
    """
    token = get_token(scope)
    
    url = BASE_URL_MINIO_API + ENDPOINT_GENERIC + bucket
    logger.info(f"URL used : {url}")
    headers = {
        "Authorization": f"Bearer {token}",
    }
    try:
        with open(file_path, "rb") as f:
            if filename is None:
                file_name = os.path.basename(file_path)
            else:
                file_name = filename
            files = {"file": (file_name, f, "application/octet-stream")}

            data = {}
            if metadata:
                md = {str(k): str(v) for k, v in metadata.items()}
                data["metadata"] = json.dumps(md)

            response = requests.post(url, headers=headers, files=files, data=data, timeout=timeout)
            response.raise_for_status()
            logger.info(f"Upload d'un objet : OK, status_code={response.status_code}")
            return response.json()
    except requests.exceptions.RequestException:
        logger.exception(f"Erreur lors de l'upload vers {url}")
        return None

def get_object(
    bucket: str, 
    object_name: str, 
    scope=["download:object"],
) -> bool:
    """
    Download file.
    """
    token = get_token(scope)
    
    url = BASE_URL_MINIO_API + ENDPOINT_DOWNLOAD_GENERIC + bucket + "/" + object_name
    logger.info(f"URL used : {url}")
    headers = {
        "Authorization": f"Bearer {token}",
    }
    
    local_path = os.path.join("/tmp", object_name)
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        with open(local_path, "wb") as f:
            f.write(response.content)
        logger.info(f"Objet téléchargé et écrit en local : {local_path}")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Erreur : {e}")
        print(f"Erreur lors de la requête : {e}")
        return False

def delete_object_on_minio(
    bucket: str, 
    object_name: str,
    scope=["object:delete"]
) -> bool:
    """
    Delete object in a bucket
    """
    token = get_token(scope)
    
    url = BASE_URL_MINIO_API + ENDPOINT_OBJECT_DELETE + bucket + "/" + object_name
    logger.info(f"URL used : {url}")
    headers = {
        "Authorization": f"Bearer {token}",
    }     
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        logger.info("Delete object : OK")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Erreur : {e}")
        print(f"Erreur lors de la requête : {e}")
        return False
        

def download_db_object_to_tmp(
    bucket: str, 
    object_name: str, 
    tmp_dir: str = "/tmp", 
    scope=["download:object"]
    ) -> str:
    """
    Download minio object and write it on '/tmp' in binary.
    Return local path.
    """
    token = get_token(scope)
    
    url = BASE_URL_MINIO_API + ENDPOINT_DOWNLOAD_GENERIC + bucket + "/" + object_name
    headers = {"Authorization": f"Bearer {token}"}

    os.makedirs(tmp_dir, exist_ok=True)
    local_path = os.path.join(tmp_dir, f"{object_name}.db")

    try:
        with requests.get(url, headers=headers, stream=True) as r:
            r.raise_for_status()
            with open(local_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        return local_path
    except requests.exceptions.RequestException as e:
        logger.error(f"Download KO object={object_name} bucket={bucket} err={e}")
        return None
    except OSError as e:
        logger.error(f"Écriture locale KO local={local_path} err={e}")
        return None