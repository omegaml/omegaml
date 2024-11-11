from os import abort

import flask
from flask import Blueprint, app, render_template, url_for, render_template_string
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
    # several places to specify contents of explain tab
    # -- object metadata (attributes.explain)
    segment_template_fqdn = f'.system/explain/{segment}'
    # -- explain dataset (attributes.docs)
    obj_template_fqdn = f'.system/explain/{segment}/{name}'
    # -- fixed template for all objects in segment
    fixed_segment_template = f'dashboard/explain/{segment}.rst'
    # -- fixed default template for all objects, all segments (this is a catch-all fallback)
    fixed_default_template = f'dashboard/explain/default.rst'
    obj_meta = None
    template_string = ""
    defaults = {}
    # resolve template, in this order
    # 1. if object's metadata is available, use its attributes.explain as a template string
    # 2. elif there is a obj explain dataset, use its attributes.docs as a template string
    # 3. elif there is a segment explain dataset, use its attributes.docs as a template string
    # 4. elif there is a segment template file, use it
    # 5. else render the default template
    # note, for consistency the obj and segment template datasets can also use attributes.explain
    # instead of attributes.docs, however attributes.docs is preferred for template datasets, as
    # attributes.docs can be edited in the dashboard.
    if om is not None:
        defaults = om.defaults
        if name and isinstance(getattr(om, segment), OmegaStore):
            store = getattr(om, segment)
            obj_meta = store.metadata(name)
            template_string = obj_meta.attributes.get('explain', '').strip()
        elif name and om.datasets.exists(obj_template_fqdn):
            obj_meta = om.datasets.metadata(obj_template_fqdn)
            template_string = obj_meta.attributes.get('docs', '').strip()
            template_string = template_string or obj_meta.attributes.get('explain', '').strip()
        elif om.datasets.exists(segment_template_fqdn):
            obj_meta = om.datasets.metadata(segment_template_fqdn)
            template_string = obj_meta.attributes.get('docs', '').strip()
            template_string = template_string or obj_meta.attributes.get('explain', '').strip()
    # finally, render the template
    with stripblocks():
        # always strip blocks from explain templates (no blank lines due to jinja blocks)
        try:
            if template_string:
                return render_template_string(template_string, segment=segment, metadata=obj_meta, defaults=defaults)
            else:
                result = render_template(fixed_segment_template, segment=segment, metadata=obj_meta, defaults=defaults)
        except Exception as e:
            result = render_template(fixed_default_template, segment=segment, metadata=obj_meta, error=e,
                                     defaults=defaults)
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
