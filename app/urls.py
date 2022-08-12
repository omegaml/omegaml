from django.conf.urls import url, include
from django.contrib import admin

admin.autodiscover()

urlpatterns = [
    url(r'^', include('omegaee.urls')),
]

"""
see https://github.com/jazzband/django-debug-toolbar/issues/1035
try:
    import debug_toolbar
except:
    pass
else:
    urlpatterns += [r'^__debug__/', debug_toolbar.urls]
"""

# enable custom urls
try:
    from app import custom_urls
except:
    pass
else:
    custom_urls.setup(urlpatterns)
