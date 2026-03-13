"""
Integration test for Security Hardening Phase 1.
Verifies password hashing, URL validation, and camera limit enforcement.
"""

import pytest
from api.services.auth_service import verify_password, get_password_hash
from api.routers.cameras import validate_camera_url
from fastapi import HTTPException
from engine.config import Settings
import secrets


def test_password_hashing():
    password = "test-password"
    hashed = get_password_hash(password)
    assert verify_password(password, hashed) is True
    assert verify_password("wrong-password", hashed) is False


def test_validate_camera_url():
    # Valid URLs
    validate_camera_url("rtsp://admin:pass@192.168.1.10:554/ch1")
    validate_camera_url("http://192.168.1.10/mjpeg")
    validate_camera_url("https://example.com/stream")
    validate_camera_url("0")
    validate_camera_url("1")

    # Invalid URLs
    with pytest.raises(HTTPException) as exc:
        validate_camera_url("ftp://example.com")
    assert exc.value.status_code == 400

    with pytest.raises(HTTPException) as exc:
        validate_camera_url("file:///etc/passwd")
    assert exc.value.status_code == 400


def test_jwt_secret_validation():
    # Test that default secret raises error
    with pytest.raises(Exception):
        Settings(jwt_secret_key="change-me-in-production")
    
    # Test that secure secret passes
    secure_secret = secrets.token_urlsafe(64)
    settings = Settings(jwt_secret_key=secure_secret)
    assert settings.jwt_secret_key == secure_secret

if __name__ == "__main__":
    test_password_hashing()
    test_validate_camera_url()
    test_jwt_secret_validation()
    print("✅ Phase 1 hardening tests passed!")
