"""
Fake login plugin for development environments only.

WARNING: Never use in production — bypasses real authentication.
"""

from importlib.resources import files

from flask import Request, current_app, render_template_string
from markupsafe import Markup

from platzky.auth import AuthenticationError, User
from platzky.plugin.login import LoginPluginBase

ROLE_ADMIN = "admin"
ROLE_NONADMIN = "nonadmin"

_BUTTON_TEMPLATE = files("platzky.debug").joinpath("templates/fake_login_button.html").read_text()


class FakeLoginPlugin(LoginPluginBase):
    """Dev-only login provider that exercises the full verify_login callback flow."""

    provider_name = "fake"

    def render_login_button(self) -> Markup:
        """Render the dev login buttons with CSRF tokens.

        Returns:
            Safe HTML markup for the development login buttons.
        """
        return Markup(render_template_string(_BUTTON_TEMPLATE))

    def authenticate(self, request: Request) -> User:
        """Authenticate from a form POST, mapping role to a User.

        Args:
            request: The Flask request containing ``role`` in ``request.form``.

        Returns:
            Authenticated user for recognised roles.

        Raises:
            AuthenticationError: If the role value is missing or unrecognised.
        """
        if not current_app.debug and not current_app.testing:
            raise RuntimeError("FakeLoginPlugin must not be used in production")
        role = request.form.get("role")
        if role == ROLE_ADMIN:
            return User(username=ROLE_ADMIN, role=ROLE_ADMIN)
        if role == ROLE_NONADMIN:
            return User(username="user", role=ROLE_NONADMIN)
        raise AuthenticationError(f"Unrecognised role: {role!r}")
