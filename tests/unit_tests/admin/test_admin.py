from unittest.mock import Mock, patch

import pytest
from flask import Flask

from platzky.admin.admin import create_admin_blueprint
from platzky.models import CmsModule

mock_login_methods = Mock()

CMS_MODULE = CmsModule(
    slug="module1",
    template="module1.html",
    name="Module 1",
    description="Test Module 1",
)


@pytest.fixture
def admin_blueprint():
    app = Flask(__name__)
    blueprint = create_admin_blueprint(mock_login_methods, [CMS_MODULE], shortcodes={})
    app.register_blueprint(blueprint)
    app.secret_key = "test_secret_key"
    return app


@patch("platzky.admin.admin.render_template")
def test_admin_panel_renders_login_when_no_user(mock_render_template: Mock, admin_blueprint: Flask):
    mock_render_template.return_value = "login"
    with admin_blueprint.test_client() as client:
        client.get("/admin/")
        mock_render_template.assert_called_with("login.html", login_methods=mock_login_methods)


@patch("platzky.admin.admin.render_template")
def test_admin_panel_renders_admin_when_user_exists(
    mock_render_template: Mock, admin_blueprint: Flask
):
    mock_render_template.return_value = "admin"
    with admin_blueprint.test_client() as client:
        with client.session_transaction() as sess:
            sess["user"] = "test_user"
        client.get("/admin/")
        mock_render_template.assert_called_with(
            "admin.html", user="test_user", cms_modules=[CMS_MODULE]
        )


@patch("platzky.admin.admin.render_template")
def test_admin_panel_renders_cms_modules(mock_render_template: Mock, admin_blueprint: Flask):
    mock_render_template.return_value = "this is test"
    with admin_blueprint.test_client() as client:
        with client.session_transaction() as sess:
            sess["user"] = "test_user"
        response = client.get("/admin/module/module1")
        mock_render_template.assert_called_with("module1.html", module=CMS_MODULE)
        assert response.status_code == 200
        assert response.data.decode("utf-8") == "this is test"
