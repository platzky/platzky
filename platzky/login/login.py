"""Blueprint for authentication — login page, provider dispatch, and logout."""

from collections.abc import Sequence
from os.path import dirname

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for
from werkzeug.wrappers import Response

from platzky.auth import AuthenticationError
from platzky.plugin.login import LoginPluginBase


def create_login_blueprint(login_plugins: Sequence[LoginPluginBase]) -> Blueprint:
    """Create the login blueprint with authentication routes.

    Args:
        login_plugins: Login provider plugin instances.

    Returns:
        Configured Flask Blueprint for authentication.
    """
    login = Blueprint(
        "login",
        __name__,
        template_folder=f"{dirname(__file__)}/templates",
    )

    @login.route("/login")
    def login_page() -> str:
        """Render the login page."""
        return render_template("login.html", login_plugins=login_plugins)

    @login.route("/login/verify/<provider>", methods=["POST"])
    def verify_login(provider: str) -> Response | tuple[Response, int]:
        """Dispatch a login request to the matching LoginPluginBase plugin.

        Args:
            provider: The provider name declared by the plugin (e.g. ``google``).

        Returns:
            Redirect to the next URL on success, or a JSON error response.
        """
        plugin = next((p for p in login_plugins if p.provider_name == provider), None)
        if plugin is None:
            return jsonify({"error": f"Unknown provider: {provider}"}), 404
        try:
            user = plugin.authenticate(request)
        except AuthenticationError as e:
            return jsonify({"error": str(e)}), 401
        session["user"] = user
        next_url = session.pop("next", None)
        if not next_url or not next_url.startswith("/") or next_url.startswith("//"):
            next_url = url_for("admin.admin_panel_home")
        return redirect(next_url)

    @login.route("/logout", methods=["POST"])
    def logout() -> Response:
        """Clear the user session and redirect to the login page.

        Returns:
            Redirect to the login page.
        """
        session.pop("user", None)
        return redirect(url_for("login.login_page"))

    return login
