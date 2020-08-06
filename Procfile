web: gunicorn app.wsgi -c config/conf_gunicorn.py
worker: celery worker --app omegaml.celeryapp -E --loglevel=debug  --max-tasks-per-child 1 -Q $CELERY_Q
omegaops: celery worker --app omegaops.celeryapp -E --loglevel=debug -Q omegaops --max-tasks-per-child 1
scheduler:  celery beat --app omegaops.celeryapp --loglevel=debug
notebook: scripts/omegajobs.sh
dask: dask-scheduler
daskworker: PYTHONPATH=. && dask-worker localhost:8786
