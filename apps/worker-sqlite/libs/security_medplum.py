from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Callable, List, Dict, Any
import base64
import json
import time

bearer = HTTPBearer(auto_error=False)

def _b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)

def _decode_jwt_no_verify(token: str) -> Dict[str, Any]:
    # NOTE: pas de vérification de signature ici (OK “pour le moment”)
    parts = token.split(".")
    if len(parts) < 2:
        raise ValueError("Not a JWT")
    payload = json.loads(_b64url_decode(parts[1]).decode("utf-8"))
    return payload

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
            payload = _decode_jwt_no_verify(token)
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid token")

        # (optionnel) check exp sans vérifier signature
        exp = payload.get("exp")
        if isinstance(exp, (int, float)) and time.time() > float(exp):
            raise HTTPException(status_code=401, detail="Token expired")

        token_scopes = set(_extract_scopes(payload))
        missing = [s for s in required if s not in token_scopes]
        if missing:
            raise HTTPException(status_code=403, detail=f"Missing scopes: {missing}")

        # identité “device/caller” : à ajuster selon tes claims réels
        caller = payload.get("client_id") or payload.get("azp") or payload.get("sub") or "unknown-client"
        return {"device": str(caller), "scopes": sorted(token_scopes)}

    return _dep
