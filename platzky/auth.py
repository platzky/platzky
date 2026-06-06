"""Authentication primitives shared across the engine and plugins."""

from __future__ import annotations

from typing import TypedDict

from typing_extensions import NotRequired


class AuthenticationError(Exception):
    """Raised when login credentials are invalid or missing."""


class User(TypedDict):
    """Authenticated user stored in the session.

    Attributes:
        username: Unique identifier for the user.
        role: Optional authorization role (e.g. ``"admin"``). Omit when the
            plugin has no role concept; role-based checks should treat a missing
            value as an unprivileged user.
    """

    username: str
    role: NotRequired[str]
