import os
import time
import json
import base64
import logging
from typing import Optional, Any, Dict, Tuple

import requests
from requests.auth import HTTPBasicAuth

from libs.secrets_utils import read_secret_from_file

logger = logging.getLogger("get_medplum_token")
logging.basicConfig(level=logging.INFO)


CLIENT_ID = read_secret_from_file("MEDPLUM_CLIENT_ID")
CLIENT_SECRET = read_secret_from_file("MEDPLUM_CLIENT_SECRET")

BASE_URL = os.getenv(
    "MEDPLUM_BASE_URL",
    "http://medplum-mesh.medplum.svc.cluster.local:8103"
)

TOKEN_ENDPOINT = os.getenv(
    "MEDPLUM_TOKEN_ENDPOINT",
    f"{BASE_URL}/oauth2/token"
)

DEFAULT_SCOPE = os.getenv("MEDPLUM_SCOPE", "")


_token_cache: Dict[str, Tuple[str, float]] = {}

class TokenError(RuntimeError):
    """Erreur lors de l'obtention du token OAuth2."""
    pass

def _is_token_valid_for_scope(scope: str) -> bool:
    """
    Vérifie si un token valide existe déjà pour ce scope.
    Ajoute une marge de sécurité de 10 secondes.
    """
    if scope not in _token_cache:
        return False

    _, expires_at = _token_cache[scope]
    return time.time() + 10 < expires_at


def _b64url_decode(data: str) -> bytes:
    """Décodage base64url avec gestion automatique du padding."""
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def _decode_jwt_no_verify(token: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Decode header & payload d’un JWT SANS vérifier la signature.
    Uniquement pour logging/debug.
    """
    parts = token.split(".")
    if len(parts) < 2:
        raise ValueError("Not a valid JWT")

    header = json.loads(_b64url_decode(parts[0]).decode("utf-8"))
    payload = json.loads(_b64url_decode(parts[1]).decode("utf-8"))
    return header, payload


def _log_token_claims_info(access_token: str) -> None:
    """
    Log informatif des claims utiles.
    Ne loggue jamais le token complet.
    """
    try:
        header, payload = _decode_jwt_no_verify(access_token)

        scope_str = payload.get("scope")
        scp = payload.get("scp")

        scopes: list[str] = []

        if isinstance(scope_str, str) and scope_str.strip():
            scopes.extend(scope_str.split())

        if isinstance(scp, list):
            scopes.extend([str(x) for x in scp if str(x).strip()])

        # Suppression des doublons (ordre conservé)
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
        logger.info("Could not decode JWT claims for logging: %s", e)


def _fetch_token_from_server(scope: str = DEFAULT_SCOPE) -> dict:
    """
    Appelle le endpoint OAuth2 pour récupérer un nouveau token.
    """
    if not CLIENT_ID or not CLIENT_SECRET:
        raise TokenError("MEDPLUM_CLIENT_ID / MEDPLUM_CLIENT_SECRET are missing")

    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }

    data = {
        "grant_type": "client_credentials"
    }

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
        logger.exception("Network error while requesting token")
        raise TokenError(f"Network error while requesting token: {e}") from e

    if resp.status_code != 200:
        logger.error("Token endpoint returned %s: %s", resp.status_code, resp.text)
        raise TokenError(
            f"Token endpoint returned {resp.status_code}: {resp.text}"
        )

    try:
        token_json = resp.json()
    except ValueError:
        raise TokenError("Token endpoint returned non-JSON response")

    if "access_token" not in token_json:
        raise TokenError("No access_token in token response")

    return token_json


def get_token(scope: str = DEFAULT_SCOPE, force_refresh: bool = False) -> str:
    """
    Retourne un access_token valide.
    Le cache est géré PAR SCOPE.
    """

    if not scope:
        scope = DEFAULT_SCOPE

    # 1️⃣ Vérifier cache pour CE scope
    if not force_refresh and _is_token_valid_for_scope(scope):
        token, _ = _token_cache[scope]
        logger.debug("Returning cached token for scope=%r", scope)
        return token

    # 2️⃣ Sinon récupérer un nouveau token
    token_json = _fetch_token_from_server(scope=scope)

    access_token = token_json.get("access_token")
    expires_in = int(token_json.get("expires_in", 3600))

    if not access_token:
        raise TokenError("Empty access_token in token response")

    expires_at = time.time() + expires_in

    # 3️⃣ Stocker dans le cache par scope
    _token_cache[scope] = (access_token, expires_at)

    logger.info(
        "Fetched new token for scope=%r (expires in %s seconds)",
        scope,
        expires_in,
    )

    _log_token_claims_info(access_token)

    return access_token


if __name__ == "__main__":
    try:
        tk = get_token()
        print("OK token:", tk[:40] + "..." if tk else "NO_TOKEN")
    except TokenError as e:
        logger.error("Cannot obtain token: %s", e)
        raise
