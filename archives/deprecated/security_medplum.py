from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Callable, List, Dict, Any
import logging

import jwt

from libs.verify_token import verify_token

logger = logging.getLogger(__name__)

bearer = HTTPBearer(auto_error=False)


def _extract_scopes(payload: Dict[str, Any]) -> List[str]:
    scopes: List[str] = []

    scope_str = payload.get("scope")
    if isinstance(scope_str, str) and scope_str.strip():
        scopes.extend(scope_str.split())

    scp = payload.get("scp")
    if isinstance(scp, list):
        scopes.extend([str(x) for x in scp if str(x).strip()])

    # de-dup stable
    seen = set()
    return [s for s in scopes if not (s in seen or seen.add(s))]


def require_scopes(required: List[str]) -> Callable:
    def _dep(creds: HTTPAuthorizationCredentials = Depends(bearer)) -> Dict[str, Any]:
        if creds is None or creds.scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Missing Bearer token")

        token = creds.credentials
        try:
            payload = verify_token(token)
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.InvalidIssuerError:
            raise HTTPException(status_code=401, detail="Invalid token issuer")
        except (jwt.PyJWTError, ValueError, RuntimeError) as exc:
            logger.warning("Token verification failed: %s", exc)
            raise HTTPException(status_code=401, detail="Invalid token")

        token_scopes = set(_extract_scopes(payload))
        missing = [s for s in required if s not in token_scopes]
        if missing:
            raise HTTPException(status_code=403, detail=f"Missing scopes: {missing}")

        caller = payload.get("client_id") or payload.get("azp") or payload.get("sub") or "unknown-client"
        return {"device": str(caller), "scopes": sorted(token_scopes)}

    return _dep
