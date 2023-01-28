from flask_migrate import Migrate
from pathlib import Path


def configure_database(db, app):
    db.init_app(app)
    _default_db_path = Path(__file__).absolute().parent / 'db.sqlite3'
    app.config.setdefault('SQLALCHEMY_DATABASE_URI', _default_db_path)
    with app.app_context():
        db.create_all()
        Migrate(app, db)

