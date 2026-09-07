"""Origin resolution for the FlexWeek desktop shell. No Qt imports.

The rules mirror backend/app.py's create_app so a misconfigured desktop build
fails at startup with the same message the server would give, instead of
loading a page whose writes the server will reject.
"""

from __future__ import annotations

import os
from urllib.parse import urlsplit

DEFAULT_ORIGIN = "http://127.0.0.1:8000"
LOCAL_HOSTS = {"127.0.0.1", "localhost", "testserver"}
DEFAULT_PORTS = {"http": 80, "https": 443}


def resolve_origin(env: dict[str, str] | None = None) -> str:
    """FLEXWEEK_DESKTOP_ORIGIN, else FLEXWEEK_ORIGIN, else the local default."""
    source = os.environ if env is None else env
    for name in ("FLEXWEEK_DESKTOP_ORIGIN", "FLEXWEEK_ORIGIN"):
        value = (source.get(name) or "").strip()
        if value:
            return validate_origin(value)
    return validate_origin(DEFAULT_ORIGIN)


def validate_origin(origin: str) -> str:
    """Return the normalized origin, or raise ValueError explaining the problem."""
    trimmed = origin.rstrip("/")
    parsed = urlsplit(trimmed)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.path or parsed.query:
        raise ValueError(f"{origin!r} must be an http(s) origin without a path, e.g. {DEFAULT_ORIGIN}")
    if parsed.scheme != "https" and parsed.hostname not in LOCAL_HOSTS:
        raise ValueError(f"{origin!r} is not local, so it must use https")
    return trimmed


def origin_key(url: str) -> tuple[str, str, int] | None:
    """Scheme/host/port triple used to decide what stays inside the window."""
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    port = parsed.port or DEFAULT_PORTS[parsed.scheme]
    return parsed.scheme, parsed.hostname.lower(), port


def is_same_origin(url: str, origin: str) -> bool:
    """True when url belongs to the app itself; anything else opens in the OS browser."""
    target = origin_key(url)
    return target is not None and target == origin_key(origin)
