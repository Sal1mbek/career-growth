from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .routers import urlpatterns as router_urls
from django.conf import settings
from django.conf.urls.static import static
from apps.users.views_auth import (
    CustomTokenObtainPairView,
    verify_email_django,
    ResendVerificationEmailAPI
)
from apps.users.views import AuthViewSet

auth = AuthViewSet.as_view({
    'post': 'register'
})

urlpatterns = [
    path('', include(router_urls)),
    path('auth/login/', CustomTokenObtainPairView.as_view(), name='login'),
    path('auth/register/', AuthViewSet.as_view({'post': 'register'}), name='register'),
    path('auth/verify-email/<uidb64>/<token>/', verify_email_django, name='verify-email'),
    path('auth/resend-verification/', ResendVerificationEmailAPI.as_view(), name='resend-verification'),
    path('auth/reset-password/', AuthViewSet.as_view({'post': 'reset_password'}), name='reset-password'),
    path('auth/reset-password-confirm/', AuthViewSet.as_view({'post': 'reset_password_confirm'}), name='reset-password-confirm'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
