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

# Reading client ID and secret from environment variables or secrets
CLIENT_ID = read_secret_from_file("MEDPLUM_CLIENT_ID")
CLIENT_SECRET = read_secret_from_file("MEDPLUM_CLIENT_SECRET")

# Base URL of the Medplum API
BASE_URL = os.getenv(
    "MEDPLUM_BASE_URL",
    "http://medplum-mesh.medplum.svc.cluster.local:8103",
).rstrip("/")

# Endpoint for getting the access token
TOKEN_ENDPOINT = os.getenv(
    "MEDPLUM_TOKEN_ENDPOINT",
    f"{BASE_URL}/oauth2/token",
)

# Default scope for the token
DEFAULT_SCOPE = os.getenv("MEDPLUM_SCOPE", "")

# Cache for storing access tokens
_token_cache: Dict[str, Tuple[str, float]] = {}
_cache_lock = threading.RLock()


class TokenError(RuntimeError):
    """Error when getting token OAuth2."""
    pass


ScopeInput = Union[str, Iterable[str], None]

# Function to normalize scope
def _normalize_scope(scope: ScopeInput) -> str:
    """
    Normalize string scope.
    - None -> DEFAULT_SCOPE
    - list/tuple/set -> "a b c"
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

# Function to check if token is valid
def _is_token_valid_for_scope(scope_key: str) -> bool:
    """Verify if token is valid."""
    token_entry = _token_cache.get(scope_key)
    if not token_entry:
        return False
    _, expires_at = token_entry
    return (time.time() + 10) < expires_at

# Function to decode base64
def _b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)

# Function to decode JWT
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

# Function to log token claims
def _log_token_claims_info(access_token: str) -> None:
    """Log token claims."""
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

# Function to fetch token
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

# Function to clear token cache
def clear_token_cache() -> None:
    """Used in debug."""
    with _cache_lock:
        _token_cache.clear()

# Function to get token
def get_token(scope: ScopeInput = DEFAULT_SCOPE, force_refresh: bool = False) -> str:
    """
    Return a valid access_token.
    Cache by scope.

    accepted scope values:
      - str
      - list/tuple/set
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
