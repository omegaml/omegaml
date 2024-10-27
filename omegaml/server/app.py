import os
import warnings
from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from matplotlib import pyplot as plt

from omegaml.server.config import config_dict
from omegaml.server.logutil import configure_logging, logutil_flask
from omegaml.server.restapi.util import JSONEncoder
from omegaml.server.util import configure_database, js_routes
from omegaml.store import OmegaStore
from omegaml.util import json_dumps_np

db = SQLAlchemy()
login_manager = LoginManager()


def create_app(server=None, url_prefix=None, *args, **kwargs):
    from omegaml.server.restapi.resources import omega_bp as restapi_bp
    from omegaml.server.dashboard.app import omega_bp as dashboard_bp
    from omegaml.server.dashboard.authentication.routes import blueprint as accounts_bp

    # load configuration
    DEBUG = (os.getenv('DEBUG', 'False') == 'True')
    get_config_mode = 'Debug' if DEBUG else 'Production'
    try:
        # Load the configuration using the default values
        config = config_dict[get_config_mode.capitalize()]
    except KeyError:
        exit('Error: Invalid <config_mode>. Expected values [Debug, Production] ')

    app = server or Flask(__name__)
    configure_logging(settings=app.config)
    logutil_flask(app)
    # ensure slashes in URIs are matched as specified
    # see https://stackoverflow.com/a/33285603/890242
    app.url_map.strict_slashes = True
    # use Flask json encoder to support datetime
    app.config['RESTX_JSON'] = {'cls': JSONEncoder}
    # configure swagger ui (flask-restx)
    # -- https://flask-restx.readthedocs.io/en/latest/swagger.html
    app.config['SWAGGER_UI_DOC_EXPANSION'] = 'list'
    app.config.from_object(config)
    configure_database(db, app)
    login_manager.init_app(app)
    app.register_blueprint(accounts_bp, url_prefix=url_prefix)
    app.register_blueprint(dashboard_bp, url_prefix=url_prefix)
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
