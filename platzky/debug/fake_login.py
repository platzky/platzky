"""
Fake login plugin for development environments only.

WARNING: Never use in production — bypasses real authentication.
"""

from __future__ import annotations

from flask import Request, current_app, render_template_string
from markupsafe import Markup

from platzky.auth import AuthenticationError, User
from platzky.plugin.login import LoginPluginBase

ROLE_ADMIN = "admin"
ROLE_NONADMIN = "nonadmin"

_BUTTON_TEMPLATE = """\
<div class="col-md-6 mb-4">
  <div class="card">
    <div class="card-header">Development Login</div>
    <div class="card-body">
      <p class="text-danger"><strong>Warning:</strong> For development only</p>
      <div class="d-flex justify-content-around">
        <form method="post" action="/verify_login/fake" style="display: inline;">
          <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
          <input type="hidden" name="role" value="admin">
          <button type="submit" class="btn btn-primary">Login as Admin</button>
        </form>
        <form method="post" action="/verify_login/fake" style="display: inline;">
          <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
          <input type="hidden" name="role" value="nonadmin">
          <button type="submit" class="btn btn-secondary">Login as Non-Admin</button>
        </form>
      </div>
    </div>
  </div>
</div>
"""


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
