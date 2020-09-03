from django.conf.urls import patterns, include, url
from django.contrib import admin

from app.apiconfig import omega_apis, admin_apis
admin.autodiscover()

urlpatterns = patterns('',
                       url(r'^', include('omegaweb.urls')),
                       url(r'^accounts/', include('allauth.urls')),
                       url(r'^admin/', include(admin.site.urls)),
                       url('^payments/', include('payments.urls')),
                       url('^orders/', include('orders.urls')),
                       )

urlpatterns += patterns('', *omega_apis.urls)
urlpatterns += patterns('', *admin_apis.urls)

"""
see https://github.com/jazzband/django-debug-toolbar/issues/1035
try:
    import debug_toolbar
except:
    pass
else:
    urlpatterns += patterns('', r'^__debug__/', include(debug_toolbar.urls))
"""
