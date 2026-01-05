"""Flask blueprint for admin panel functionality."""

from os.path import dirname

from flask import Blueprint, render_template, session


def create_admin_blueprint(login_methods, cms_modules):
    """Create admin blueprint with dynamic module routes.

    Args:
        login_methods: Available login methods
        cms_modules: List of CMS modules to register routes for
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
        def module_route(module=module):
            """Render a CMS module page."""
            return render_template(module.template, module=module)

    @admin.route("/", methods=["GET"])
    def admin_panel_home():
        """Display admin panel home or login page."""
        user = session.get("user", None)

        if not user:
            return render_template("login.html", login_methods=login_methods)

        return render_template("admin.html", user=user, cms_modules=cms_modules)

    return admin
