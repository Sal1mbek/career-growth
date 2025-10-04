# apps/users/views_auth.py (можно держать вместе с ViewSet или отдельно)
from rest_framework_simplejwt.views import TokenObtainPairView
from .auth import EmailTokenObtainPairSerializer

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = EmailTokenObtainPairSerializer
