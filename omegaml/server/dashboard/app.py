from os import abort

import flask
from flask import Blueprint, app, render_template, url_for, render_template_string
from jinja2 import TemplateNotFound
from omegaml.server.dashboard.views.admin import users
from omegaml.server.dashboard.views.cards import plotcards
from omegaml.server.util import debug_only, stripblocks
from werkzeug.utils import redirect

omega_bp = Blueprint('omega-server', __name__,
                     static_folder='static',
                     template_folder='templates')

from omegaml.server.dashboard.views.respository import scripts, datasets, jobs, models, dashboard
from omegaml.server.dashboard.views.runtime import summary, streams, tracking


@omega_bp.route('/')
def index():
    return redirect(url_for('omega-server.index_index'))


@omega_bp.route('/docs')
def docs():
    return redirect("https://omegaml.github.io/omegaml/", code=302)


@debug_only
@omega_bp.route('/test/modal/<path:template>')
def modal_test(template):
    if not app.debug:
        abort(401)
    return render_template(f'dashboard/{template}')


@omega_bp.route('/explain/<string:segment>')
def explain(segment):
    from omegaml.store import OmegaStore
    name = flask.request.args.get('name')
    om = getattr(flask.current_app, 'current_om')
    template_fqdn = f'.system/explain/{segment}'
    # get object metadata for explained object
    if name and om is not None and isinstance(getattr(om, segment), OmegaStore):
        store = getattr(om, segment)
        obj_meta = store.metadata(name)
    else:
        obj_meta = None
    if om is not None and om.datasets.exists(template_fqdn):
        explain_meta = om.datasets.metadata(template_fqdn)
        template = explain_meta.attributes.get('docs', '').strip()
        return render_template_string(template, segment=segment, metadata=obj_meta)
    with stripblocks():
        # always strip blocks from explain tempaltes (no blank lines due to jinja blocks)
        try:
            result = render_template(f'dashboard/explain/{segment}.rst', segment=segment, metadata=obj_meta)
        except TemplateNotFound:
            result = render_template(f'dashboard/explain/default.rst', segment=segment)
    return result


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
# -- cards
plotcards.create_view(omega_bp)
