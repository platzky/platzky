#TODO consider moving this to a separate module, maybe in tests directory
from flask import url_for, session, redirect

def get_fake_login_html():
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
            <a href="/admin/fake-login/admin" class="btn btn-primary">Login as Admin</a>
            <a href="/admin/fake-login/nonadmin" class="btn btn-secondary">Login as Non-Admin</a>
          </div>
        </div>
      </div>
    </div>
    """
    return html

def setup_fake_login_routes(blueprint):
    """Add fake login routes to the provided blueprint."""
    @blueprint.route("/fake-login/<role>")
    def fake_login(role):
        if role == 'admin':
            session['user'] = {'username': 'admin', 'role': 'admin'}
        else:
            session['user'] = {'username': 'user', 'role': 'nonadmin'}
        return redirect(url_for('admin.admin_panel_home'))