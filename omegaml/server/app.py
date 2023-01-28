import os
from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import redirect

from omegaml.server.config import config_dict
from omegaml.server.restapi.util import JSONEncoder
from omegaml.server.util import configure_database

db = SQLAlchemy()
login_manager = LoginManager()


def create_app(*args, **kwargs):
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

    app = Flask(__name__)
    # ensure slashes in URIs are matched as specified
    # see https://stackoverflow.com/a/33285603/890242
    app.url_map.strict_slashes = True
    # use Flask json encoder to support datetime
    app.config['RESTX_JSON'] = {'cls': JSONEncoder}
    app.config.from_object(config)
    configure_database(db, app)
    login_manager.init_app(app)
    app.register_blueprint(accounts_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(restapi_bp)

    @app.route('/')
    def index():
        return 'index'

    @app.route('/docs')
    def docs():
        return redirect("https://omegaml.github.io/omegaml/", code=302)

    return app


def serve_objects():
    from omegaml.server.restapi import resource_filter
    import re

    specs = os.environ.get('OMEGA_RESTAPI_FILTER')
    if specs:
        respecs = [re.compile(s) for s in specs.split(';') if s]
        resource_filter.extend(respecs)
    return create_app()
