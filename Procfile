web: .local/bin/caddy run
omegaml: PORT=8000 python -m omegaml.server
base: PORT=5002 python app1.py
#sse: PORT=5001 python app2.py
sse: PORT=5001 python ssechat.py
runtime: om runtime celery worker --flags "--loglevel=DEBUG"


