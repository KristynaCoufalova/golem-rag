"""
Lightweight OIDC token verification for FastAPI endpoints.

Assumptions:
- Authorization: Bearer <id_token> (JWT) is sent with each request.
- Tokens are issued by the configured OIDC authority and include `sub` as the user id.

Environment:
- OIDC_AUTHORITY (e.g., https://idd.histruct.com)
- OIDC_AUDIENCE (client id / audience to validate)

Notes:
- This keeps a simple in-memory JWKS cache. For production, consider caching with TTL
  and handling key rotation errors gracefully.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any, Dict

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwk, jwt
from jose.exceptions import JWTError


bearer_scheme = HTTPBearer(auto_error=False)


class AuthSettings:
    authority: str
    audience: str

    def __init__(self) -> None:
        # Support both OIDC_* and AUTH_OIDC_* naming conventions
        self.authority = (
            os.getenv("OIDC_AUTHORITY") 
            or os.getenv("AUTH_OIDC_AUTHORITY") 
            or "https://idd.histruct.com"
        ).rstrip("/")
        self.audience = (
            os.getenv("OIDC_AUDIENCE") 
            or os.getenv("OIDC_CLIENT_ID")
            or os.getenv("AUTH_OIDC_CLIENT_ID")
            or "histruct-golem-localhost"
        )


@lru_cache(maxsize=1)
def _get_settings() -> AuthSettings:
    return AuthSettings()


@lru_cache(maxsize=1)
def _get_jwks() -> Dict[str, Any]:
    settings = _get_settings()
    jwks_uri = f"{settings.authority}/.well-known/openid-configuration"
    resp = httpx.get(jwks_uri, timeout=5.0)
    resp.raise_for_status()
    jwks_url = resp.json().get("jwks_uri")
    if not jwks_url:
        raise RuntimeError("jwks_uri not found in OIDC discovery document")
    keys_resp = httpx.get(jwks_url, timeout=5.0)
    keys_resp.raise_for_status()
    return {key["kid"]: key for key in keys_resp.json().get("keys", [])}


def _verify_jwt(token: str) -> Dict[str, Any]:
    settings = _get_settings()
    unverified_header = jwt.get_unverified_header(token)
    kid = unverified_header.get("kid")
    if not kid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token missing kid")

    jwks = _get_jwks()
    if kid not in jwks:
        _get_jwks.cache_clear()
        jwks = _get_jwks()
    key_data = jwks.get(kid)
    if not key_data:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown signing key")

    public_key = jwk.construct(key_data)
    try:
        payload = jwt.decode(
            token,
            public_key.to_pem().decode(),
            audience=settings.audience,
            issuer=settings.authority,
            options={"verify_exp": True, "verify_aud": True, "verify_iss": True},
            algorithms=[key_data.get("alg", "RS256")],
        )
        return payload
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> Dict[str, Any]:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
    return _verify_jwt(token)


__all__ = ["get_current_user"]

