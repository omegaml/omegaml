web: gunicorn app.wsgi -c config/conf_gunicorn.py
worker: celery worker --app omegaml.celeryapp -E -B --loglevel=debug 
notebook: cd omegajobs && jupyter notebook --notebook-dir .
dask: dask-scheduler 
daskworker: PYTHONPATH=. && dask-worker localhost:8786
