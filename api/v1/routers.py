from rest_framework.routers import DefaultRouter
from apps.users.views import (
    UserViewSet, OfficerProfileViewSet, CommanderProfileViewSet,
    HRProfileViewSet, CommanderAssignmentViewSet
)
from apps.users.views_auth import CustomTokenObtainPairView
from apps.users.views import AuthViewSet

from apps.directory.views import (
    RankViewSet, UnitViewSet, PositionViewSet, PositionRequirementViewSet, CompetencyViewSet,
    CompetencyRequirementViewSet, ProviderViewSet, TrainingCourseViewSet
)

router = DefaultRouter()

# Users
router.register(r'users', UserViewSet, basename='user')
router.register(r'officers', OfficerProfileViewSet, basename='officer')
router.register(r'commanders', CommanderProfileViewSet, basename='commander')
router.register(r'hr', HRProfileViewSet, basename='hr')
router.register(r'assignments', CommanderAssignmentViewSet, basename='assignment')

# Directory (справочники)
router.register(r'directory/ranks', RankViewSet, basename='dir-ranks')
router.register(r'directory/units', UnitViewSet, basename='dir-units')
router.register(r'directory/positions', PositionViewSet, basename='dir-positions')
router.register(r'directory/position-requirements', PositionRequirementViewSet, basename='dir-position-reqs')
router.register(r'directory/competencies', CompetencyViewSet, basename='dir-competencies')
router.register(r'directory/competency-requirements', CompetencyRequirementViewSet, basename='dir-competency-reqs')
router.register(r'directory/providers', ProviderViewSet, basename='dir-providers')
router.register(r'directory/courses', TrainingCourseViewSet, basename='dir-courses')

urlpatterns = router.urls