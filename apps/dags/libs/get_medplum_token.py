import os
import time
import json
import base64
import logging
import threading
from typing import Any, Dict, Optional, Tuple, Iterable, Union

import requests
from requests.auth import HTTPBasicAuth

from libs.secrets_utils import read_secret_from_file

logger = logging.getLogger("get_medplum_token")

CLIENT_ID = os.getenv("MEDPLUM_CLIENT_ID")
CLIENT_SECRET = os.getenv("MEDPLUM_CLIENT_SECRET")

BASE_URL = "http://medplum-mesh.medplum.svc.cluster.local:8103"

TOKEN_ENDPOINT = os.getenv(
    "MEDPLUM_TOKEN_ENDPOINT",
    f"{BASE_URL}/oauth2/token",
)

DEFAULT_SCOPE = os.getenv("MEDPLUM_SCOPE", "")

# scope_string -> (access_token, expires_at)
_token_cache: Dict[str, Tuple[str, float]] = {}
_cache_lock = threading.RLock()


class TokenError(RuntimeError):
    """Erreur lors de l'obtention du token OAuth2."""
    pass


ScopeInput = Union[str, Iterable[str], None]


def _normalize_scope(scope: ScopeInput) -> str:
    """
    Normalise le scope en string (clé de cache stable).
    - None -> DEFAULT_SCOPE
    - list/tuple/set -> "a b c" (trié, dédoublonné)
    - str -> str
    """
    if scope is None:
        scope = DEFAULT_SCOPE

    if isinstance(scope, str):
        return scope.strip()

    # Iterable[str] (list/tuple/set/...) -> string stable
    try:
        items = [str(s).strip() for s in scope if str(s).strip()]
    except TypeError as e:
        raise TokenError(f"Invalid scope type: {type(scope)}") from e

    # stable: de-dup + sort
    uniq = sorted(set(items))
    return " ".join(uniq).strip()


def _is_token_valid_for_scope(scope_key: str) -> bool:
    """Vérifie si on a un token non-expiré pour ce scope (marge 10s)."""
    token_entry = _token_cache.get(scope_key)
    if not token_entry:
        return False
    _, expires_at = token_entry
    return (time.time() + 10) < expires_at


def _b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def _decode_jwt_no_verify(token: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Decode JWT header/payload WITHOUT verifying signature.
    For logging/debug only.
    """
    parts = token.split(".")
    if len(parts) < 2:
        raise ValueError("Not a JWT (expected at least 2 dot-separated parts)")

    header = json.loads(_b64url_decode(parts[0]).decode("utf-8"))
    payload = json.loads(_b64url_decode(parts[1]).decode("utf-8"))
    return header, payload


def _log_token_claims_info(access_token: str) -> None:
    """Log best-effort des infos utiles sans jamais logger le token complet."""
    try:
        header, payload = _decode_jwt_no_verify(access_token)

        scope_str = payload.get("scope")
        scp = payload.get("scp")

        scopes: list[str] = []
        if isinstance(scope_str, str) and scope_str.strip():
            scopes.extend(scope_str.split())
        if isinstance(scp, list):
            scopes.extend([str(x) for x in scp if str(x).strip()])

        # de-dup (ordre conservé)
        seen = set()
        scopes = [s for s in scopes if not (s in seen or seen.add(s))]

        logger.info(
            "Medplum token claims: iss=%s aud=%s sub=%s exp=%s scopes=%s",
            payload.get("iss"),
            payload.get("aud"),
            payload.get("sub"),
            payload.get("exp"),
            scopes,
        )
        logger.info(
            "Medplum token header: alg=%s kid=%s",
            header.get("alg"),
            header.get("kid"),
        )
    except Exception as e:
        logger.debug("Could not decode JWT claims (non-fatal): %s", e)


def _fetch_token_from_server(scope_key: str) -> dict:
    if not CLIENT_ID or not CLIENT_SECRET:
        raise TokenError("MEDPLUM_CLIENT_ID / MEDPLUM_CLIENT_SECRET are missing")

    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    data = {"grant_type": "client_credentials"}
    if scope_key:
        data["scope"] = scope_key

    try:
        resp = requests.post(
            TOKEN_ENDPOINT,
            headers=headers,
            data=data,
            auth=HTTPBasicAuth(CLIENT_ID, CLIENT_SECRET),
            timeout=10,
        )
    except requests.RequestException as e:
        raise TokenError(f"Network error while requesting token: {e}") from e

    if resp.status_code != 200:
        raise TokenError(f"Token endpoint returned {resp.status_code}: {resp.text}")

    try:
        token_json = resp.json()
    except ValueError as e:
        raise TokenError("Token endpoint returned non-JSON response") from e

    if "access_token" not in token_json:
        raise TokenError(f"No access_token in token response: {token_json}")

    return token_json


def clear_token_cache() -> None:
    """Utile en debug/tests."""
    with _cache_lock:
        _token_cache.clear()


def get_token(scope: ScopeInput = DEFAULT_SCOPE, force_refresh: bool = False) -> str:
    """
    Retourne un access_token valide.
    Cache par scope normalisé.

    scope accepte:
      - str
      - list/tuple/set de str
      - None
    """
    scope_key = _normalize_scope(scope)

    with _cache_lock:
        if not force_refresh and _is_token_valid_for_scope(scope_key):
            token, _ = _token_cache[scope_key]
            logger.debug("Returning cached token for scope=%r", scope_key)
            return token

    token_json = _fetch_token_from_server(scope_key=scope_key)
    access_token = token_json.get("access_token")
    expires_in = int(token_json.get("expires_in", 3600))

    if not access_token:
        raise TokenError("Empty access_token in token response")

    expires_at = time.time() + expires_in

    with _cache_lock:
        _token_cache[scope_key] = (access_token, expires_at)

    logger.info("Fetched new token for scope=%r (expires_in=%ss)", scope_key, expires_in)
    _log_token_claims_info(access_token)

    return access_token


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    tk = get_token()
    print("OK token:", tk[:40] + "..." if tk else "NO_TOKEN")
