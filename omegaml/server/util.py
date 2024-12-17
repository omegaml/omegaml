import base64
import json
import logging
from contextlib import contextmanager
from flask import current_app, jsonify, url_for
from functools import wraps, cache
from pathlib import Path
from urllib.parse import unquote
from werkzeug.exceptions import abort

logger = logging.getLogger(__name__)


def configure_database(db, app):
    from flask_migrate import Migrate
    db.init_app(app)
    _default_db_path = Path(__file__).absolute().parent / 'db.sqlite3'
    app.config.setdefault('SQLALCHEMY_DATABASE_URI', _default_db_path)
    with app.app_context():
        db.create_all()
        Migrate(app, db)


def datatables_ajax(data, n_total=None, n_filtered=None, draw=0, ignore=None):
    # return datatables ajax response
    # https://datatables.net/manual/server-side#Returned-data
    n_total = n_total or len(data)
    n_filtered = n_filtered or len(data)
    ignore = ignore or []
    if isinstance(data, dict):
        columns = data.keys()
    elif isinstance(data, list) and data:
        columns = data[0].keys()
    else:
        columns = []
    columns = list(k for k in columns if not k in ignore)
    resp = {
        'data': data,
        'columns': columns,
        'recordsTotal': n_total,
        'recordsFiltered': n_filtered,
    }
    resp.update(draw=draw) if draw is not None else None
    return resp


def debug_only(f):
    # route decorator to only allow access in debug mode
    # https://stackoverflow.com/a/55729767/890242
    @wraps(f)
    def wrapped(**kwargs):
        if not current_app.debug:
            abort(404)
        return f(**kwargs)

    return wrapped


def json_abort(status_code, message=None, data=None):
    # abort with a json response
    message = message or 'unknown error occurred'
    response = jsonify(data or {'error': message})
    response.status_code = status_code
    abort(response)


def js_routes(app):
    """ return a base64 encoded dict of routes for js use

    Usage:
        1. Call this in your flask.create_app function:
            js_routes(app)
        2. Add this snippet to your template:
            var routes = JSON.parse(atob('{{ view.js_routes }}'));
            window.url_for = function(name) { return routes[name]; }
        3. Use the url_for function in your js code:
            var myUrl = url_for('my_view');
    """

    @cache
    def encode_routes():
        routes = {}
        for rule in app.url_map.iter_rules():
            try:
                # Check if the rule has arguments
                if rule.arguments:
                    # You can create a placeholder for required parameters
                    routes[rule.endpoint] = url_for(rule.endpoint, **{arg: f"{{{arg}}}" for arg in rule.arguments})
                else:
                    routes[rule.endpoint] = url_for(rule.endpoint)
                routes[rule.endpoint] = unquote(routes[rule.endpoint])
            except:
                logger.warn(f'cannot encode route {rule}')
        return base64.b64encode(json.dumps(routes).encode()).decode()

    @app.context_processor
    def inject_routes():
        # This function will be called for every request and will inject the encoded routes into the template context
        return dict(encoded_routes=encode_routes())


@contextmanager
def stripblocks(trim_blocks=True, lstrip_blocks=True):
    import flask
    app = flask.current_app
    original_trim = app.jinja_env.trim_blocks
    original_lstrip = app.jinja_env.lstrip_blocks
    app.jinja_env.trim_blocks = trim_blocks
    app.jinja_env.lstrip_blocks = lstrip_blocks
    try:
        yield
    finally:
        app.jinja_env.trim_blocks = original_trim
        app.jinja_env.lstrip_blocks = original_lstrip
