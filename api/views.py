
from django.contrib.auth import get_user_model
from django.db.models import Count
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from accounts.models import Appointment, HealthRecord

from .serializers import (
    MobileTokenObtainPairSerializer,
    UserProfileSerializer,
    StudentProfileUpdateSerializer,
    MobilePasswordChangeSerializer,
    AppointmentSerializer,
    HealthRecordSerializer,
)

User = get_user_model()


class MobileLoginView(TokenObtainPairView):
    serializer_class = MobileTokenObtainPairSerializer


class MobileTokenRefreshView(TokenRefreshView):
    permission_classes = [permissions.AllowAny]


class MobileProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data)

    def patch(self, request):
        if getattr(request.user, 'role', '').lower() != 'student':
            return Response(
                {'detail': 'Only students can update their mobile profile.'},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = StudentProfileUpdateSerializer(
            request.user,
            data=request.data,
            partial=True
        )

        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(UserProfileSerializer(request.user).data)

    def put(self, request):
        if getattr(request.user, 'role', '').lower() != 'student':
            return Response(
                {'detail': 'Only students can update their mobile profile.'},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = StudentProfileUpdateSerializer(
            request.user,
            data=request.data
        )

        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(UserProfileSerializer(request.user).data)


class MobilePasswordChangeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = MobilePasswordChangeSerializer(
            data=request.data,
            context={'request': request}
        )

        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {'detail': 'Password changed successfully.'},
            status=status.HTTP_200_OK
        )


class StudentDashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if getattr(request.user, 'role', '').lower() != 'student':
            return Response(
                {'detail': 'Student access only.'},
                status=status.HTTP_403_FORBIDDEN
            )

        appointments = Appointment.objects.filter(student=request.user)
        health_records = HealthRecord.objects.filter(student=request.user)

        return Response({
            'appointments_count': appointments.count(),
            'health_records_count': health_records.count(),
            'recent_appointments': AppointmentSerializer(
                appointments.order_by('-id')[:5],
                many=True
            ).data,
        })


class StudentAppointmentsView(generics.ListCreateAPIView):
    serializer_class = AppointmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self.request.user, 'role', '').lower() != 'student':
            return Appointment.objects.none()

        return Appointment.objects.filter(
            student=self.request.user
        ).order_by('-id')

    def perform_create(self, serializer):
        if getattr(self.request.user, 'role', '').lower() != 'student':
            raise permissions.PermissionDenied(
                'Only students can request appointments.'
            )

        serializer.save(student=self.request.user)


class StudentHealthRecordsView(generics.ListAPIView):
    serializer_class = HealthRecordSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self.request.user, 'role', '').lower() != 'student':
            return HealthRecord.objects.none()

        return HealthRecord.objects.filter(
            student=self.request.user
        ).order_by('-id')
