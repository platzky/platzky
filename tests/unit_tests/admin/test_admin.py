import pytest
from unittest.mock import Mock, patch
from flask import session
from platzky.admin.admin import create_admin_blueprint

@pytest.fixture
def admin_blueprint():
    mock_db = Mock()
    mock_login_methods = Mock()
    mock_locale_func = Mock()
    return create_admin_blueprint(mock_login_methods, mock_db, mock_locale_func)

@patch('platzky.admin.admin.render_template')
def admin_panel_renders_login_when_no_user(mock_render_template, admin_blueprint):
    with admin_blueprint.test_request_context('/admin/'):
        session['user'] = None
        response = admin_blueprint.view_functions['admin_panel']()
        mock_render_template.assert_called_with('login.html', login_methods=Mock())

@patch('platzky.admin.admin.render_template')
def admin_panel_renders_admin_when_user_exists(mock_render_template, admin_blueprint):
    mock_db = Mock()
    mock_db.get_plugins_data.return_value = [{'name': 'plugin1'}, {'name': 'plugin2'}]
    with admin_blueprint.test_request_context('/admin/'):
        session['user'] = 'test_user'
        response = admin_blueprint.view_functions['admin_panel']()
        mock_render_template.assert_called_with('admin.html', user='test_user', cms_modules={'plugins': ['plugin1', 'plugin2']})

@patch('platzky.admin.admin.render_template')
def admin_panel_handles_empty_plugins_data(mock_render_template, admin_blueprint):
    mock_db = Mock()
    mock_db.get_plugins_data.return_value = []
    with admin_blueprint.test_request_context('/admin/'):
        session['user'] = 'test_user'
        response = admin_blueprint.view_functions['admin_panel']()
        mock_render_template.assert_called_with('admin.html', user='test_user', cms_modules={'plugins': []})
