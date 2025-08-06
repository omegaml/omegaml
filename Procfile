web: .local/bin/caddy run
omegaml: PORT=8000 python -m omegaml.server
base: PORT=5002 python app1.py
#sse: PORT=5001 python app2.py
#sse-test: FLASK_RUN_PORT=5001 flask -A omegaml.server.events:create_app run
sse: gunicorn "omegaml.server.events:create_app()" -k gevent -b localhost:5001 --threads 50
runtime: om runtime celery worker --flags "--loglevel=DEBUG"


