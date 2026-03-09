# libs/security.py

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Callable, List, Dict, Any
import logging

import jwt

from libs.verify_token import verify_token, InsufficientScopeError

logger = logging.getLogger(__name__)

bearer = HTTPBearer(auto_error=False)

LIGHT_JWT_SECRET = os.getenv("LIGHT_JWT_SECRET")
if not LIGHT_JWT_SECRET:
    raise RuntimeError("LIGHT_JWT_SECRET is not set")

# ── Helpers ──────────────────────────────────────────────────────────────────

def _extract_scopes(payload: Dict[str, Any]) -> List[str]:
    """Extrait les scopes depuis 'scope' (str ou list) ou 'scp' (list)."""
    scopes: List[str] = []

    scope_field = payload.get("scope")
    if isinstance(scope_field, str) and scope_field.strip():
        scopes.extend(scope_field.split())
    elif isinstance(scope_field, list): 
        scopes.extend([str(x) for x in scope_field if str(x).strip()])

    scp = payload.get("scp")
    if isinstance(scp, list):
        scopes.extend([str(x) for x in scp if str(x).strip()])

    # de-dup stable
    seen = set()
    return [s for s in scopes if not (s in seen or seen.add(s))]



def _extract_caller(payload: Dict[str, Any]) -> str:
    """Extrait l'identité du client depuis le payload."""
    return (
        payload.get("client_id")
        or payload.get("azp")
        or payload.get("sub")
        or "unknown-client"
    )

# ── Dépendance principale ─────────────────────────────────────────────────────

def require_scopes(required: List[str]) -> Callable:
    """
    Dépendance FastAPI qui vérifie le token Bearer et les scopes requis.

    Usage :
        # Cas 1 : protéger la route uniquement
        @app.post("/route", dependencies=[Depends(require_scopes(["ingest:fhir"]))])
        def my_route(): ...

        # Cas 2 : protéger ET accéder au contexte
        @app.post("/route")
        def my_route(ctx: dict = Depends(require_scopes(["ingest:fhir"]))):
            print(ctx["device"])   # identité du client
            print(ctx["scopes"])   # scopes accordés
    """
    def _dep(
        creds: HTTPAuthorizationCredentials = Depends(bearer),
    ) -> Dict[str, Any]:

        # 1. Vérifier la présence du token
        if creds is None or creds.scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Missing Bearer token")

        token = creds.credentials

        # 2. Vérifier la signature, l'expiration, l'issuer, l'audience
        try:
            payload = verify_token(token)
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.InvalidIssuerError:
            raise HTTPException(status_code=401, detail="Invalid token issuer")
        except jwt.InvalidAudienceError:
            raise HTTPException(status_code=401, detail="Invalid token audience")
        except (jwt.PyJWTError, ValueError, RuntimeError) as exc:
            logger.warning("Token verification failed: %s", exc)
            raise HTTPException(status_code=401, detail="Invalid token")
        except InsufficientScopeError as exc:
            raise HTTPException(status_code=403, detail=str(exc))

        # 3. Vérifier les scopes
        token_scopes = set(_extract_scopes(payload))
        missing = [s for s in required if s not in token_scopes]
        if missing:
            logger.warning(
                "Missing scopes: required=%s granted=%s device=%s",
                required,
                sorted(token_scopes),
                _extract_caller(payload),
            )
            raise HTTPException(status_code=403, detail=f"Missing scopes: {missing}")

        # 4. Retourner le contexte enrichi
        return {
            "device": _extract_caller(payload),
            "scopes": sorted(token_scopes),
            "sub":    payload.get("sub"),
            "payload": payload,  # accès complet si besoin
        }

    return _dep

def require_scopes_light(required: List[str]) -> Callable:
    """
    Version light de require_scopes pour devices sans mTLS.
    Utilise un JWT fixe signé HS256 avec un secret partagé.
    Pas d'expiration, mais signature et scopes vérifiés.
    """
    def _dep(
        creds: HTTPAuthorizationCredentials = Depends(bearer),
    ) -> Dict[str, Any]:

        # 1. Vérifier la présence du token
        if creds is None or creds.scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Missing Bearer token")

        token = creds.credentials

        # 2. Vérifier la signature avec le secret partagé
        try:
            payload = jwt.decode(
                token,
                LIGHT_JWT_SECRET,      # lu depuis variable d'env
                algorithms=["HS256"],
                options={
                    "verify_exp": False,   # pas d'expiration
                },
            )
        except jwt.InvalidSignatureError:
            raise HTTPException(status_code=401, detail="Invalid token signature")
        except jwt.PyJWTError as exc:
            logger.warning("Light token verification failed: %s", exc)
            raise HTTPException(status_code=401, detail="Invalid token")

        # 3. Vérifier les scopes
        token_scopes = set(payload.get("scopes", []))
        missing = [s for s in required if s not in token_scopes]
        if missing:
            logger.warning(
                "Light - Missing scopes: required=%s granted=%s device=%s",
                required,
                sorted(token_scopes),
                payload.get("sub", "unknown"),
            )
            raise HTTPException(status_code=403, detail=f"Missing scopes: {missing}")

        # 4. Retourner le contexte enrichi
        return {
            "device": payload.get("sub", "unknown"),
            "scopes": sorted(token_scopes),
            "sub":    payload.get("sub"),
            "payload": payload,
        }

    return _dep