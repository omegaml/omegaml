import os

from flask import Flask
from flask_restx import Api
from werkzeug.utils import redirect


def create_app(*args, **kwargs):
    from omegaml.restapi.resources import omega_bp

    app = Flask(__name__)
    # ensure slashes in URIs are matched as specified
    # see https://stackoverflow.com/a/33285603/890242
    app.url_map.strict_slashes = True
    # use Flask json encoder to support datetime
    app.config['RESTX_JSON'] = {'cls': app.json_encoder}
    app.register_blueprint(omega_bp)

    @app.route('/docs')
    def docs():
        return redirect("https://omegaml.github.io/omegaml/", code=302)

    return app


def serve_objects():
    from omegaml.restapi import resource_filter
    import re

    specs = os.environ.get('OMEGA_RESTAPI_FILTER')
    if specs:
        respecs = [re.compile(s) for s in specs.split(';') if s]
        resource_filter.extend(respecs)
    return create_app()
