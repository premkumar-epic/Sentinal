"""
SENTINAL v2 — Authentication Service
Handles password hashing and verification using bcrypt.
"""

import bcrypt


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Compare a plain-text password with its hashed version."""
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())


def get_password_hash(password: str) -> str:
    """Generate a hashed version of a plain-text password."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
