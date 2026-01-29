"""
Fake login functionality for development environments only.

WARNING: This module provides fake login functionality and should NEVER be used in production
environments as it bypasses proper authentication and authorization controls.
"""

from collections.abc import Callable
from typing import Any

from flask import Blueprint, flash, redirect, render_template_string, session, url_for
from flask.sansio.app import App
from flask_wtf import FlaskForm
from markupsafe import Markup
from werkzeug.wrappers import Response


class DebugBlueprint(Blueprint):
    """A Blueprint that can only be registered on apps in debug/testing mode.

    Raises RuntimeError during registration if the app is not in debug or testing mode.
    This provides a structural guarantee that debug-only routes cannot be accidentally
    enabled in production.
    """

    def register(self, app: App, options: dict[str, Any]) -> None:
        """Register the blueprint, but only if app is in debug/testing mode."""
        if not (app.config.get("DEBUG") or app.config.get("TESTING")):
            raise RuntimeError(
                f"SECURITY ERROR: Cannot register DebugBlueprint '{self.name}' in production. "
                f"DEBUG and TESTING are both False. "
                f"Set DEBUG: true or TESTING: true in your config."
            )
        super().register(app, options)


ROLE_ADMIN = "admin"
ROLE_NONADMIN = "nonadmin"
VALID_ROLES = [ROLE_ADMIN, ROLE_NONADMIN]


class FakeLoginForm(FlaskForm):
    """
    Empty form class that inherits CSRF protection from FlaskForm.

    Used specifically for the fake login functionality to enable
    CSRF token validation on form submissions.
    """

    pass


def get_fake_login_html() -> Callable[[], str]:
    """Return a callable that generates HTML for fake login buttons."""

    def generate_html() -> str:
        admin_url = url_for("fake_login.handle_fake_login", role="admin")
        nonadmin_url = url_for("fake_login.handle_fake_login", role="nonadmin")

        # Create a form instance to get the CSRF token
        form = FakeLoginForm()

        html = render_template_string(
            """
        <div class="col-md-6 mb-4">
          <div class="card">
            <div class="card-header">
              Development Login
            </div>
            <div class="card-body">
              <p class="text-danger"><strong>Warning:</strong> For development only</p>
              <div class="d-flex justify-content-around">
                <form method="post" action="{{ admin_url }}" style="display: inline;">
                  {{ form.csrf_token }}
                  <button type="submit" class="btn btn-primary">Login as Admin</button>
                </form>
                <form method="post" action="{{ nonadmin_url }}" style="display: inline;">
                  {{ form.csrf_token }}
                  <button type="submit" class="btn btn-secondary">Login as Non-Admin</button>
                </form>
              </div>
            </div>
          </div>
        </div>
        """,
            form=form,
            admin_url=admin_url,
            nonadmin_url=nonadmin_url,
        )

        return Markup(html)

    return generate_html


def create_fake_login_blueprint() -> DebugBlueprint:
    """Create a DebugBlueprint with fake login routes.

    The returned blueprint will raise RuntimeError if registered on an app
    that is not in debug or testing mode.

    Returns:
        DebugBlueprint with fake login routes at /admin/fake-login/<role>.
    """
    bp = DebugBlueprint("fake_login", __name__, url_prefix="/admin")

    @bp.route("/fake-login/<role>", methods=["POST"])
    def handle_fake_login(role: str) -> Response:
        form = FakeLoginForm()
        if form.validate_on_submit() and role in VALID_ROLES:
            if role == ROLE_ADMIN:
                session["user"] = {"username": ROLE_ADMIN, "role": ROLE_ADMIN}
            else:
                session["user"] = {"username": "user", "role": ROLE_NONADMIN}
            return redirect(url_for("admin.admin_panel_home"))

        flash(f"Invalid role: {role}. Must be one of: {', '.join(VALID_ROLES)}", "error")
        return redirect(url_for("admin.admin_panel_home"))

    return bp
