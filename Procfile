web: python manage.py runserver
worker: celery worker --app omegaml.celeryapp -E -B --loglevel=debug --heartbeat-interval $CELERY_HEARTBEAT
