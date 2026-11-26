
from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from accounts.models import Appointment, HealthRecord

User = get_user_model()


class MobileTokenObtainPairSerializer(TokenObtainPairSerializer):

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['username'] = user.username
        token['role'] = user.role
        return token

    def validate(self, attrs):
        data = super().validate(attrs)

        if getattr(self.user, 'role', '').lower() != 'student':
            raise serializers.ValidationError(
                'Only student accounts can access the mobile application.'
            )

        if getattr(self.user, 'verification_status', '').lower() != 'verified':
            raise serializers.ValidationError(
                'Your student account must be verified before logging in.'
            )

        data['user'] = UserProfileSerializer(self.user).data
        return data


class UserProfileSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'first_name',
            'middle_name',
            'last_name',
            'email',
            'role',
            'id_number',
            'sex',
            'course',
            'department',
            'year_block',
            'contact_number',
            'profile_picture',
            'verification_status',
        ]
        read_only_fields = fields


class StudentProfileUpdateSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = [
            'first_name',
            'middle_name',
            'last_name',
            'email',
            'contact_number',
            'sex',
            'course',
            'year_block',
            'profile_picture',
        ]

    def validate_email(self, value):
        queryset = User.objects.filter(
            email__iexact=value
        ).exclude(pk=self.instance.pk)

        if queryset.exists():
            raise serializers.ValidationError(
                'This email address is already in use.'
            )

        return value


class MobilePasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate_current_password(self, value):
        user = self.context['request'].user

        if not user.check_password(value):
            raise serializers.ValidationError(
                'Current password is incorrect.'
            )

        return value

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError({
                'confirm_password': 'Passwords do not match.'
            })

        return attrs

    def save(self):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save(update_fields=['password'])
        return user


class AppointmentSerializer(serializers.ModelSerializer):

    class Meta:
        model = Appointment
        fields = '__all__'
        read_only_fields = [
            'id',
            'student',
            'status',
        ]


class HealthRecordSerializer(serializers.ModelSerializer):

    class Meta:
        model = HealthRecord
        fields = '__all__'
        read_only_fields = [
            field.name
            for field in HealthRecord._meta.get_fields()
            if getattr(field, 'concrete', False)
        ]
