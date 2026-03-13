"""
SENTINAL v2 — JWT Authentication Router
Provides login endpoint and JWT token generation.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt

from api.limiter import limiter
from api.services.auth_service import verify_password
from engine.config import settings

# Module-level constants for middleware/other components to import
SECRET_KEY = settings.jwt_secret_key
ALGORITHM = settings.jwt_algorithm

router = APIRouter(prefix="/api/auth", tags=["auth"])


@limiter.limit("5/minute")
@router.post("/login")
async def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends()) -> Dict[str, str]:
    """
    Authenticate user with username and password, return JWT token.
    Rate-limited to 5 requests/minute per IP via slowapi.
    """
    if form_data.username != settings.auth_username or not verify_password(form_data.password, settings.auth_password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    now = datetime.now(timezone.utc)
    exp_time = now + timedelta(minutes=settings.jwt_expire_minutes)

    payload = {
        "sub": form_data.username,
        "exp": exp_time,
    }

    access_token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    return {"access_token": access_token, "token_type": "bearer"}
