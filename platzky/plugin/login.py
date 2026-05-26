"""LoginPluginBase capability — plugins that provide authentication methods."""

from __future__ import annotations

import inspect
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import ClassVar

from flask import Request

from platzky.auth import AuthenticationError as AuthenticationError
from platzky.auth import User as User
from platzky.plugin.plugin import PluginBase


class LoginPluginBase(PluginBase, ABC):
    """Base class for login provider plugins.

    Subclasses declare a ``provider_name`` and implement ``authenticate``
    (credential verification) and ``get_login_method`` (login UI).

    The engine registers a single ``/verify_login/<provider>`` route that
    dispatches incoming data to the matching plugin's ``authenticate`` method.
    """

    provider_name: ClassVar[str]

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        if not inspect.isabstract(cls) and "provider_name" not in cls.__dict__:
            raise TypeError(f"{cls.__name__} must define provider_name as a class attribute")

    @abstractmethod
    def get_login_method(self) -> Callable[[], str]:
        """Return a callable that renders the login button HTML.

        Returns:
            A zero-argument callable returning an HTML string.
        """
        ...

    @abstractmethod
    def authenticate(self, request: Request) -> User:
        """Attempt authentication from the incoming Flask request.

        The plugin extracts whatever it needs from ``request`` —
        ``request.get_json()``, ``request.form``, ``request.args``, etc.

        Args:
            request: The Flask request object for the current login attempt.

        Returns:
            Authenticated user on success.

        Raises:
            AuthenticationError: If credentials are invalid or missing.
        """
        ...
