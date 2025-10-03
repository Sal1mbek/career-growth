from django.urls import path, include
from .routers import urlpatterns as router_urls

urlpatterns = [
    path('', include(router_urls))
]
