"""
Fake login functionality for development environments only.

WARNING: This module provides fake login functionality and should NEVER be used in production
environments as it bypasses proper authentication and authorization controls.
"""
from typing import Any

from flask import Blueprint, flash, redirect, session, url_for, Response

def get_fake_login_html() -> str:
    """Generate HTML for fake login buttons."""
    html = """
    <div class="col-md-6 mb-4">
      <div class="card">
        <div class="card-header">
          Development Login
        </div>
        <div class="card-body">
          <p class="text-danger"><strong>Warning:</strong> For development only</p>
          <div class="d-flex justify-content-around">
            <a href="{{ url_for('admin.fake_login', role='admin') }}" class="btn btn-primary">Login as Admin</a>
            <a href="{{ url_for('admin.fake_login', role='nonadmin') }}" class="btn btn-secondary">Login as Non-Admin</a>
          </div>
        </div>
      </div>
    </div>
    """
    return html

def setup_fake_login_routes(blueprint: Blueprint) -> None:
    """Add fake login routes to the provided blueprint."""

    @blueprint.route("/fake-login/<role>")
    def fake_login(role: str) -> Any:
        if role == "admin":
            session["user"] = {"username": "admin", "role": "admin"}
        else:
            session["user"] = {"username": "user", "role": "nonadmin"}
        return redirect(url_for("admin.admin_panel_home"))
