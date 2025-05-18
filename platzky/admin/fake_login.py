"""
Fake login functionality for development environments only.

WARNING: This module provides fake login functionality and should NEVER be used in production
environments as it bypasses proper authentication and authorization controls.
"""

import os
from typing import Any, Callable

from flask import Blueprint, flash, redirect, session, url_for
from markupsafe import Markup

ROLE_ADMIN = "admin"
ROLE_NONADMIN = "nonadmin"
VALID_ROLES = [ROLE_ADMIN, ROLE_NONADMIN]


def get_fake_login_html() -> Callable[[], str]:
    """Return a callable that generates HTML for fake login buttons."""

    def generate_html() -> str:
        admin_url = url_for("admin.handle_fake_login", role="admin")
        nonadmin_url = url_for("admin.handle_fake_login", role="nonadmin")

        # Rest of the code remains the same
        html = f"""
        <div class="col-md-6 mb-4">
          <div class="card">
            <div class="card-header">
              Development Login
            </div>
            <div class="card-body">
              <p class="text-danger"><strong>Warning:</strong> For development only</p>
              <div class="d-flex justify-content-around">
                <form method="post" action="{admin_url}" style="display: inline;">
                  <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
                  <button type="submit" class="btn btn-primary">Login as Admin</button>
                </form>
                <form method="post" action="{nonadmin_url}" style="display: inline;">
                  <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
                  <button type="submit" class="btn btn-secondary">Login as Non-Admin</button>
                </form>
              </div>
            </div>
          </div>
        </div>
        """
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
    def handle_fake_login(role: str) -> Any:
        if role not in VALID_ROLES:
            flash(f"Invalid role: {role}. Must be one of: {', '.join(VALID_ROLES)}", "error")
            return redirect(url_for("admin.admin_panel_home"))
        if role == ROLE_ADMIN:
            session["user"] = {"username": ROLE_ADMIN, "role": ROLE_ADMIN}
        else:
            session["user"] = {"username": "user", "role": ROLE_NONADMIN}
        return redirect(url_for("admin.admin_panel_home"))

    return admin_blueprint
