"""

TODO: check all CDN dependencies, e.g. toastui

"""

import logging
import os
import warnings
from flask import Flask
from flask_session import Session
from matplotlib import pyplot as plt

from omegaml.server.config import CONFIG_MAP
from omegaml.server.logutil import configure_logging, logutil_flask
from omegaml.server.restapi.util import JSONEncoder
from omegaml.server.util import js_routes
from omegaml.store import OmegaStore
from omegaml.util import json_dumps_np

logger = logging.getLogger(__name__)


def create_app(server=None, url_prefix=None, configure=False, *args, **kwargs):
    from omegaml.server.restapi.resources import create_app as create_restapi_app
    from omegaml.server.dashboard.app import omega_bp as dashboard_bp

    url_prefix = url_prefix[:-1] if url_prefix and url_prefix.endswith('/') else url_prefix or ''
    # local configuration
    if configure or server is None:
        # only do this running standalone
        # -- ensure url_for('static') files are served from blue blueprint
        app = Flask(__name__,
                    static_url_path=f'{url_prefix}/static')
        should_debug = os.getenv('DEBUG', '0')[0].lower() in ('1', 'y', 't')
        config = CONFIG_MAP['dev'] if should_debug else CONFIG_MAP['live']
        app.config.from_object(config)
        configure_logging(settings=app.config)
        logutil_flask(app)
        Session(app)

        # simulate user
        # TODO use login manager
        @app.context_processor
        def simulate_user():
            class user:
                username = 'admin'

            return dict(current_user=user())
    else:
        app = server
    # ensure slashes in URIs are matched as specified
    # see https://stackoverflow.com/a/33285603/890242
    app.url_map.strict_slashes = True
    # assets are served from the blueprint folder
    app.root_path = dashboard_bp.root_path
    app.static_folder = 'static'
    app.config['ASSETS_ROOT'] = f'{url_prefix}/static/assets'
    # use Flask json encoder to support datetime
    app.config['RESTX_JSON'] = {'cls': JSONEncoder}
    # configure swagger ui (flask-restx)
    # -- https://flask-restx.readthedocs.io/en/latest/swagger.html
    app.config['SWAGGER_UI_DOC_EXPANSION'] = 'list'
    app.config['CARDS_ENABLED'] = True if os.environ.get('OMEGA_CARDS_ENABLED') in ('1', 'true', 'yes') else False
    app.register_blueprint(dashboard_bp, url_prefix=url_prefix)
    restapi_bp = create_restapi_app(url_prefix=url_prefix)
    app.register_blueprint(restapi_bp, url_prefix=url_prefix)
    js_routes(app)
    app.current_om = setup_omega()
    # use our custom json_dumps function
    # -- see https://stackoverflow.com/a/65129122/890242
    app.jinja_env.policies['json.dumps_function'] = json_dumps_np
    # -- set matplotlib backend to non-interactive
    plt.switch_backend('Agg')
    # avoid reloading the app due to queryops warnings
    # TODO: queryops should have a better way to handle this
    warnings.filterwarnings("ignore", module='omegaml.store.queryops')

    # add a static route to the blueprint
    # -- this is necessary to serve static files from the blueprint
    # -- we try bc the server/Flask() may already have endpoint=static route
    try:
        @app.route(f'{url_prefix}/static/<path:filename>', endpoint='static')
        def app_static(filename):
            return app.send_static_file(filename)
    except (RuntimeError, AssertionError) as e:
        logger.warning((f"could not add {url_prefix}/static endpoint=static due to {e} "
                        f"- make sure that url_for('static') renders to {url_prefix} or use url_for('omega-server.static')"))

    @app.context_processor
    def setconfig():
        cards_enabled = (getattr(app.current_om.defaults, 'OMEGA_CARDS_ENABLED', False)
                         or app.config.get('CARDS_ENABLED', False))
        return dict(cards_enabled=cards_enabled)

    return app


def setup_omega():
    import omegaml as om
    om = om.setup()
    om.system: OmegaStore = getattr(om, 'system', om._make_store('.system'))
    admin_user = om.system.metadata('users/admin')
    if not admin_user:
        admin_user = om.system.put({}, 'users/admin', replace=True)
    return om


def serve_objects():
    from omegaml.server.restapi import resource_filter
    import re

    specs = os.environ.get('OMEGA_RESTAPI_FILTER')
    if specs:
        respecs = [re.compile(s) for s in specs.split(';') if s]
        resource_filter.extend(respecs)
    return create_app()
