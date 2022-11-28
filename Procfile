web: gunicorn app.wsgi -c config/conf_gunicorn.py
worker: celery --app omegaml.celeryapp worker -E --loglevel=debug  --max-tasks-per-child 1 -Q $CELERY_Q
omegaops: celery --app omegaops.celeryapp worker -E --loglevel=debug -Q omegaops --max-tasks-per-child 1
scheduler:  celery --app omegaops.celeryapp beat --loglevel=debug
notebook: scripts/omegajobs.sh
dask: dask-scheduler
daskworker: PYTHONPATH=. && dask-worker localhost:8786
