"""
SENTINAL v2 — JWT Authentication Middleware
FastAPI dependency for validating Bearer JWT tokens on protected routes.
"""

from typing import Optional

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from engine.config import settings

# Module-level OAuth2 scheme — points to the login endpoint
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# JWT algorithm — must match what auth router uses
ALGORITHM = "HS256"


async def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    """
    FastAPI dependency for validating JWT Bearer tokens.

    Decodes the JWT using the configured secret key and extracts the username (sub claim).
    Used as a dependency on protected routes.

    Args:
        token: JWT token extracted from Authorization header by OAuth2PasswordBearer

    Returns:
        The username (sub field) from the JWT payload

    Raises:
        HTTPException: 401 if token is invalid, expired, or missing sub claim
    """
    return await _validate_token(token)


async def get_current_user_from_query(token: str = Query(...)) -> str:
    """
    FastAPI dependency for validating JWT tokens passed as a query parameter.
    Useful for components that cannot send Bearer headers (e.g. <img> tags).
    """
    return await _validate_token(token)


async def _validate_token(token: str) -> str:
    """Internal helper to validate JWT and extract username."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # Decode the JWT token using the secret key
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[ALGORITHM])
        username: Optional[str] = payload.get("sub")

        if username is None:
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    return username
