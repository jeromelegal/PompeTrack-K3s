# libs/verify_token.py
import os
import time
import logging
import urllib.request
import json

import jwt
from jwt.algorithms import ECAlgorithm

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────────────

JWKS_URL = os.environ.get(
    "JWKS_URL",
    "http://medplum-mesh.medplum.svc.cluster.local:8103/.well-known/jwks.json",
)
TOKEN_ISSUER = os.environ.get("TOKEN_ISSUER", "https://app.phylcero.fr/api")
TOKEN_AUDIENCE = os.environ.get("TOKEN_AUDIENCE", None)  # None = désactivé

JWKS_CACHE_TTL = int(os.environ.get("JWKS_CACHE_TTL", "300"))  # 5 min

# ── Cache JWKS ───────────────────────────────────────────────────────────────

_jwks_cache: dict = {}        # kid → clé publique
_jwks_cache_ts: float = 0.0   # timestamp du dernier fetch


def _fetch_jwks() -> dict:
    """Récupère les clés publiques depuis le JWKS endpoint."""
    logger.debug("Fetching JWKS from %s", JWKS_URL)
    try:
        with urllib.request.urlopen(JWKS_URL, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Cannot fetch JWKS from {JWKS_URL}: {exc}") from exc

    keys = {}
    for jwk in data.get("keys", []):
        kid = jwk.get("kid")
        if not kid:
            continue
        keys[kid] = ECAlgorithm.from_jwk(json.dumps(jwk))
        logger.debug("Loaded public key kid=%s", kid)

    if not keys:
        raise RuntimeError("JWKS response contains no usable keys")

    return keys


def _get_jwks() -> dict:
    """Retourne les clés JWKS (depuis le cache ou en refetchant)."""
    global _jwks_cache, _jwks_cache_ts

    if time.monotonic() - _jwks_cache_ts > JWKS_CACHE_TTL or not _jwks_cache:
        _jwks_cache = _fetch_jwks()
        _jwks_cache_ts = time.monotonic()
        logger.info("JWKS cache refreshed (%d key(s))", len(_jwks_cache))

    return _jwks_cache


def _get_public_key(kid: str):
    """Retourne la clé publique correspondant au kid."""
    keys = _get_jwks()

    if kid not in keys:
        # On tente un refresh forcé (rotation de clé possible)
        logger.warning("kid=%s not in cache, forcing JWKS refresh", kid)
        global _jwks_cache_ts
        _jwks_cache_ts = 0.0
        keys = _get_jwks()

    if kid not in keys:
        raise ValueError(f"Public key not found for kid={kid}")

    return keys[kid]


# ── Vérification du token ────────────────────────────────────────────────────

def verify_token(token: str) -> dict:
    """
    Vérifie un JWT signé ES256.

    Returns:
        dict: payload décodé

    Raises:
        jwt.PyJWTError: signature invalide, token expiré, issuer incorrect...
        ValueError: kid introuvable
        RuntimeError: JWKS inaccessible
    """
    # Décoder l'en-tête sans vérification pour récupérer le kid
    unverified_header = jwt.get_unverified_header(token)
    kid = unverified_header.get("kid")

    if not kid:
        raise ValueError("Token header missing 'kid'")

    public_key = _get_public_key(kid)

    decode_kwargs = dict(
        algorithms=["ES256"],
        issuer=TOKEN_ISSUER,
        options={"verify_exp": True},
    )
    if TOKEN_AUDIENCE:
        decode_kwargs["audience"] = TOKEN_AUDIENCE

    payload = jwt.decode(token, public_key, **decode_kwargs)
    logger.debug("Token verified for sub=%s", payload.get("sub"))
    return payload
