"""
SENTINAL v2 — JWT Authentication Router
Provides login endpoint and JWT token generation.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt

from engine.config import settings

# Module-level constants for middleware/other components to import
SECRET_KEY = settings.jwt_secret_key
ALGORITHM = "HS256"

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()) -> Dict[str, str]:
    """
    Authenticate user with username and password, return JWT token.

    Args:
        form_data: OAuth2 form with username and password fields

    Returns:
        Dictionary with access_token and token_type

    Raises:
        HTTPException: 401 if credentials do not match configured auth settings
    """
    # Validate credentials against settings
    if form_data.username != settings.auth_username or form_data.password != settings.auth_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create JWT payload with expiration
    now = datetime.now(timezone.utc)
    exp_time = now + timedelta(minutes=settings.jwt_expire_minutes)

    payload = {
        "sub": form_data.username,
        "exp": exp_time,
    }

    # Sign JWT token
    access_token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    return {"access_token": access_token, "token_type": "bearer"}
