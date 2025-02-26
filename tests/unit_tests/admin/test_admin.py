from unittest.mock import Mock, patch
import pytest
from flask import Flask, session
from platzky.admin.admin import create_admin_blueprint

@pytest.fixture
def admin_blueprint():
    app = Flask(__name__)
    mock_db = Mock()
    mock_login_methods = Mock()
    mock_locale_func = Mock()
    blueprint = create_admin_blueprint(mock_login_methods, mock_db, mock_locale_func)
    app.register_blueprint(blueprint)
    app.mock_db = mock_db
    app.login_methods = mock_login_methods
    app.secret_key = 'test_secret_key'
    return app

@patch("platzky.admin.admin.render_template")
def test_admin_panel_renders_login_when_no_user(mock_render_template, admin_blueprint):
    with admin_blueprint.test_request_context("/admin/"):
        session["user"] = None
        admin_blueprint.view_functions["admin.admin_panel"]()
        mock_render_template.assert_called_with("login.html", login_methods=admin_blueprint.login_methods)

@patch("platzky.admin.admin.render_template")
def test_admin_panel_renders_admin_when_user_exists(mock_render_template, admin_blueprint):
    admin_blueprint.mock_db.get_plugins_data.return_value = [{"name": "plugin1"}, {"name": "plugin2"}]
    with admin_blueprint.test_request_context("/admin/"):
        session["user"] = "test_user"
        admin_blueprint.view_functions["admin.admin_panel"]()
        mock_render_template.assert_called_with(
            "admin.html", user="test_user", cms_modules={"plugins": ["plugin1", "plugin2"]}
        )

@patch("platzky.admin.admin.render_template")
def test_admin_panel_handles_empty_plugins_data(mock_render_template, admin_blueprint):
    admin_blueprint.mock_db.get_plugins_data.return_value = []
    with admin_blueprint.test_request_context("/admin/"):
        session["user"] = "test_user"
        admin_blueprint.view_functions["admin.admin_panel"]()
        mock_render_template.assert_called_with(
            "admin.html", user="test_user", cms_modules={"plugins": []}
        )
