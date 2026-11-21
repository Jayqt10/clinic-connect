
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower, Trim
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator


def validate_profile_picture_size(value):
    if value.size > 5 * 1024 * 1024:
        raise ValidationError("Profile picture must not exceed 5 MB.")


class User(AbstractUser):
    ROLE_CHOICES = (
        ('student', 'Student'),
        ('teacher', 'Teacher'),
        ('staff', 'Clinic Staff'),
    )

    EMPLOYMENT_STATUS_CHOICES = (
        ('regular', 'Regular'),
        ('contractual', 'Contractual'),
        ('part_time', 'Part-time'),
        ('temporary', 'Temporary'),
    )

    VERIFICATION_STATUS_CHOICES = (
        ('pending', 'Pending Verification'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
    )

    STAFF_POSITION_CHOICES = (
        ('admin', 'Clinic Administrator'),
        ('nurse', 'School Nurse'),
        ('receptionist', 'Clinic Receptionist'),
        ('records', 'Records and Monitoring Staff'),
    )

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='student'
    )

    profile_picture = models.ImageField(
        upload_to='profile_pictures/',
        blank=True,
        null=True,
        validators=[
            FileExtensionValidator(
                allowed_extensions=['jpg', 'jpeg', 'png', 'webp']
            ),
            validate_profile_picture_size
        ]
    )

    middle_name = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    id_number = models.CharField(
        max_length=50,
        blank=True,
        null=True
    )

    sex = models.CharField(
        max_length=20,
        blank=True,
        null=True
    )

    course = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    department = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    year_block = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    block = models.CharField(
        max_length=10,
        blank=True,
        null=True
    )

    contact_number = models.CharField(
        max_length=20,
        blank=True,
        null=True
    )

    staff_position = models.CharField(
        max_length=100,
        choices=STAFF_POSITION_CHOICES,
        blank=True,
        null=True
    )

    employment_status = models.CharField(
        max_length=30,
        choices=EMPLOYMENT_STATUS_CHOICES,
        blank=True,
        null=True
    )

    verification_status = models.CharField(
        max_length=20,
        choices=VERIFICATION_STATUS_CHOICES,
        default='pending',
        blank=True
    )

    verification_evidence = models.FileField(
        upload_to='student_verification_evidence/',
        blank=True,
        null=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                Lower(Trim("email")),
                condition=~Q(email=""),
                name="unique_user_email_ci",
            ),
            models.UniqueConstraint(
                Lower(Trim("id_number")),
                condition=(
                    Q(role="student")
                    & Q(id_number__isnull=False)
                    & ~Q(id_number="")
                ),
                name="unique_student_id_ci",
            ),
        ]

    def clean(self):
        super().clean()

        if self.role == 'staff':
            self.year_block = None
            self.block = None
            self.verification_status = 'verified'

        elif self.role == 'teacher':
            self.year_block = None
            self.block = None
            self.verification_status = 'verified'

    @property
    def department_obj(self):
        value = (self.department or '').strip()

        if not value:
            return None

        return (
            Department.objects.filter(name__iexact=value).first()
            or Department.objects.filter(code__iexact=value).first()
        )

    @property
    def department_room_count(self):
        dept = self.department_obj

        if dept is None:
            return None

        actual = Room.objects.filter(
            building__department=dept
        ).count()

        if actual:
            return actual

        return (
            dept.buildings.aggregate(
                total=models.Sum('total_rooms')
            )['total'] or 0
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

    added_at = models.DateTimeField(auto_now_add=True)

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

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.student} - {self.preferred_date} ({self.status})"


class Referral(models.Model):
    STATUS_CHOICES = (
        ('Approved', 'Sent (Immediate)'),
        ('Received', 'Received by Clinic'),
        ('Completed', 'Completed'),
    )

    teacher = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='referred_by'
    )

    student_name = models.CharField(
        max_length=255,
        blank=True
    )

    department = models.ForeignKey(
        'Department',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    building = models.ForeignKey(
        'Building',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    room = models.ForeignKey(
        'Room',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    location = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    symptoms = models.TextField(
        blank=True,
        null=True,
        help_text="Describe the symptoms experienced by the student."
    )

    concern = models.TextField(
        blank=True,
        null=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='Approved'
    )

    received_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='received_referrals'
    )

    received_at = models.DateTimeField(
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Emergency Referral: {self.student_name} - {self.status}"


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
        null=True,
        help_text="Record the symptoms reported by the student."
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

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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

    days_recommended = models.IntegerField()

    notes = models.TextField(
        blank=True,
        null=True
    )

    issued_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Sick Note - {self.appointment}"


class ClinicStatus(models.Model):
    is_available = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "Available" if self.is_available else "Unavailable"


class Department(models.Model):
    name = models.CharField(max_length=150, unique=True)

    code = models.CharField(
        max_length=50,
        blank=True,
        null=True
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Building(models.Model):
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name="buildings"
    )

    name = models.CharField(max_length=150)
    total_rooms = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.name} ({self.department.name})"


class Room(models.Model):
    building = models.ForeignKey(
        Building,
        on_delete=models.CASCADE,
        related_name="rooms",
        null=True,
        blank=True
    )

    floor = models.PositiveSmallIntegerField(default=1)
    room_number = models.CharField(max_length=50)

    room_name = models.CharField(
        max_length=150,
        blank=True,
        null=True
    )

    class Meta:
        ordering = ["floor", "room_number"]

    def __str__(self):
        building_name = self.building.name if self.building else "No building"
        return f"Room {self.room_number} - {self.room_name or 'Unnamed'} ({building_name})"


class Course(models.Model):
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name="courses"
    )

    code = models.CharField(max_length=50)
    name = models.CharField(max_length=200)

    class Meta:
        ordering = ["code"]

        constraints = [
            models.UniqueConstraint(
                fields=["department", "code"],
                name="unique_course_code_per_department"
            )
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"


class Medicine(models.Model):
    name = models.CharField(max_length=150)
    dosage_form = models.CharField(max_length=100, blank=True)
    stock_quantity = models.PositiveIntegerField(default=0)
    reorder_level = models.PositiveIntegerField(default=5)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name", "dosage_form"]

    def __str__(self):
        if self.dosage_form:
            return f"{self.name} ({self.dosage_form})"
        return self.name

    @property
    def is_available(self):
        return self.is_active and self.stock_quantity > 0

    @property
    def stock_status(self):
        if not self.is_active or self.stock_quantity <= 0:
            return "Out of Stock"
        if self.stock_quantity <= self.reorder_level:
            return "Low Stock"
        return "In Stock"


class ClinicAnnouncement(models.Model):
    AUDIENCE_CHOICES = (
        ('all', 'All Users'),
        ('student', 'Students'),
        ('teacher', 'Teachers'),
        ('department', 'Specific Department'),
    )

    title = models.CharField(max_length=160)
    message = models.TextField(default="")
    audience = models.CharField(
        max_length=20,
        choices=AUDIENCE_CHOICES,
        default='all'
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name='announcements',
        blank=True,
        null=True
    )
    event_date = models.DateField(blank=True, null=True)
    start_time = models.TimeField(blank=True, null=True)
    end_time = models.TimeField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name='clinic_announcements',
        blank=True,
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['event_date', '-created_at']

    def __str__(self):
        if self.event_date:
            return f"{self.title} ({self.event_date})"
        return self.title