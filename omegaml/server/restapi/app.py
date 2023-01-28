import os
from flask import Flask
from werkzeug.utils import redirect

from omegaml.server.restapi.resources import omega_bp


def create_app(*args, **kwargs):
    from omegaml.server.restapi.util import JSONEncoder

    app = Flask(__name__)
    # ensure slashes in URIs are matched as specified
    # see https://stackoverflow.com/a/33285603/890242
    app.url_map.strict_slashes = True
    # use Flask json encoder to support datetime
    app.config['RESTX_JSON'] = {'cls': JSONEncoder}
    # disable 404 help as it interferes with our api.errorhandler
    app.config['RESTX_ERROR_404_HELP'] = False

    @app.route('/')
    def index():
        return redirect("/api/docs", code=302)

    @app.route('/docs')
    def docs():
        return redirect("https://omegaml.github.io/omegaml/", code=302)

    app.register_blueprint(omega_bp)
    return app


def serve_objects():
    from omegaml.server.restapi import resource_filter
    import re

    specs = os.environ.get('OMEGA_RESTAPI_FILTER')
    if specs:
        respecs = [re.compile(s) for s in specs.split(';') if s]
        resource_filter.extend(respecs)
    return create_app()
