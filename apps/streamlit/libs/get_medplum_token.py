import os
import time
import json
import base64
import logging
import threading
from typing import Optional, Any, Dict, Tuple, List

import requests
from requests.auth import HTTPBasicAuth

from libs.secrets_utils import read_secret_from_file

logger = logging.getLogger("get_medplum_token")
logging.basicConfig(level=logging.INFO)

# ── Configuration (immutable) ─────────────────────────────────────────────────
CLIENT_ID = read_secret_from_file("MEDPLUM_CLIENT_ID")
CLIENT_SECRET = read_secret_from_file("MEDPLUM_CLIENT_SECRET")
BASE_URL = os.getenv("MEDPLUM_BASE_URL", "http://medplum-mesh.medplum.svc.cluster.local:8103")
TOKEN_ENDPOINT = os.getenv("MEDPLUM_TOKEN_ENDPOINT", f"{BASE_URL}/oauth2/token")
DEFAULT_SCOPE = os.getenv("MEDPLUM_SCOPE", "")

class TokenError(RuntimeError):
    pass

# ── Helpers JWT ──────────────────────────────────────────────────────────────
def _b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)

def _decode_jwt_no_verify(token: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    parts = token.split(".")
    if len(parts) < 2:
        raise ValueError("Not a JWT")
    header = json.loads(_b64url_decode(parts[0]).decode("utf-8"))
    payload = json.loads(_b64url_decode(parts[1]).decode("utf-8"))
    return header, payload

def _log_token_claims(access_token: str) -> None:
    try:
        _, payload = _decode_jwt_no_verify(access_token)
        scope_str = payload.get("scope", "")
        scopes = scope_str.split() if isinstance(scope_str, str) else []
        logger.info("Token scopes: %s | sub=%s", scopes, payload.get("sub"))
    except Exception:
        pass

# ── Fetch depuis Medplum ────────────────────────────────────────────────────
def _fetch_token(scope: str) -> Tuple[str, int]:
    if not CLIENT_ID or not CLIENT_SECRET:
        raise TokenError("Missing MEDPLUM_CLIENT_ID or MEDPLUM_CLIENT_SECRET")
    
    data = {"grant_type": "client_credentials"}
    if scope:
        data["scope"] = scope
    
    try:
        resp = requests.post(
            TOKEN_ENDPOINT,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data=data,
            auth=HTTPBasicAuth(CLIENT_ID, CLIENT_SECRET),
            timeout=10,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        raise TokenError(f"Network error: {e}") from e
    
    token_json = resp.json()
    access_token = token_json.get("access_token")
    expires_in = int(token_json.get("expires_in", 3600))
    
    if not access_token:
        raise TokenError("No access_token in response")
    
    return access_token, expires_in

# ── Fonction principale (cache intégré) ───────────────────────────────────────
def get_token(scope: str = DEFAULT_SCOPE, force_refresh: bool = False) -> str:
    """
    Return a valid access token (cached per scope).
    Cache stored as function attribute - no global variables.
    """
    # BULLETPROOF: Initialise le cache sur la fonction si inexistant ou corrompu
    if not hasattr(get_token, "_cache") or not isinstance(get_token._cache, dict):
        get_token._cache = {}  # {scope: (token, expires_at)}
        get_token._cache_lock = threading.Lock()
    
    cache = get_token._cache
    lock = get_token._cache_lock
    
    with lock:  # Thread-safe
        # Vérifier cache existant
        if not force_refresh and scope in cache:
            token, expires_at = cache[scope]
            if time.time() + 10 < expires_at:  # Marge 10s
                logger.debug("Cache HIT for scope=%r", scope)
                return token
        
        # Fetch nouveau token
        logger.info("Cache MISS - fetching new token for scope=%r", scope)
        access_token, expires_in = _fetch_token(scope)
        
        # Stocker
        cache[scope] = (access_token, time.time() + expires_in)
    
    _log_token_claims(access_token)
    return access_token

if __name__ == "__main__":
    try:
        t1 = get_token("ingest:iphone")
        print(f"iPhone: {t1[:20]}...")
        t2 = get_token("ingest:sqlite")
        print(f"SQLite: {t2[:20]}...")
        t3 = get_token("ingest:iphone")  # Devrait être cache hit
        print(f"iPhone again: {t3[:20]}... (should be same)")
        print(f"Different tokens: {t1 != t2}")
    except Exception as e:
        logger.error("FAIL: %s", e)
        raise
