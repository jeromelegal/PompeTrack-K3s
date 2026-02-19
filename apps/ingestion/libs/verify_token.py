# libs/verify_token.py
import os
import time
import logging
import urllib.request
import json
from libs.secrets_utils import read_secret_from_file
import jwt
from jwt.algorithms import ECAlgorithm

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────────────

JWKS_URL = os.getenv(
    "JWKS_URL",
    "http://medplum-mesh.medplum.svc.cluster.local:8103/.well-known/jwks.json",
)
TOKEN_ISSUER = os.getenv("TOKEN_ISSUER", "https://app.phylcero.fr/api")

TOKEN_AUDIENCE_WORKER_FHIR = os.getenv("TOKEN_AUDIENCE_WORKER_FHIR", None)
TOKEN_AUDIENCE_STREAMLIT = os.getenv("TOKEN_AUDIENCE_STREAMLIT", None)
TOKEN_AUDIENCE_WORKER_SQLITE = os.getenv("TOKEN_AUDIENCE_WORKER_SQLITE", None)

JWKS_CACHE_TTL = int(os.getenv("JWKS_CACHE_TTL", "300"))  # 5 min

# ── Audiences autorisées ─────────────────────────────────────────────────────

VALID_AUDIENCES = [
    aud for aud in [
        TOKEN_AUDIENCE_WORKER_FHIR,
        TOKEN_AUDIENCE_STREAMLIT,
        TOKEN_AUDIENCE_WORKER_SQLITE,
    ]
    if aud is not None
]

if not VALID_AUDIENCES:
    logger.warning("No TOKEN_AUDIENCE_* configured — audience verification disabled!")

# ── Exceptions ───────────────────────────────────────────────────────────────

class InsufficientScopeError(Exception):
    """Token valide mais scope insuffisant."""
    pass

# ── Cache JWKS ───────────────────────────────────────────────────────────────

_jwks_cache: dict = {}
_jwks_cache_ts: float = 0.0

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
    global _jwks_cache_ts

    keys = _get_jwks()

    if kid not in keys:
        logger.warning("kid=%s not in cache, forcing JWKS refresh", kid)
        _jwks_cache_ts = 0.0
        keys = _get_jwks()

    if kid not in keys:
        raise ValueError(f"Public key not found for kid={kid}")

    return keys[kid]

# ── Vérification du token ────────────────────────────────────────────────────

def verify_token(token: str, required_scope: str | None = None) -> dict:
    """
    Vérifie un JWT signé ES256.

    Args:
        token:          Le JWT brut (Bearer token)
        required_scope: Scope attendu (ex: "ingest:fhir"). Si fourni,
                        lève InsufficientScopeError si absent du token.

    Returns:
        dict: payload décodé

    Raises:
        jwt.PyJWTError:        signature invalide, token expiré, issuer incorrect...
        ValueError:            kid introuvable
        RuntimeError:          JWKS inaccessible
        InsufficientScopeError: token valide mais scope insuffisant
    """
    # 1. Récupérer le kid depuis l'en-tête
    unverified_header = jwt.get_unverified_header(token)
    kid = unverified_header.get("kid")

    if not kid:
        raise ValueError("Token header missing 'kid'")

    public_key = _get_public_key(kid)

    # 2. Vérifier signature, issuer, audience, expiration
    decode_kwargs = dict(
        algorithms=["ES256"],
        issuer=TOKEN_ISSUER,
        options={"verify_exp": True},
    )

    if VALID_AUDIENCES:
        decode_kwargs["audience"] = VALID_AUDIENCES
    else:
        decode_kwargs["options"]["verify_aud"] = False

    payload = jwt.decode(token, public_key, **decode_kwargs)

    # 3. Vérifier le scope si demandé
    if required_scope is not None:
        token_scopes = payload.get("scope", "").split()
        if required_scope not in token_scopes:
            logger.warning(
                "Insufficient scope: required=%s granted=%s sub=%s",
                required_scope,
                token_scopes,
                payload.get("sub"),
            )
            raise InsufficientScopeError(
                f"Required scope '{required_scope}' not granted (got: {token_scopes})"
            )

    logger.debug(
        "Token verified for sub=%s scope=%s",
        payload.get("sub"),
        payload.get("scope"),
    )
    return payload
