# libs/get_medplum_token.py

import os
import time
import json
import base64
import logging
from typing import Optional, Any, Dict, Tuple, List

import requests
from requests.auth import HTTPBasicAuth

from libs.secrets_utils import read_secret_from_file

logger = logging.getLogger("get_medplum_token")
logging.basicConfig(level=logging.INFO)

# ── Configuration ────────────────────────────────────────────────────────────

CLIENT_ID = read_secret_from_file("MEDPLUM_CLIENT_ID")
CLIENT_SECRET = read_secret_from_file("MEDPLUM_CLIENT_SECRET")

BASE_URL = os.getenv("MEDPLUM_BASE_URL", "http://medplum-mesh.medplum.svc.cluster.local:8103")
TOKEN_ENDPOINT = os.getenv("MEDPLUM_TOKEN_ENDPOINT", f"{BASE_URL}/oauth2/token")

DEFAULT_SCOPE = os.getenv("MEDPLUM_SCOPE", "")

_token_cache: Dict[str, Tuple[str, float]] = {}

class TokenError(RuntimeError):
    pass

def _safe_cache() -> Dict[str, Tuple[str, float]]:
    """
    Retourne le cache, le réinitialise si jamais il est corrompu (None ou autre).
    C'est une protection défensive contre d'éventuels restes d'ancien code.
    """
    global _token_cache
    if not isinstance(_token_cache, dict):
        logger.error(f"BUG: _token_cache était {type(_token_cache).__name__}, reset à {{}}")
        _token_cache = {}
    return _token_cache

def _is_token_valid_for_scope(scope: str) -> bool:
    """Vérifie si on a un token valide pour ce scope spécifique."""
    cache = _safe_cache()
    if scope not in cache:
        return False
    _, expires_at = cache[scope]
    return time.time() + 10 < expires_at

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

def _log_token_claims_info(access_token: str) -> None:
    try:
        header, payload = _decode_jwt_no_verify(access_token)
        scope_str = payload.get("scope", "")
        scp = payload.get("scp", [])
        scopes = list(dict.fromkeys(  # de-dup preserve order
            scope_str.split() if isinstance(scope_str, str) else [] + 
            [str(x) for x in scp if isinstance(scp, list)]
        ))
        logger.info("Token scopes: %s | sub=%s | exp=%s", scopes, payload.get("sub"), payload.get("exp"))
    except Exception as e:
        logger.debug("Could not decode JWT for logging: %s", e)

def _fetch_token_from_server(scope: str = DEFAULT_SCOPE) -> dict:
    if not CLIENT_ID or not CLIENT_SECRET:
        raise TokenError("MEDPLUM_CLIENT_ID / MEDPLUM_CLIENT_SECRET are missing")

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
    except requests.RequestException as e:
        raise TokenError(f"Network error: {e}") from e

    if resp.status_code != 200:
        raise TokenError(f"HTTP {resp.status_code}: {resp.text}")

    return resp.json()

def get_token(scope: str = DEFAULT_SCOPE, force_refresh: bool = False) -> str:
    """
    Return a valid access token (cached per scope).
    """
    cache = _safe_cache()  # Utilise toujours cette fonction pour accéder au cache
    
    # 1. Vérifier le cache
    if not force_refresh and _is_token_valid_for_scope(scope):
        token, _ = cache[scope]
        logger.debug("Cache hit for scope=%r", scope)
        return token

    # 2. Fetch nouveau token
    token_json = _fetch_token_from_server(scope=scope)
    access_token = token_json.get("access_token")
    expires_in = int(token_json.get("expires_in", 3600))

    if not access_token:
        raise TokenError("Empty access_token")

    # 3. Stocker dans le cache (mutation, pas réassignation !)
    cache[scope] = (access_token, time.time() + expires_in)

    logger.info("New token fetched for scope=%r (expires in %ss)", scope, expires_in)
    _log_token_claims_info(access_token)

    return access_token

if __name__ == "__main__":
    try:
        tk1 = get_token("ingest:iphone")
        print(f"iPhone: {tk1[:20]}...")
        tk2 = get_token("ingest:sqlite")
        print(f"SQLite: {tk2[:20]}...")
        print("Différents?" , tk1 != tk2)
    except TokenError as e:
        logger.error("Fail: %s", e)
        raise
