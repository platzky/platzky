"""LoginPluginBase capability — plugins that provide authentication methods."""

import inspect
from abc import ABC, abstractmethod
from typing import ClassVar

from flask import Request
from markupsafe import Markup

from platzky.auth import User
from platzky.plugin.plugin import PluginBase


class LoginPluginBase(PluginBase, ABC):
    """Base class for login provider plugins.

    Subclasses declare a ``provider_name`` and implement ``authenticate``
    (credential verification) and ``render_login_button`` (login UI).

    The engine registers a single ``/verify_login/<provider>`` route that
    dispatches incoming data to the matching plugin's ``authenticate`` method.
    """

    provider_name: ClassVar[str]

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        if not inspect.isabstract(cls) and "provider_name" not in cls.__dict__:
            raise TypeError(f"{cls.__name__} must define provider_name as a class attribute")

    @abstractmethod
    def render_login_button(self) -> Markup:
        """Render the login button HTML for this provider.

        Returns:
            Safe HTML markup for the login button, rendered within a request context.
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
