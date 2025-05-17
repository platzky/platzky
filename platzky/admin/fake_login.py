"""
Fake login functionality for development environments only.

WARNING: This module provides fake login functionality and should NEVER be used in production
environments as it bypasses proper authentication and authorization controls.
"""

from typing import Any, Callable

from flask import Blueprint, flash, redirect, session, url_for


def get_fake_login_html() -> Callable[[], str]:
    """Return a callable that generates HTML for fake login buttons."""

    def generate_html() -> str:
        from flask import url_for

        admin_url = url_for("admin.handle_fake_login", role="admin")
        nonadmin_url = url_for("admin.handle_fake_login", role="nonadmin")

        # Rest of the code remains the same
        return f"""
        <div class="col-md-6 mb-4">
          <div class="card">
            <div class="card-header">
              Development Login
            </div>
            <div class="card-body">
              <p class="text-danger"><strong>Warning:</strong> For development only</p>
              <div class="d-flex justify-content-around">
                <a href="{admin_url}"
                   class="btn btn-primary">Login as Admin</a>
                <a href="{nonadmin_url}"
                   class="btn btn-secondary">Login as Non-Admin</a>
              </div>
            </div>
          </div>
        </div>
        """

    return generate_html


def setup_fake_login_routes(blueprint: Blueprint) -> None:
    """Add fake login routes to the provided blueprint."""

    import os

    if os.environ.get("FLASK_ENV") == "production":
        import warnings

        warnings.warn(
            "Fake login routes are enabled in a production environment! "
            "This is a serious security risk and should be disabled immediately.",
            UserWarning,
            stacklevel=2,
        )

    @blueprint.route("/fake-login/<role>")
    def handle_fake_login(role: str) -> Any:
        valid_roles = ["admin", "nonadmin"]
        if role not in valid_roles:
            flash(f"Invalid role: {role}. Must be one of: {', '.join(valid_roles)}", "error")
            return redirect(url_for("admin.admin_panel_home"))
        if role == "admin":
            session["user"] = {"username": "admin", "role": "admin"}
        else:
            session["user"] = {"username": "user", "role": "nonadmin"}
        return redirect(url_for("admin.admin_panel_home"))
