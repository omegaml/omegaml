from django.urls import re_path as url, include
from django.contrib import admin

from app.apiconfig import omega_apis, admin_apis

admin.autodiscover()

urlpatterns = [
    url(r'^', include('omegaweb.urls')),
    url(r'^accounts/', include('allauth.urls')),
    url('^payments/', include('payments.urls')),
    url('^orders/', include('orders.urls')),
]

urlpatterns += [*omega_apis.urls]
urlpatterns += [*admin_apis.urls]

# FIXME admin.site.urls and admin_apis.urls conflict
# -- admin.site.urls must be last
urlpatterns += [
    url(r'^admin/', admin.site.urls),
]

