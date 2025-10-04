from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .routers import urlpatterns as router_urls
from apps.users.views_auth import CustomTokenObtainPairView
from apps.users.views import AuthViewSet

auth = AuthViewSet.as_view({
    'post': 'register'
})

urlpatterns = [
    path('', include(router_urls)),
    path('auth/login/', CustomTokenObtainPairView.as_view(), name='login'),
    path('auth/register/', AuthViewSet.as_view({'post': 'register'}), name='register'),
    path('auth/verify-email/', AuthViewSet.as_view({'post': 'verify_email'}), name='verify-email'),
    path('auth/reset-password/', AuthViewSet.as_view({'post': 'reset_password'}), name='reset-password'),
    path('auth/reset-password-confirm/', AuthViewSet.as_view({'post': 'reset_password_confirm'}), name='reset-password-confirm'),
]
