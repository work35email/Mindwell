"""Fernet encryption for journal text, chat, check-in notes, and summaries."""

from __future__ import annotations

import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

UNREADABLE = "[could not read this entry]"

_fernet: Fernet | None = None


def init_crypto(key: str | bytes | None, instance_path: str | None = None) -> None:
    """Install the process-wide Fernet key.

    Preference order: the argument, FIELD_ENCRYPTION_KEY, then instance/field.key.
    A missing key is generated once and stored under the instance path so a local
    demo survives restarts. Tests should always pass an explicit key.
    """
    global _fernet
    raw = _coerce(key) or _coerce(os.getenv("FIELD_ENCRYPTION_KEY"))
    if raw is None and instance_path:
        path = Path(instance_path) / "field.key"
        if path.exists():
            raw = path.read_bytes().strip()
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            raw = Fernet.generate_key()
            path.write_bytes(raw)
    if raw is None:
        raise RuntimeError("FIELD_ENCRYPTION_KEY is not set and no instance path was given.")
    _fernet = Fernet(raw)


def encrypt(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    if _fernet is None:
        raise RuntimeError("Encryption is not initialised.")
    return _fernet.encrypt(value.encode("utf-8")).decode("ascii")


def decrypt(value: str | None) -> str:
    if not value:
        return ""
    if _fernet is None:
        raise RuntimeError("Encryption is not initialised.")
    try:
        return _fernet.decrypt(value.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return UNREADABLE


def _coerce(key: str | bytes | None) -> bytes | None:
    if key is None:
        return None
    if isinstance(key, bytes):
        token = key.strip()
    else:
        token = key.strip().encode("ascii")
    if not token:
        return None
    # Validate early so a bad .env fails at startup, not on the first journal save.
    Fernet(token)
    return token
