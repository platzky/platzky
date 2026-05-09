"""Blueprint for admin panel functionality."""

from collections.abc import Callable
from os.path import dirname

from flask import Blueprint, render_template, session

from platzky.models import CmsModule
from platzky.shortcodes import Shortcode


def create_admin_blueprint(
    login_methods: list[Callable[[], str]],
    cms_modules: list[CmsModule],
    shortcodes: dict[str, Shortcode],
) -> Blueprint:
    """Create admin blueprint with dynamic module routes.

    Args:
        login_methods: Available login methods
        cms_modules: List of CMS modules to register routes for
        shortcodes: Registered shortcode descriptors for the help page

    Returns:
        Configured Flask Blueprint for admin panel
    """
    admin = Blueprint(
        "admin",
        __name__,
        url_prefix="/admin",
        template_folder=f"{dirname(__file__)}/templates",
    )

    @admin.before_request
    def require_login() -> str | None:
        if not session.get("user"):
            return render_template("login.html", login_methods=login_methods)
        return None

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
        """Display the admin panel home page."""
        return render_template("admin.html", user=session.get("user"), cms_modules=cms_modules)

    @admin.route("/help", methods=["GET"])
    def admin_help() -> str:
        """Display the admin help page for content authors."""
        return render_template("help.html", shortcodes=list(shortcodes.items()))

    return admin
