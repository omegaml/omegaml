from flask import current_app, jsonify
from flask_migrate import Migrate
from functools import wraps
from pathlib import Path
from werkzeug.exceptions import abort


def configure_database(db, app):
    db.init_app(app)
    _default_db_path = Path(__file__).absolute().parent / 'db.sqlite3'
    app.config.setdefault('SQLALCHEMY_DATABASE_URI', _default_db_path)
    with app.app_context():
        db.create_all()
        Migrate(app, db)


def datatables_ajax(data, n_total=None, n_filtered=None, draw=0):
    # return datatables ajax response
    # https://datatables.net/manual/server-side#Returned-data
    n_total = n_total or len(data)
    n_filtered = n_filtered or len(data)
    if isinstance(data, dict):
        columns = list(data.keys())
    elif isinstance(data, list) and data:
        columns = list(data[0].keys())
    else:
        columns = []
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
