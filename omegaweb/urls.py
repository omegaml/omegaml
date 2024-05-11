from django.urls import re_path as url, include
from django.urls import path
from jwt_auth import views as jwt_auth_views

from omegaweb import views

urlpatterns = [
    url(r'^dashboard', views.dashboard),
    url(r'^dataset/(.*)?/', views.dataview),
    url(r'^report/(.*)?/', views.report),
    url(r'^', include('landingpage.urls')),
]

urlpatterns += [
    # https://github.com/webstack/django-jwt-auth
    path("token-auth/", jwt_auth_views.jwt_token),
    path("token-refresh/", jwt_auth_views.refresh_jwt_token),
]
