from os.path import dirname

from flask import Blueprint, render_template, session


def create_admin_blueprint(login_methods, db, locale_func):
    admin = Blueprint(
        "admin",
        __name__,
        url_prefix="/admin",
        template_folder=f"{dirname(__file__)}/templates",
    )

    @admin.route("/", methods=["GET"])
    def admin_panel_home():
        user = session.get("user", None)

        if not user:
            return render_template("login.html", login_methods=login_methods)

        cms_modules = {"plugins": [plugin.get("name") for plugin in db.get_plugins_data()]}
        return render_template("admin.html", user=user, cms_modules=cms_modules)

    @admin.route("/module/<module_name>", methods=["GET"])
    def module_settings(module_name):
        user = session.get("user", None)

        if not user:
            return render_template("login.html", login_methods=login_methods)

        return render_template("module.html", user=user, module_name=module_name)

    return admin
