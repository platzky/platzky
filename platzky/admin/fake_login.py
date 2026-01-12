"""
Fake login functionality for development environments only.

WARNING: This module provides fake login functionality and should NEVER be used in production
environments as it bypasses proper authentication and authorization controls.
"""

import os
from collections.abc import Callable

from flask import Blueprint, flash, redirect, render_template_string, session, url_for
from flask_wtf import FlaskForm
from markupsafe import Markup
from werkzeug.wrappers import Response

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
        admin_url = url_for("admin.handle_fake_login", role="admin")
        nonadmin_url = url_for("admin.handle_fake_login", role="nonadmin")

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


def setup_fake_login_routes(admin_blueprint: Blueprint) -> Blueprint:
    """Add fake login routes to the provided admin_blueprint."""

    env = os.environ
    is_testing = "PYTEST_CURRENT_TEST" in env.keys() or env.get("FLASK_DEBUG") in (
        "1",
        "true",
        "True",
        True,
    )

    if not is_testing:
        raise RuntimeError(
            "SECURITY ERROR: Fake login routes are enabled outside of a testing environment! "
            "This functionality must only be used during development or testing."
        )

    @admin_blueprint.route("/fake-login/<role>", methods=["POST"])
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

    return admin_blueprint
