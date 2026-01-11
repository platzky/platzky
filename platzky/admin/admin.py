"""Blueprint for admin panel functionality."""

from os.path import dirname
from typing import Any

from flask import Blueprint, render_template, session

from platzky.models import CmsModule


def create_admin_blueprint(login_methods: list[Any], cms_modules: list[CmsModule]) -> Blueprint:
    """Create admin blueprint with dynamic module routes.

    Args:
        login_methods: Available login methods
        cms_modules: List of CMS modules to register routes for

    Returns:
        Configured Flask Blueprint for admin panel
    """
    # …rest of the function…
    admin = Blueprint(
        "admin",
        __name__,
        url_prefix="/admin",
        template_folder=f"{dirname(__file__)}/templates",
    )

    for module in cms_modules:

        @admin.route(f"/module/{module.slug}", methods=["GET"])
        def module_route(module: CmsModule = module) -> str:
            """Render a CMS module page.

            Args:
                module: CMS module object containing template and configuration

            Returns:
                Rendered HTML template for the module
            """
            return render_template(module.template, module=module)

    @admin.route("/", methods=["GET"])
    def admin_panel_home() -> str:
        """Display admin panel home or login page.

        Returns:
            Rendered login page if not authenticated, admin panel if authenticated
        """
        user = session.get("user", None)

        if not user:
            return render_template("login.html", login_methods=login_methods)

        return render_template("admin.html", user=user, cms_modules=cms_modules)

    return admin
