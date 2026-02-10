import os
from typing import Optional, Union, Dict
import uuid
import logging
from io import BytesIO
import json
import tempfile
from fastapi.responses import StreamingResponse
import mimetypes
import pathlib
import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger("API-ingestion")
logger.setLevel(os.getenv("LOGLEVEL", "INFO"))

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
MINIO_ACCESS_KEY_ID = os.getenv("MINIO_ACCESS_KEY_ID", None)
MINIO_SECRET_ACCESS_KEY = os.getenv("MINIO_SECRET_ACCESS_KEY", None)
MINIO_REGION = os.getenv("MINIO_REGION", "us-east-1")
MINIO_FORCE_PATH_STYLE = os.getenv("MINIO_FORCE_PATH_STYLE", "true").lower() in ("1", "true", "yes")

_botocore_config = Config(
    signature_version="s3v4",
    region_name=MINIO_REGION,
    s3={"addressing_style": "path"} if MINIO_FORCE_PATH_STYLE else None,
)

# Create client
s3_client = boto3.client(
    "s3",
    endpoint_url=MINIO_ENDPOINT,
    aws_access_key_id=MINIO_ACCESS_KEY_ID,
    aws_secret_access_key=MINIO_SECRET_ACCESS_KEY,
    config=_botocore_config,
)

# def _make_object_name(bucket: str, object_name: Optional[str]) -> str:
#     if object_name:
#         return object_name
#     return uuid.uuid4().hex
def _make_object_name(bucket: str, filename: str | None):
    """
    Si `filename` est None ou vide, génère une clé aléatoire
    sous forme `bucket/<hex>.json` (ou selon votre convention).
    """
    # Le choix entre aléatoire ou "bucket/" doit être clair
    if not filename:
        # On conserve le préfixe bucket/
        return f"{bucket}/{uuid.uuid4().hex}"
    else:
        # S’il y a déjà un préfixe de dossier, on le laisse
        if str(filename).startswith(f"{bucket}/"):
            return filename
        return f"{filename}"

def upload_file(
    filedata: Union[str, bytes, bytearray, BytesIO],
    bucket: str,
    object_name: Optional[str] = None,
    content_type: Optional[str] = None,
    metadata: Optional[Dict[str, str]] = None,
) -> dict:
    """
    Uploads either:
      - a filesystem path (str -> upload_file),
      - bytes/bytearray/BytesIO -> upload_fileobj
      - fallback -> put_object

    metadata: optional dict of strings -> will be sent as S3 user metadata (x-amz-meta-*)
    Returns a dict with status and object name or error.
    """
    object_name = _make_object_name(bucket, object_name)

    # build ExtraArgs if needed for upload_file / upload_fileobj
    extra_args = {}
    if content_type:
        extra_args["ContentType"] = content_type
    if metadata:
        # boto3 expects plain dict for metadata (it will add x-amz-meta- prefix)
        extra_args["Metadata"] = metadata

    try:
        # filesystem path
        if isinstance(filedata, str):
            if os.path.exists(filedata):
                # upload_file wants ExtraArgs dict (can be empty)
                s3_client.upload_file(filedata, bucket, object_name, ExtraArgs=extra_args or {})
                return {"ok": True, "bucket": bucket, "object": object_name, "method": "upload_file"}
            else:
                msg = f"path not found: {filedata}"
                logger.error(msg)
                return {"ok": False, "error": msg}

        # bytes-like -> stream (recommended)
        if isinstance(filedata, (bytes, bytearray)):
            bio = BytesIO(filedata)
            bio.seek(0)
            s3_client.upload_fileobj(bio, bucket, object_name, ExtraArgs=extra_args or {})
            return {"ok": True, "bucket": bucket, "object": object_name, "method": "upload_fileobj", "size": len(filedata)}

        # BytesIO-like
        if isinstance(filedata, BytesIO):
            filedata.seek(0)
            s3_client.upload_fileobj(filedata, bucket, object_name, ExtraArgs=extra_args or {})
            size = filedata.getbuffer().nbytes if hasattr(filedata, "getbuffer") else None
            return {"ok": True, "bucket": bucket, "object": object_name, "method": "upload_fileobj", "size": size}

        # fallback -> put_object accepts Metadata parameter directly
        put_kwargs = {"Bucket": bucket, "Key": object_name, "Body": filedata}
        if content_type:
            put_kwargs["ContentType"] = content_type
        if metadata:
            put_kwargs["Metadata"] = metadata

        s3_client.put_object(**put_kwargs)
        return {"ok": True, "bucket": bucket, "object": object_name, "method": "put_object"}

    except (BotoCoreError, ClientError) as exc:
        logger.exception("MINIO upload failed")
        return {"ok": False, "error": str(exc), "bucket": bucket, "object": object_name}

def bucket_list_objects(bucket: str, s3_client=s3_client, prefix: str | None = None):
    """
    Return list of file name in a bucket.
    """
    try:
        paginator = s3_client.get_paginator("list_objects_v2")
        page_iterator = paginator.paginate(Bucket=bucket, Prefix=prefix or "")

        keys = []
        for page in page_iterator:
            for obj in page.get("Contents", []):
                keys.append(obj["Key"])
        return keys

    except (ClientError, BotoCoreError) as e:
        logging.error(e)
        raise RuntimeError(f"Erreur S3 lors du listing du bucket '{bucket}': {e}") from e

def download_file(bucket: str, key: str, s3_client=s3_client) -> str:
    """
    Download object in a temp file and return local path.
    """
    try:
        tmp = tempfile.NamedTemporaryFile(prefix="minio_", delete=False)
        tmp_path = tmp.name
        tmp.close()
        s3_client.download_file(Bucket=bucket, Key=key, Filename=tmp_path)
        logger.info("download_file: succès, fichier local=%s", tmp_path)
        return tmp_path
    except (ClientError, BotoCoreError) as e:
        logger.exception("Erreur lors du download_file depuis %s/%s", bucket, key)
        raise RuntimeError(f"Erreur lors de la lecture '{key}' dans '{bucket}': {e}") from e
    
def get_raw_object(bucket: str, object_name: str, s3_client=s3_client) -> str:
    """
    Download object
    """
    try:
        object = s3_client.get_object(Bucket=bucket, Key=object_name)
        body = object["Body"]
        
        content_type = object.get("ContentType") or mimetypes.guess_type(object_name)[0] or "application/octet-stream"
        
        return StreamingResponse(
            body,
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{object_name}"'
            },
        )

    except (ClientError, BotoCoreError) as e:
        raise ValueError(f"Objet introuvable ou erreur MinIO: {e}")

def get_object_json(bucket: str, object_name: str, s3_client=s3_client):
    """
    Return a json object from a bucket.
    """
    try:
        resp = s3_client.get_object(Bucket=bucket, Key=object_name)
        body = resp["Body"].read()
        return json.loads(body)
    except (ClientError, BotoCoreError) as e:
        logging.error(e)
        raise RuntimeError(f"Erreur lors de la lecture de '{object_name}' dans '{bucket}': {e}") from e
    except json.JSONDecodeError as je:
        logging.error(je)
        raise ValueError(f"Le contenu de '{object_name}' n'est pas un JSON valide : {je}") from je
 
# Déplace un object dans Minio d'un bucket à un autre
def move_object(object_name, source_bucket, destination_bucket, s3_client=s3_client):
    """
    Move an object from a bucket to another 
    Return True if OK, else False
    """
    try:
        copy_source = {'Bucket': source_bucket, 'Key': object_name}
        s3_client.copy_object(
            CopySource=copy_source,
            Bucket=destination_bucket,
            Key=object_name
        )
        s3_client.delete_object(
            Bucket=source_bucket,
            Key=object_name
        )
        return True
    except ClientError as e:
        logging.error(e)
        print(f"Fail to move object : {e}")
        return False
        
def bucket_create(bucket_name, s3_client=s3_client):
    """
    Create a bucket.
    """
    # Create bucket
    try:
        s3_client.create_bucket(Bucket=bucket_name)
    except ClientError as e:
        logging.error(e)
        return False
    return True

def bucket_delete(bucket_name, s3_client=s3_client):
    """
    Delete a bucket.
    """
    # Delete bucket
    try:
        s3_client.delete_bucket(Bucket=bucket_name)
    except ClientError as e:
        logging.error(e)
        return False
    return True

def object_delete(object_name, bucket_name, s3_client=s3_client):
    """
    Delete object in a bucket.
    """
    try:
        s3_client.delete_object(Bucket=bucket_name,
                                Key=object_name,)
    except ClientError as e:
        logging.error(e)
        return False
    return True
    

def buckets_list(s3_client=s3_client):
    """Lister le noms des buckets"""
    response = s3_client.list_buckets()
    logger.info('Existing buckets:')
    for bucket in response['Buckets']:
        logger.info(f'  {bucket["Name"]}')
    return response

def _streaming_body_iter(streaming_body, chunk_size: int = 64 * 1024):
    """
    Itère sur le StreamingBody de boto3 en chunks.
    """
    while True:
        chunk = streaming_body.read(chunk_size)
        if not chunk:
            break
        yield chunk

def get_object_stream(bucket: str,
                      key: str,
                      s3_client=s3_client,
                      filename: str | None = None,
                      media_type: str = "application/octet-stream",
                      chunk_size: int = 64 * 1024):
    """
    Récupère l'objet depuis S3/MinIO et renvoie une StreamingResponse.
    - n'effectue PAS de lecture complète en mémoire (utilise le StreamingBody).
    - s3_client doit être un client boto3 initialisé.
    - filename : nom souhaité pour Content-Disposition; si None, utilisera `key`.
    """
    try:
        resp = s3_client.get_object(Bucket=bucket, Key=key)
        streaming_body = resp.get("Body")
        if streaming_body is None:
            raise RuntimeError("S3 response has no Body")
        # Content-Disposition filename
        fname = filename or key
        headers = {"Content-Disposition": f'attachment; filename="{fname}"'}
        # On retourne directement la StreamingResponse qui va itérer le streaming_body.read()
        return StreamingResponse(_streaming_body_iter(streaming_body, chunk_size=chunk_size),
                                 media_type=media_type,
                                 headers=headers)
    except (ClientError, BotoCoreError) as e:
        logger.exception("Erreur lors de la lecture de %s/%s depuis S3", bucket, key)
        raise RuntimeError(f"Erreur lors de la lecture de '{key}' dans '{bucket}': {e}") from e
    except Exception as e:
        logger.exception("Erreur inattendue get_object_stream")
        raise