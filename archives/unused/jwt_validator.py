import time
import requests
from jose import jwt
from jose.exceptions import JWTError
from fastapi import HTTPException, status

JWKS_URL = "http://medplum-mesh.medplum.svc.cluster.local:8103/.well-known/jwks.json"
EXPECTED_ISSUER = "https://app.phylcero.fr/api"
EXPECTED_AUDIENCE = "81b76561-9dad-43d7-a4ec-85942b5ee4cc"

# Cache simple en mémoire
_jwks_cache = {
    "keys": None,
    "expires_at": 0,
}

JWKS_CACHE_TTL = 300  # 5 minutes


def _get_jwks():
    now = time.time()

    # ✅ si cache valide → on ne touche pas au réseau
    if _jwks_cache["keys"] and now < _jwks_cache["expires_at"]:
        return _jwks_cache["keys"]

    try:
        response = requests.get(JWKS_URL, timeout=15)
        response.raise_for_status()
        jwks = response.json()

        _jwks_cache["keys"] = jwks
        _jwks_cache["expires_at"] = now + JWKS_CACHE_TTL

        return jwks

    except Exception as e:
        # ✅ si on a déjà un cache, on l'utilise même expiré
        if _jwks_cache["keys"]:
            return _jwks_cache["keys"]

        raise HTTPException(
            status_code=503,
            detail=f"JWKS unavailable: {str(e)}"
        )



def verify_token(token: str, required_scopes: list[str] | None = None):
    try:
        jwks = _get_jwks()

        payload = jwt.decode(
            token,
            jwks,
            algorithms=["ES256"],
            audience=EXPECTED_AUDIENCE,
            issuer=EXPECTED_ISSUER,
        )

    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
        )

    # ✅ Vérification des scopes
    if required_scopes:
        token_scopes = payload.get("scope", "")
        token_scopes_list = token_scopes.split()

        for scope in required_scopes:
            if scope not in token_scopes_list:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Missing required scope: {scope}",
                )

    return payload
