from django.urls import re_path as url, include
from django.contrib import admin

admin.autodiscover()

urlpatterns = [
    url(r'^', include('omegaee.urls')),
]

try:
    import django_admin_shell
except:
    pass
else:
    urlpatterns += [url(r'^admin/shell/', include('django_admin_shell.urls')),]

"""
see https://github.com/jazzband/django-debug-toolbar/issues/1035
"""
try:
    import debug_toolbar
except:
    pass
else:
    urlpatterns += [url(r'^__debug__/', include(debug_toolbar.urls)),]

