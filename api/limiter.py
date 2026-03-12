"""SENTINAL v2 — Shared rate limiter instance (breaks circular import)."""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
