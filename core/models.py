from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    ROLE_CHOICES = (
        ('student', 'Student'),
        ('teacher', 'Teacher'),
        ('staff', 'Clinic Staff')
    )

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='student'
    )

    contact_number = models.CharField(
        max_length=20,
        blank=True,
        null=True
    )

    id_number = models.CharField(
        max_length=50,
        blank=True,
        null=True
    )

    department = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    def __str__(self):
        return self.get_full_name() or self.username


class TeacherStudent(models.Model):
    teacher = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='assigned_students'
    )

    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='assigned_teachers'
    )

    added_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['teacher', 'student'],
                name='unique_teacher_student'
            )
        ]

        ordering = [
            'student__last_name',
            'student__first_name'
        ]

    def __str__(self):
        return f"{self.teacher} - {self.student}"


class Appointment(models.Model):
    STATUS_CHOICES = (
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rescheduled', 'Rescheduled'),
        ('Rejected', 'Rejected'),
        ('Completed', 'Completed'),
    )

    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='appointments'
    )

    concern = models.TextField()

    preferred_date = models.DateField()

    preferred_time = models.TimeField()

    scheduled_date = models.DateField(
        blank=True,
        null=True
    )

    scheduled_time = models.TimeField(
        blank=True,
        null=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='Pending'
    )

    rejection_reason = models.TextField(
        blank=True,
        null=True
    )

    staff_notes = models.TextField(
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return f"{self.student} - {self.preferred_date} - {self.status}"


class Referral(models.Model):
    STATUS_CHOICES = (
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rescheduled', 'Rescheduled'),
        ('Rejected', 'Rejected'),
        ('Completed', 'Completed'),
    )

    teacher = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='referred_by'
    )

    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='referrals_received',
        null=True,
        blank=True
    )

    student_name = models.CharField(
        max_length=255
    )

    concern = models.TextField()

    suggested_date = models.DateField()

    suggested_time = models.TimeField()

    scheduled_date = models.DateField(
        blank=True,
        null=True
    )

    scheduled_time = models.TimeField(
        blank=True,
        null=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='Pending'
    )

    rejection_reason = models.TextField(
        blank=True,
        null=True
    )

    staff_notes = models.TextField(
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return f"{self.student_name} - {self.status}"


class HealthRecord(models.Model):
    appointment = models.OneToOneField(
        Appointment,
        on_delete=models.CASCADE,
        related_name='health_record'
    )

    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='health_records'
    )

    symptoms = models.TextField(
        blank=True,
        null=True
    )

    diagnosis = models.TextField(
        blank=True,
        null=True
    )

    treatment = models.TextField(
        blank=True,
        null=True
    )

    notes = models.TextField(
        blank=True,
        null=True
    )

    recorded_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='recorded_health_records'
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return f"Health Record - {self.student}"


class SickNote(models.Model):
    appointment = models.OneToOneField(
        Appointment,
        on_delete=models.CASCADE,
        related_name='sick_note'
    )

    issued_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='issued_notes'
    )

    diagnosis = models.TextField()

    days_recommended = models.IntegerField()

    notes = models.TextField(
        blank=True,
        null=True
    )

    issued_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return f"Sick Note - {self.appointment}"