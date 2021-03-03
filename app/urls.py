from django.conf.urls import url, include
from django.contrib import admin

from app.apiconfig import omega_apis, admin_apis
admin.autodiscover()

urlpatterns = [
                       url(r'^', include('omegaweb.urls')),
                       url(r'^accounts/', include('allauth.urls')),
                       url(r'^admin/', admin.site.urls),
                       url('^payments/', include('payments.urls')),
                       url('^orders/', include('orders.urls')),
              ]

urlpatterns += [*omega_apis.urls]
urlpatterns += [*admin_apis.urls]

"""
see https://github.com/jazzband/django-debug-toolbar/issues/1035
try:
    import debug_toolbar
except:
    pass
else:
    urlpatterns += [r'^__debug__/', debug_toolbar.urls]
"""
