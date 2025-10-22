# apps/users/views_auth.py
from django.contrib.auth import get_user_model
from django.utils.http import urlsafe_base64_decode
from django.shortcuts import redirect
from django.contrib.auth.tokens import default_token_generator
from django.conf import settings
from rest_framework import permissions, views
from core.responses import APIResponse
from .auth import EmailTokenObtainPairSerializer
from .utils import send_verification_email

from rest_framework_simplejwt.views import TokenObtainPairView

User = get_user_model()


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = EmailTokenObtainPairSerializer


def verify_email_django(request, uidb64, token):
    """GET /api/v1/auth/verify-email/<uidb64>/<token>/ → редирект на фронт с флагом"""
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User._default_manager.get(pk=uid)
    except Exception:
        user = None

    ok = (user is not None and default_token_generator.check_token(user, token))
    if ok:
        user.email_verified = True
        if not user.is_active:
            user.is_active = True
        user.save(update_fields=['email_verified', 'is_active'])

    front = getattr(settings, "FRONTEND_APP_URL", "http://34.173.17.206/")
    return redirect(f"{front}/auth/verify-result?success={'1' if ok else '0'}")


class ResendVerificationEmailAPI(views.APIView):
    """POST /api/v1/auth/resend-verification/ {email} — всегда 200"""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get("email")
        user = User.objects.filter(email=email).first()
        if user and not getattr(user, "email_verified", False):
            try:
                send_verification_email(user, request)
            except Exception:
                pass
        return APIResponse.success({"detail": "Если аккаунт существует, письмо отправлено."})
