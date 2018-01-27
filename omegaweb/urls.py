from django.conf.urls import url, include

from omegaweb import views
urlpatterns = [
    url(r'^', views.index),
    #url(r'^', include('landingpage.urls')),
]
