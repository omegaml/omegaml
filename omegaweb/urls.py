from django.conf.urls import url, include

from omegaweb import views
urlpatterns = [
    url(r'^dashboard', views.dashboard),
    url(r'^dataset/(.*)?/', views.dataview),
    url(r'^report/(.*)?/', views.report),
    url(r'^', include('landingpage.urls')),
]