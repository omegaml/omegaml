web: gunicorn app.wsgi -c config/conf_gunicorn.py
worker: celery worker --app omegaml.celeryapp -E -B --loglevel=debug 
