web: gunicorn app.wsgi -c config/conf_gunicorn.py
worker: celery worker --app omegaml.celeryapp -E -B --loglevel=debug 
notebook: scripts/omegajobs.sh
dask: dask-scheduler 
daskworker: PYTHONPATH=. && dask-worker localhost:8786
