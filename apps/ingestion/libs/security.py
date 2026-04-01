# libs/security.py

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Callable, List, Dict, Any
import logging
import os

import jwt

from libs.verify_token import verify_token, InsufficientScopeError

logger = logging.getLogger(__name__)

bearer = HTTPBearer(auto_error=False)

################## Only for 'ingestion' #######################################
LIGHT_JWT_SECRET = os.getenv("LIGHT_JWT_SECRET")
if not LIGHT_JWT_SECRET:
    raise RuntimeError("LIGHT_JWT_SECRET is not set")
###############################################################################

# Function _extract_scopes
def _extract_scopes(payload: Dict[str, Any]) -> List[str]:
    """Extracts scopes from 'scope' (str or list) or 'scp' (list)."""
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


# Function _extract_caller
def _extract_caller(payload: Dict[str, Any]) -> str:
    """Extracts caller from 'client_id' (str) or 'azp' (str)."""
    return (
        payload.get("client_id")
        or payload.get("azp")
        or payload.get("sub")
        or "unknown-client"
    )

# Function require_scopes
def require_scopes(required: List[str]) -> Callable:
    """
    Decorator to require specific scopes in a FastAPI endpoint.
    """
    def _dep(
        creds: HTTPAuthorizationCredentials = Depends(bearer),
    ) -> Dict[str, Any]:

        # Verify the presence of the token
        if creds is None or creds.scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Missing Bearer token")

        token = creds.credentials

        # Verify the token signature
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

        # Verify the scopes
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

        # Return the enriched context
        return {
            "device": _extract_caller(payload),
            "scopes": sorted(token_scopes),
            "sub":    payload.get("sub"),
            "payload": payload,
        }

    return _dep

# Function require_scopes_light for specific devices
def require_scopes_light(required: List[str]) -> Callable:
    """
    Light decorator to require specific scopes in a FastAPI endpoint.
    """
    def _dep(
        creds: HTTPAuthorizationCredentials = Depends(bearer),
    ) -> Dict[str, Any]:

        # Verify the presence of the token
        if creds is None or creds.scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Missing Bearer token")

        token = creds.credentials

        # Verify the token signature
        try:
            payload = jwt.decode(
                token,
                LIGHT_JWT_SECRET,
                algorithms=["HS256"],
                options={
                    "verify_exp": False,
                },
            )
        except jwt.InvalidSignatureError:
            raise HTTPException(status_code=401, detail="Invalid token signature")
        except jwt.PyJWTError as exc:
            logger.warning("Light token verification failed: %s", exc)
            raise HTTPException(status_code=401, detail="Invalid token")

        # Verify the scopes
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

        # Return the enriched context
        return {
            "device": payload.get("sub", "unknown"),
            "scopes": sorted(token_scopes),
            "sub":    payload.get("sub"),
            "payload": payload,
        }

    return _dep