worker: celery worker --app omegaml.celeryapp -E -B --loglevel=DEBUG
notebook: jupyter notebook --allow-root --ip 0.0.0.0 --no-browser $JUPYTER_PARAM --port $JUPYTER_PORT
restapi: python -m omegaml.restapi
