import os
import time
import logging
from typing import Optional
from libs.secrets_utils import read_secret_from_file

import requests

logger = logging.getLogger("get_medplum_token")
logging.basicConfig(level=logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s - %(message)s"))
    logger.addHandler(ch)

CLIENT_ID = read_secret_from_file("CLIENT_ID_FILE", "CLIENT_ID")
CLIENT_SECRET = read_secret_from_file("CLIENT_SECRET_FILE", "CLIENT_SECRET")
BASE_URL = os.getenv("MEDPLUM_BASE_URL", "http://medplum-mesh.medplum.svc.cluster.local:8103")
TOKEN_ENDPOINT = os.getenv("MEDPLUM_TOKEN_ENDPOINT", f"{BASE_URL}/oauth2/token")
DEFAULT_SCOPE = os.getenv("MEDPLUM_SCOPE", "system/*.*")

_cached_token: Optional[str] = None
_token_expires_at: Optional[float] = None

class TokenError(RuntimeError):
    pass

def _is_token_valid() -> bool:
    global _cached_token, _token_expires_at
    if not _cached_token or not _token_expires_at:
        return False
    # small safety margin 10s
    return time.time() + 10 < _token_expires_at

def _fetch_token_from_server(scope: str = DEFAULT_SCOPE) -> dict:
    if not CLIENT_ID or not CLIENT_SECRET:
        raise TokenError("WORKER_ID and WORKER_SECRET must be set in environment")

    data = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": scope
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    try:
        logger.debug("Requesting token from", TOKEN_ENDPOINT)
        resp = requests.post(TOKEN_ENDPOINT, headers=headers, data=data)
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
    Return a valid access token (cached in memory). Raises TokenError on failure.
    """
    global _cached_token, _token_expires_at

    if not force_refresh and _is_token_valid():
        logger.debug("Returning cached token (valid until %s)", _token_expires_at)
        return _cached_token  # type: ignore

    token_json = _fetch_token_from_server(scope=scope)

    access_token = token_json.get("access_token")
    expires_in = int(token_json.get("expires_in", 3600))
    # set expiry with small safety margin
    _token_expires_at = time.time() + expires_in

    _cached_token = access_token
    logger.info("Fetched new access token, expires in %s seconds", expires_in)
    return access_token

if __name__ == "__main__":
    try:
        tk = get_token()
        print("OK token:", tk[:40] + "..." if tk else "NO_TOKEN")
    except TokenError as e:
        logger.error("Cannot obtain token: %s", e)
        raise