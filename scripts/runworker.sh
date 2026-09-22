#!/bin/bash
pip install watchdog
watchmedo auto-restart --directory=. --pattern=*.py --recursive -- om runtime celery worker --flags "--loglevel=debug"
