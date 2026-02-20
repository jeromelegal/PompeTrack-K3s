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

# ── Cache par scope (défensif) ───────────────────────────────────────────────
# Structure: {scope_string: (access_token, expires_at_timestamp)}
# Initialisé ici, mais on vérifie sa validité dans les fonctions au cas où
_token_cache: Optional[Dict[str, Tuple[str, float]]] = {}

class TokenError(RuntimeError):
    pass

def _ensure_cache_initialized() -> None:
    """Vérifie que le cache est un dict, le recrée si None (défensif)."""
    global _token_cache
    if _token_cache is None:
        logger.warning("_token_cache was None, reinitializing to empty dict")
        _token_cache = {}

def _is_token_valid_for_scope(scope: str) -> bool:
    """Vérifie si on a un token valide pour ce scope spécifique."""
    global _token_cache
    _ensure_cache_initialized()
    
    if scope not in _token_cache:
        return False
    _, expires_at = _token_cache[scope]
    # Marge de 10 secondes pour éviter d'utiliser un token quasi-expiré
    return time.time() + 10 < expires_at

def _b64url_decode(data: str) -> bytes:
    # base64url padding
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)

def _decode_jwt_no_verify(token: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Decode JWT header/payload WITHOUT verifying signature.
    Only for debugging/logging purposes.
    """
    parts = token.split(".")
    if len(parts) < 2:
        raise ValueError("Not a JWT (expected at least 2 dot-separated parts)")

    header_b = _b64url_decode(parts[0])
    payload_b = _b64url_decode(parts[1])

    header = json.loads(header_b.decode("utf-8"))
    payload = json.loads(payload_b.decode("utf-8"))
    return header, payload

def _log_token_claims_info(access_token: str) -> None:
    """
    INFO logs: scopes and a few standard claims (best-effort).
    Never logs the full token.
    """
    try:
        header, payload = _decode_jwt_no_verify(access_token)

        scope_str = payload.get("scope")
        scp = payload.get("scp")

        scopes: List[str] = []
        if isinstance(scope_str, str) and scope_str.strip():
            scopes.extend(scope_str.split())
        if isinstance(scp, list):
            scopes.extend([str(x) for x in scp if str(x).strip()])

        # de-dup while preserving order
        seen = set()
        scopes = [s for s in scopes if not (s in seen or seen.add(s))]

        iss = payload.get("iss")
        aud = payload.get("aud")
        sub = payload.get("sub")
        exp = payload.get("exp")

        logger.info(
            "Medplum token claims: iss=%s aud=%s sub=%s exp=%s scopes=%s",
            iss, aud, sub, exp, scopes
        )

        # (optionnel) algo / kid utiles en debug infra
        alg = header.get("alg")
        kid = header.get("kid")
        logger.info("Medplum token header: alg=%s kid=%s", alg, kid)

    except Exception as e:
        logger.info("Could not decode JWT claims for logging: %s", e)

def _fetch_token_from_server(scope: str = DEFAULT_SCOPE) -> dict:
    if not CLIENT_ID or not CLIENT_SECRET:
        raise TokenError("MEDPLUM_CLIENT_ID / MEDPLUM_CLIENT_SECRET are missing")

    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    data = {"grant_type": "client_credentials"}
    if scope:
        data["scope"] = scope

    try:
        logger.debug("Requesting token from %s (scope=%r)", TOKEN_ENDPOINT, scope)
        resp = requests.post(
            TOKEN_ENDPOINT,
            headers=headers,
            data=data,
            auth=HTTPBasicAuth(CLIENT_ID, CLIENT_SECRET),
            timeout=10,
        )
    except requests.RequestException as e:
        logger.exception("Network error while requesting token: %s", e)
        raise TokenError(f"Network error while requesting token: {e}") from e

    if resp.status_code != 200:
        logger.error("Token endpoint returned %s: %s", resp.status_code, resp.text)
        raise TokenError(f"Token endpoint returned {resp.status_code}: {resp.text}")

    try:
        token_json = resp.json()
    except ValueError:
        logger.error("Token endpoint returned non-JSON: %s", resp.text)
        raise TokenError("Token endpoint returned non-JSON response")

    if "access_token" not in token_json:
        logger.error("No access_token in response: %s", token_json)
        raise TokenError("No access_token in token response")

    return token_json

def get_token(scope: str = DEFAULT_SCOPE, force_refresh: bool = False) -> str:
    """
    Return a valid access token (cached per scope).
    """
    global _token_cache
    _ensure_cache_initialized()
    
    # 1. Vérifier le cache spécifique à ce scope
    if not force_refresh and _is_token_valid_for_scope(scope):
        token, _ = _token_cache[scope]
        logger.debug("Returning cached token for scope=%r", scope)
        return token

    # 2. Sinon, fetch nouveau token auprès du serveur
    token_json = _fetch_token_from_server(scope=scope)
    access_token = token_json.get("access_token")
    expires_in = int(token_json.get("expires_in", 3600))

    if not access_token:
        raise TokenError("Empty access_token in token response")

    # 3. Stocker dans le cache avec la clé = scope
    _token_cache[scope] = (access_token, time.time() + expires_in)

    logger.info("Fetched new token for scope=%r, expires in %s seconds", scope, expires_in)
    _log_token_claims_info(access_token)

    return access_token

if __name__ == "__main__":
    try:
        # Test rapide : demande deux tokens différents pour vérifier le cache
        print("Test 1 - scope 'ingest:iphone':")
        tk1 = get_token("ingest:iphone")
        print("OK token:", tk1[:40] + "...")
        
        print("\nTest 2 - scope 'ingest:sqlite':")
        tk2 = get_token("ingest:sqlite")
        print("OK token:", tk2[:40] + "...")
        
        # Vérifier qu'on a bien deux tokens différents (ou pas si le serveur retourne le même)
        if tk1 == tk2:
            print("\n⚠️  Les deux tokens sont identiques (le serveur les a peut-être fusionnés)")
        else:
            print("\n✓ Deux tokens distincts en cache")
            
    except TokenError as e:
        logger.error("Cannot obtain token: %s", e)
        raise
