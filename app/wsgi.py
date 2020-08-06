"""
WSGI config for x project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/1.6/howto/deployment/wsgi/
"""

import os

from stackable import StackableSettings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")
application = StackableSettings.get_wsgi_application()
