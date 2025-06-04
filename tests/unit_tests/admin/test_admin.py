from unittest.mock import Mock, patch

import pytest
from flask import Flask, session

from platzky.admin.admin import create_admin_blueprint

mock_login_methods = Mock()


@pytest.fixture
def admin_blueprint():
    app = Flask(__name__)
    cms_modules = []
    blueprint = create_admin_blueprint(mock_login_methods, cms_modules)
    app.register_blueprint(blueprint)
    app.secret_key = "test_secret_key"
    return app


@patch("platzky.admin.admin.render_template")
def test_admin_panel_renders_login_when_no_user(mock_render_template, admin_blueprint):
    with admin_blueprint.test_request_context("/admin/"):
        session["user"] = None
        admin_blueprint.view_functions["admin.admin_panel_home"]()
        mock_render_template.assert_called_with("login.html", login_methods=mock_login_methods)


@patch("platzky.admin.admin.render_template")
def test_admin_panel_renders_admin_when_user_exists(mock_render_template, admin_blueprint):
    with admin_blueprint.test_request_context("/admin/"):
        session["user"] = "test_user"
        admin_blueprint.view_functions["admin.admin_panel_home"]()
        mock_render_template.assert_called_with(
            "admin.html", user="test_user", cms_modules=[]
        )
