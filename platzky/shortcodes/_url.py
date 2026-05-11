from __future__ import annotations

from urllib.parse import urlparse

_ALLOWED_SCHEMES = {"http", "https", ""}


def is_url_allowed(url: str) -> bool:
    return urlparse(url).scheme in _ALLOWED_SCHEMES
