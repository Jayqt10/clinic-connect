
from django.urls import path
from rest_framework_simplejwt.views import TokenVerifyView

from .views import (
    MobileLoginView,
    MobileTokenRefreshView,
    MobileProfileView,
    MobilePasswordChangeView,
    StudentDashboardView,
    StudentAppointmentsView,
    StudentHealthRecordsView,
)

app_name = 'api'

urlpatterns = [
    path('auth/login/', MobileLoginView.as_view(), name='mobile_login'),
    path('auth/refresh/', MobileTokenRefreshView.as_view(), name='mobile_refresh'),
    path('auth/verify/', TokenVerifyView.as_view(), name='mobile_verify'),
    path('profile/', MobileProfileView.as_view(), name='mobile_profile'),
    path('password/change/', MobilePasswordChangeView.as_view(), name='mobile_password_change'),
    path('student/dashboard/', StudentDashboardView.as_view(), name='student_dashboard'),
    path('student/appointments/', StudentAppointmentsView.as_view(), name='student_appointments'),
    path('student/health-records/', StudentHealthRecordsView.as_view(), name='student_health_records'),
]
