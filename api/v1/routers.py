from rest_framework.routers import DefaultRouter
from apps.users.views import (
    UserViewSet, OfficerProfileViewSet, CommanderProfileViewSet,
    HRProfileViewSet, CommanderAssignmentViewSet
)
from apps.users.views_auth import CustomTokenObtainPairView
from apps.users.views import AuthViewSet

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'officers', OfficerProfileViewSet, basename='officer')
router.register(r'commanders', CommanderProfileViewSet, basename='commander')
router.register(r'hr', HRProfileViewSet, basename='hr')
router.register(r'assignments', CommanderAssignmentViewSet, basename='assignment')

urlpatterns = router.urls