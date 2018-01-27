from django.conf.urls import patterns, include, url
from django.contrib import admin

from app.apiconfig import apis
admin.autodiscover()

urlpatterns = patterns('',
                       url(r'^', include('omegaweb.urls')),
                       url(r'^accounts/', include('allauth.urls')),
                       url(r'^admin/', include(admin.site.urls)),
                       url('^payments/', include('payments.urls')),
                       url('^orders/', include('orders.urls')),
                       )

urlpatterns += patterns('', *apis.urls)
