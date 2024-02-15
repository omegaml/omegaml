from flask import current_app
from functools import wraps

from flask_migrate import Migrate
from pathlib import Path
from werkzeug.exceptions import abort


def configure_database(db, app):
    db.init_app(app)
    _default_db_path = Path(__file__).absolute().parent / 'db.sqlite3'
    app.config.setdefault('SQLALCHEMY_DATABASE_URI', _default_db_path)
    with app.app_context():
        db.create_all()
        Migrate(app, db)


def datatables_ajax(data, n_total=None, n_filtered=None):
    # return datatables ajax response
    # https://datatables.net/manual/server-side#Returned-data
    n_total = n_total or len(data)
    n_filtered = n_filtered or len(data)
    return {
        'data': data,
        'recordsTotal': n_total,
        'recordsFiltered': n_filtered,
    }


def debug_only(f):
    # https://stackoverflow.com/a/55729767/890242
    @wraps(f)
    def wrapped(**kwargs):
        if not current_app.debug:
            abort(404)
        return f(**kwargs)

    return wrapped