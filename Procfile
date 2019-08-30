web: gunicorn app.wsgi -c config/conf_gunicorn.py
worker: celery worker --app omegaml.celeryapp -E --loglevel=debug  --max-tasks-per-child 1
cloudmgr: celery worker --app omegaops.celeryapp -E --loglevel=debug
scheduler: celery beat --app omegaops.celeryapp --loglevel=debug
notebook: scripts/omegajobs.sh
dask: dask-scheduler 
daskworker: PYTHONPATH=. && dask-worker localhost:8786
