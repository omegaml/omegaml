from os import abort

from flask import Blueprint, app, render_template
from werkzeug.utils import redirect

from omegaml.server.dashboard.views.admin import users
from omegaml.server.util import debug_only

omega_bp = Blueprint('omega-server', __name__, template_folder='templates')

from omegaml.server.dashboard.views.respository import scripts, datasets, jobs, models, dashboard
from omegaml.server.dashboard.views.runtime import summary, streams, tracking


@omega_bp.route('/')
def index():
    return 'index'


@omega_bp.route('/docs')
def docs():
    return redirect("https://omegaml.github.io/omegaml/", code=302)


@debug_only
@omega_bp.route('/test/modal/<path:template>')
def modal_test(template):
    if not app.debug:
        abort(401)
    return render_template(f'dashboard/{template}')


# add all sub views
# -- repository
dashboard.create_view(omega_bp)
models.create_view(omega_bp)
datasets.create_view(omega_bp)
jobs.create_view(omega_bp)
scripts.create_view(omega_bp)
# -- runtime
summary.create_view(omega_bp)
streams.create_view(omega_bp)
tracking.create_view(omega_bp)
# -- admin
users.create_view(omega_bp)
