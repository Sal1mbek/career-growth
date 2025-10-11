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

from apps.officers.views import (
    PositionHistoryViewSet, OfficerDocumentViewSet,
    CourseEnrollmentViewSet, CertificateViewSet
)

from apps.assessments.views import AssessmentViewSet, RaterViewSet, CompetencyRatingViewSet

from apps.career.views import CareerTrajectoryViewSet, PlanStepViewSet, RecommendationViewSet

from apps.staffing.views import VacancyViewSet, CandidateMatchViewSet, AssignmentViewSet

from apps.comms.views import (
    NotificationViewSet, SupportTicketViewSet, TicketMessageViewSet
)

from apps.insights.views import TrajectoryForecastViewSet

from apps.audit.views import AuditLogViewSet

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

# Officers
router.register(r'officers/position-history', PositionHistoryViewSet, basename='officer-history')
router.register(r'officers/documents', OfficerDocumentViewSet, basename='officer-docs')
router.register(r'officers/enrollments', CourseEnrollmentViewSet, basename='officer-enrollments')
router.register(r'officers/certificates', CertificateViewSet, basename='officer-certificates')

# Assessment (Аттестации и оценки)
router.register(r'assessments', AssessmentViewSet, basename='assessments')
router.register(r'assessments/raters', RaterViewSet, basename='raters')
router.register(r'assessments/ratings', CompetencyRatingViewSet, basename='ratings')

# Career
router.register(r'career/trajectories', CareerTrajectoryViewSet, basename='career-trajectory')
router.register(r'career/steps', PlanStepViewSet, basename='career-step')
router.register(r'career/recommendations', RecommendationViewSet, basename='career-recommendation')

# Staffing (Vacancy)
router.register(r'staffing/vacancies', VacancyViewSet, basename='vacancies')
router.register(r'staffing/candidates', CandidateMatchViewSet, basename='candidates')
router.register(r'staffing/assignments', AssignmentViewSet, basename='assignments')

# Communication and support
router.register(r'comms/notifications', NotificationViewSet, basename='notifications')
router.register(r'comms/tickets', SupportTicketViewSet, basename='tickets')
router.register(r'comms/ticket-messages', TicketMessageViewSet, basename='ticket-messages')

# Insights
router.register(r'insights/forecasts', TrajectoryForecastViewSet, basename='insights-forecasts')

# Audit
router.register(r'audit/logs', AuditLogViewSet, basename='audit-logs')

urlpatterns = router.urls