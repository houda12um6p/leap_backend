"""Symmetric encryption for at-rest credentials (e.g. Jira API tokens).

The Fernet key is derived from `settings.secret_key` via HKDF-SHA256 with a
fixed application info string, so:
- rotating SECRET_KEY rotates this key too,
- no new env var is required, and
- this key never appears in the same form as the JWT signing key, even though
  both derive from the same secret.
"""
import base64
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .config import settings

_HKDF_INFO = b"leap.credentials.v1"
_HKDF_SALT = b"leap-credentials-salt"


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    if not settings.secret_key:
        raise RuntimeError(
            "SECRET_KEY is not configured; cannot encrypt or decrypt credentials."
        )
    raw = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_HKDF_SALT,
        info=_HKDF_INFO,
    ).derive(settings.secret_key.encode("utf-8"))
    return Fernet(base64.urlsafe_b64encode(raw))


def encrypt(plaintext: str) -> str:
    """Encrypt a string. Result is URL-safe base64 (Fernet token)."""
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt(token: str) -> str:
    """Decrypt a Fernet token. Raises InvalidToken on bad data / wrong key."""
    return _fernet().decrypt(token.encode("ascii")).decode("utf-8")


def try_decrypt(token: str | None) -> str | None:
    """Decrypt or return None if the token is missing or unreadable."""
    if not token:
        return None
    try:
        return decrypt(token)
    except (InvalidToken, ValueError):
        return None
