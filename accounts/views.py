import mimetypes
import calendar
from functools import wraps
from io import BytesIO
from .models import Medicine
from django.db import transaction
from datetime import date, datetime

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordChangeView
from django.core.mail import EmailMessage
from django.db.models import Q
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST

from .models import ClinicAnnouncement

from .models import User

from pptx import Presentation
from pptx.util import Inches, Pt

from .forms import (
    SignUpForm,
    AuthorizedUserForm,
    UserUpdateForm,
    StudentUpdateForm,
    StudentProfileUpdateForm,
    StudentAppointmentForm,
    TeacherReferralForm,
    AppointmentRescheduleForm,
    HealthRecordForm,
    SickNoteForm,
    DepartmentForm,
    BuildingForm,
    RoomForm,
    CourseForm,
)

from .models import (
    User,
    TeacherStudent,
    Appointment,
    Referral,
    HealthRecord,
    SickNote,
    ClinicStatus,
    Department,
    Building,
    Room,
    Course,
)

from .forms import (
    SignUpForm,
    AuthorizedUserForm,
    UserUpdateForm,
    StudentUpdateForm,
    StudentProfileUpdateForm,
    StudentAppointmentForm,
    TeacherReferralForm,
    AppointmentRescheduleForm,
    HealthRecordForm,
    SickNoteForm,
    DepartmentForm,
    BuildingForm,
    RoomForm,
    CourseForm,
)


def get_role(user):
    return str(getattr(user, "role", "") or "").strip().lower()


def student_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("accounts:login")

        if get_role(request.user) != "student":
            messages.error(
                request,
                "You are not authorized to access this page."
            )
            return redirect("accounts:dashboard")

        if request.user.verification_status != "verified":
            messages.warning(
                request,
                "Your student verification has not been verified. Please contact Clinic Staff."
            )
            logout(request)
            return redirect("accounts:login")

        return view_func(request, *args, **kwargs)

    return wrapper


def staff_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("accounts:login")

        if get_role(request.user) != "staff":
            messages.error(
                request,
                "You are not authorized to access this page."
            )
            return redirect("accounts:dashboard")

        return view_func(request, *args, **kwargs)

    return wrapper


def staff_position_required(*allowed_positions):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect("accounts:login")

            if (
                get_role(request.user) != "staff"
                or request.user.staff_position not in allowed_positions
            ):
                messages.error(
                    request,
                    "You are not authorized to access this page."
                )
                return redirect("accounts:dashboard")

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("accounts:login")

        if (
            get_role(request.user) != "staff"
            or request.user.staff_position != "admin"
        ):
            messages.error(
                request,
                "Only the Clinic Administrator can access this page."
            )
            return redirect("accounts:dashboard")

        return view_func(request, *args, **kwargs)

    return wrapper


def get_clinic_status():
    status, _ = ClinicStatus.objects.get_or_create(
        id=1,
        defaults={"is_available": True},
    )
    return status


def get_status_counts(queryset):
    return {
        "total": queryset.count(),
        "pending": queryset.filter(status__iexact="Pending").count(),
        "approved": queryset.filter(status__iexact="Approved").count(),
        "received": queryset.filter(status__iexact="Received").count(),
        "rescheduled": queryset.filter(
            status__iexact="Rescheduled"
        ).count(),
        "rejected": queryset.filter(status__iexact="Rejected").count(),
        "completed": queryset.filter(status__iexact="Completed").count(),
    }


def send_appointment_notification(appointment):
    student = appointment.student

    if not student or not student.email:
        return False

    student_name = student.get_full_name() or student.username
    appointment_date = (
        appointment.scheduled_date or appointment.preferred_date
    )
    appointment_time = (
        appointment.scheduled_time or appointment.preferred_time
    )

    if not appointment_date or not appointment_time:
        return False

    email = EmailMessage(
        subject=f"Clinic Connect - Appointment {appointment.status}",
        body=f"""Hello {student_name},

Your Clinic Connect appointment has been updated.

Appointment Status:
{appointment.status}

Appointment Date:
{appointment_date.strftime("%B %d, %Y")}

Appointment Time:
{appointment_time.strftime("%I:%M %p")}

Health Concern:
{appointment.concern}

Please log in to Clinic Connect to view your appointment details.

Clinic Connect
""",
        from_email=None,
        to=[student.email],
    )

    try:
        return email.send(fail_silently=True) > 0
    except Exception:
        return False


def login_view(request):
    if request.user.is_authenticated:
        return redirect("accounts:dashboard")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        user = authenticate(
            request,
            username=username,
            password=password,
        )

        if user is not None and user.is_active:
            if (
                get_role(user) == "student"
                and user.verification_status != "verified"
            ):
                if user.verification_status == "rejected":
                    messages.error(
                        request,
                        "Your student verification was rejected. Please contact Clinic Staff for assistance."
                    )
                else:
                    messages.warning(
                        request,
                        "Your student enrollment is awaiting verification. Please contact Clinic Staff."
                    )

                return redirect("accounts:login")
            login(request, user)
            return redirect("accounts:dashboard")

        messages.error(request, "Invalid username or password.")

    return render(request, "accounts/login.html")


@admin_required
def create_authorized_account(request):
    if request.method == "POST":
        form = AuthorizedUserForm(request.POST)

        if form.is_valid():
            user = form.save()

            messages.success(
                request,
                f"{user.get_full_name() or user.username} account was created successfully."
            )

            return redirect("accounts:create_authorized_account")
    else:
        form = AuthorizedUserForm()

    return render(
        request,
        "accounts/create_authorized_account.html",
        {
            "form": form,
        },
    )


@staff_position_required("admin", "receptionist", "records")
def staff_student_verification(request):
    from collections import Counter, defaultdict

    department_aliases = {
        "DCS": "Department of Computer Studies",
        "DBM": "Department of Business Management",
        "CCJE": "College of Criminal Justice Education",
        "DGTT": "Department of General Teacher Training",
        "DIT": "Department of Industrial Technology",
    }

    department_courses = {
        "Department of Computer Studies": ["BSInfoTech", "BSCS"],
        "Department of Business Management": ["BSBA"],
        "College of Criminal Justice Education": ["BSCrim"],
        "Department of General Teacher Training": ["BEED"],
        "Department of Industrial Technology": ["BSIndTech"],
    }

    year_options = ["1st Year", "2nd Year", "3rd Year", "4th Year"]

    def normalize_department(value):
        value = (value or "").strip()
        return department_aliases.get(value.upper(), value)

    def get_year(value):
        value = (value or "").strip()
        for year in year_options:
            if year.lower() in value.lower():
                return year
        return "Other Year"

    all_students = User.objects.filter(
        role="student"
    ).order_by("-date_joined")

    search = request.GET.get("search", "").strip()
    selected_department = request.GET.get("department", "").strip()
    selected_course = request.GET.get("course", "").strip()
    selected_year = request.GET.get("year", "").strip()
    selected_status = request.GET.get("status", "pending").strip().lower()

    if selected_status not in {"pending", "verified"}:
        selected_status = "pending"

    if search:
        all_students = all_students.filter(
            Q(first_name__icontains=search)
            | Q(middle_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(username__icontains=search)
            | Q(id_number__icontains=search)
            | Q(email__icontains=search)
        )

    filtered_students = all_students.filter(
        verification_status=selected_status
    )

    if selected_department:
        department_filter = Q(department__iexact=selected_department)

        for code, name in department_aliases.items():
            if normalize_department(selected_department) == name:
                department_filter |= Q(department__iexact=code)

        filtered_students = filtered_students.filter(department_filter)

    if selected_course:
        filtered_students = filtered_students.filter(
            course__iexact=selected_course
        )

    if selected_year in year_options:
        filtered_students = filtered_students.filter(
            year_block__icontains=selected_year
        )

    registered_departments = list(
        User.objects.filter(role="student")
        .exclude(department__isnull=True)
        .exclude(department="")
        .values_list("department", flat=True)
        .distinct()
    )

    active_departments = list(
        Department.objects.filter(is_active=True)
        .order_by("name")
        .values_list("name", flat=True)
    )

    department_names = {
        normalize_department(name)
        for name in registered_departments + active_departments
        if name and name.strip()
    }

    department_names.update(department_courses.keys())
    department_names = sorted(department_names, key=str.lower)

    status_students = all_students.filter(
        verification_status=selected_status
    )

    department_counts = Counter(
        normalize_department(department)
        for department in status_students.values_list(
            "department", flat=True
        )
        if department and department.strip()
    )

    department_cards = [
        {
            "name": name,
            "count": department_counts.get(name, 0),
            "active": selected_department == name,
        }
        for name in department_names
    ]

    students_by_department = defaultdict(list)

    for student in filtered_students:
        department_name = normalize_department(student.department)
        students_by_department[department_name].append(student)

    department_sections = []

    for department_name in department_names:
        department_students = students_by_department.get(
            department_name, []
        )

        if not department_students:
            continue

        grouped_years = defaultdict(list)

        for student in department_students:
            grouped_years[get_year(student.year_block)].append(student)

        year_groups = []

        for year in year_options:
            year_students = grouped_years.get(year, [])

            if year_students:
                year_groups.append({
                    "name": year,
                    "students": year_students,
                    "count": len(year_students),
                })

        other_students = grouped_years.get("Other Year", [])

        if other_students:
            year_groups.append({
                "name": "Other Year",
                "students": other_students,
                "count": len(other_students),
            })

        courses = sorted({
            student.course
            for student in department_students
            if student.course
        })

        department_sections.append({
            "name": department_name,
            "courses": courses or department_courses.get(
                department_name, []
            ),
            "students": department_students,
            "year_groups": year_groups,
            "count": len(department_students),
            "pending_count": User.objects.filter(
                role="student",
                verification_status="pending",
            ).filter(
                Q(department__iexact=department_name)
                | Q(
                    department__iexact=next(
                        (
                            code for code, name in department_aliases.items()
                            if name == department_name
                        ),
                        "",
                    )
                )
            ).count(),
        })

    courses = list(
        User.objects.filter(role="student")
        .exclude(course__isnull=True)
        .exclude(course="")
        .values_list("course", flat=True)
        .distinct()
        .order_by("course")
    )

    context = {
        "department_cards": department_cards,
        "department_sections": department_sections,
        "departments": department_names,
        "courses": courses,
        "year_options": year_options,
        "search": search,
        "selected_department": normalize_department(selected_department),
        "selected_course": selected_course,
        "selected_year": selected_year,
        "selected_status": selected_status,
        "pending_count": User.objects.filter(
            role="student",
            verification_status="pending",
        ).count(),
        "verified_count": User.objects.filter(
            role="student",
            verification_status="verified",
        ).count(),
        "total_students": filtered_students.count(),
    }

    return render(
        request,
        "accounts/staff_student_verification.html",
        context,
    )


@staff_position_required("admin", "receptionist")
@require_POST
def staff_verify_student(request, student_id):
    student = get_object_or_404(
        User,
        pk=student_id,
        role="student"
    )

    if student.verification_status == "verified":
        messages.info(
            request,
            f"{student.get_full_name() or student.username} is already verified."
        )
    elif student.verification_status == "rejected":
        messages.error(
            request,
            "This enrollment was rejected and cannot be verified through this action."
        )
    else:
        student.verification_status = "verified"
        student.save(update_fields=["verification_status"])
        messages.success(
            request,
            f"{student.get_full_name() or student.username} has been verified."
        )

    return redirect("accounts:staff_student_verification")


@staff_position_required("admin", "receptionist", "records")
@require_GET
@xframe_options_sameorigin
def staff_verification_evidence(request, pk):
    student = get_object_or_404(
        User,
        pk=pk,
        role="student",
    )

    if not student.verification_evidence:
        raise Http404("No verification evidence was uploaded.")

    file_name = student.verification_evidence.name.split("/")[-1]
    extension = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""

    content_types = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
        "pdf": "application/pdf",
    }

    content_type = content_types.get(extension)

    if not content_type:
        raise Http404("Unsupported verification evidence format.")

    try:
        return FileResponse(
            student.verification_evidence.open("rb"),
            as_attachment=False,
            filename=file_name,
            content_type=content_type,
        )
    except (OSError, ValueError):
        raise Http404("The verification evidence file could not be opened.")


@login_required
@require_POST
def logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out successfully.")
    return redirect("accounts:login")


def signup_view(request):
    if request.user.is_authenticated:
        return redirect("accounts:dashboard")

    if request.method == "POST":
        form = SignUpForm(request.POST, request.FILES)

        if form.is_valid():
            user = form.save(commit=False)
            user.role = "student"
            user.verification_status = "pending"
            user.verification_evidence = form.cleaned_data["verification_evidence"]
            user.save()
            form.save_m2m()

            messages.success(
                request,
                "Your account has been created successfully. "
                "Your student verification is pending review by Clinic Staff."
            )

            return redirect("accounts:login")
    else:
        form = SignUpForm()

    return render(
        request,
        "accounts/signup.html",
        {
            "form": form,
        },
    )


def get_student_dashboard_context(user):
    appointments = Appointment.objects.filter(
        student=user
    ).order_by("-created_at")

    referrals = Referral.objects.filter(
        student_name=user.get_full_name()
    ).select_related(
        "teacher",
        "department",
        "building",
        "room",
    ).order_by("-created_at")

    sick_notes = SickNote.objects.filter(
        appointment__student=user
    ).select_related(
        "appointment",
        "issued_by",
    ).order_by("-issued_at")

    available_medicines = list(
        Medicine.objects.filter(
            is_active=True,
            stock_quantity__gt=0,
        ).order_by("name", "dosage_form")
    )

    appointment_counts = get_status_counts(appointments)
    referral_counts = get_status_counts(referrals)

    today = timezone.localdate()

    upcoming_appointments = appointments.filter(
        status__in=["Approved", "Rescheduled"],
        scheduled_date__gte=today,
    ).order_by("scheduled_date", "scheduled_time")

    clinic_announcements = list(
        get_announcements_for_user(user)[:6]
    )

    return {
        "appointments": appointments,
        "referrals": referrals,
        "sick_notes": sick_notes,
        "available_medicines": available_medicines,
        "recent_appointments": appointments[:5],
        "upcoming_appointments": upcoming_appointments,
        "total_appointments": appointment_counts["total"],
        "pending_appointments": appointment_counts["pending"],
        "total_referrals": referral_counts["total"],
        "pending_referrals": referral_counts["pending"],
        "total_sick_notes": sick_notes.count(),
        "appointment_count": appointment_counts["total"],
        "pending_appointment_count": appointment_counts["pending"],
        "referral_count": referral_counts["total"],
        "pending_referral_count": referral_counts["pending"],
        "sick_note_count": sick_notes.count(),
        "pending_referrals_count": referral_counts["pending"],
    }


@student_required
def student_home(request):
    context = get_student_dashboard_context(request.user)
    return render(request, "accounts/student_home.html", context)


@login_required
def dashboard_view(request):
    role = get_role(request.user)

    if role == "student" and request.user.verification_status != "verified":
        messages.warning(
            request,
            "Your student enrollment is pending verification. Please contact Clinic Staff."
        )
        logout(request)
        return redirect("accounts:login")

    if role == "student":
        context = get_student_dashboard_context(request.user)
        context["student_page"] = "home"
        context["clinic_status"] = get_clinic_status()
        context["clinic_announcements"] = list(
            get_announcements_for_user(request.user)[:6]
        )

        return render(
            request,
            "accounts/dashboard.html",
            context,
        )

    if role == "teacher":
        teacher_department = (request.user.department or "").strip()

        if teacher_department:
            students = User.objects.filter(
                role="student",
                verification_status="verified",
                department__iexact=teacher_department,
            ).order_by("last_name", "first_name")
        else:
            students = User.objects.none()

        referrals = Referral.objects.filter(
            teacher=request.user
        ).select_related(
            "teacher",
            "department",
            "building",
            "room",
        ).order_by("-created_at")

        student_count = students.count()
        referral_counts = get_status_counts(referrals)

        student_by_name = {}
        for student in students:
            full_name_key = (student.get_full_name() or "").strip().casefold()
            username_key = (student.username or "").strip().casefold()
            if full_name_key and full_name_key not in student_by_name:
                student_by_name[full_name_key] = student
            if username_key and username_key not in student_by_name:
                student_by_name[username_key] = student

        referred_student_names = {
            (referral.student_name or "").strip().casefold()
            for referral in referrals
            if (referral.student_name or "").strip()
        }

        students_with_referrals = len(
            set(student_by_name.keys()).intersection(referred_student_names)
        )

        referral_coverage = (
            round(
                students_with_referrals / student_count * 100,
                1,
            )
            if student_count > 0
            else 0
        )

        total_referrals = referral_counts["total"]

        pending_referrals = referral_counts["pending"]
        approved_referrals = referral_counts["approved"]
        received_referrals = referral_counts["received"]
        completed_referrals = referral_counts["completed"]
        rejected_referrals = referral_counts["rejected"]

        pending_percentage = (
            round(pending_referrals / total_referrals * 100, 1)
            if total_referrals > 0 else 0
        )

        approved_percentage = (
            round(approved_referrals / total_referrals * 100, 1)
            if total_referrals > 0 else 0
        )

        received_percentage = (
            round(received_referrals / total_referrals * 100, 1)
            if total_referrals > 0 else 0
        )

        completed_percentage = (
            round(completed_referrals / total_referrals * 100, 1)
            if total_referrals > 0 else 0
        )

        rejected_percentage = (
            round(rejected_referrals / total_referrals * 100, 1)
            if total_referrals > 0 else 0
        )

        recent_referrals = list(referrals[:5])
        for referral in recent_referrals:
            name_key = (referral.student_name or "").strip().casefold()
            referral.matched_student = student_by_name.get(name_key)

        clinic_announcements = list(
            get_announcements_for_user(request.user)[:6]
        )

        context = {
            "students": students,
            "referrals": referrals,
            "total_students": student_count,
            "total_referrals": total_referrals,
            "pending_referrals": pending_referrals,
            "approved_referrals": approved_referrals,
            "completed_referrals": completed_referrals,
            "rejected_referrals": rejected_referrals,
            "sent_referrals": approved_referrals,
            "received_referrals": received_referrals,
            "students_with_referrals": students_with_referrals,
            "referral_coverage": referral_coverage,
            "pending_percentage": pending_percentage,
            "approved_percentage": approved_percentage,
            "received_percentage": received_percentage,
            "completed_percentage": completed_percentage,
            "rejected_percentage": rejected_percentage,
            "recent_referrals": recent_referrals,
            "teacher_department": teacher_department,
            "clinic_status": get_clinic_status(),
            "clinic_announcements": clinic_announcements,
        }

        return render(
            request,
            "accounts/dashboard_teacher.html",
            context,
        )

    if role == "staff":
        today = timezone.localdate()
        month_value = request.GET.get("month", "").strip()

        try:
            selected_month = datetime.strptime(
                month_value,
                "%Y-%m",
            ).date().replace(day=1)
        except ValueError:
            selected_month = today.replace(day=1)

        year = selected_month.year
        month = selected_month.month

        month_start = date(year, month, 1)
        month_end = date(
            year,
            month,
            calendar.monthrange(year, month)[1],
        )

        selected_date_value = request.GET.get("date", "").strip()

        try:
            selected_date = datetime.strptime(
                selected_date_value,
                "%Y-%m-%d",
            ).date()
        except ValueError:
            selected_date = (
                today
                if today.year == year and today.month == month
                else month_start
            )

        if (
            selected_date.year != year
            or selected_date.month != month
        ):
            selected_date = month_start

        appointments = Appointment.objects.select_related(
            "student",
        ).order_by("-created_at")

        referrals = Referral.objects.select_related(
            "teacher",
            "department",
            "building",
            "room",
        ).order_by("-created_at")

        appointment_counts = get_status_counts(appointments)
        referral_counts = get_status_counts(referrals)

        calendar_appointments = appointments.filter(
            Q(
                scheduled_date__gte=month_start,
                scheduled_date__lte=month_end,
            )
            | Q(
                scheduled_date__isnull=True,
                preferred_date__gte=month_start,
                preferred_date__lte=month_end,
            )
        )

        appointments_by_date = {}

        for appointment in calendar_appointments:
            appointment.calendar_date = (
                appointment.scheduled_date
                or appointment.preferred_date
            )
            appointment.calendar_time = (
                appointment.scheduled_time
                or appointment.preferred_time
            )
            appointment.calendar_is_request = (
                appointment.scheduled_date is None
            )

            appointments_by_date.setdefault(
                appointment.calendar_date,
                [],
            ).append(appointment)

        for day_appointments in appointments_by_date.values():
            day_appointments.sort(
                key=lambda appointment: (
                    appointment.calendar_time is None,
                    appointment.calendar_time,
                    appointment.student.last_name or "",
                    appointment.student.first_name or "",
                )
            )

        month_calendar = calendar.Calendar(firstweekday=6)
        calendar_weeks = []

        for week in month_calendar.monthdatescalendar(year, month):
            week_days = []

            for calendar_day in week:
                day_appointments = appointments_by_date.get(
                    calendar_day,
                    [],
                )

                week_days.append({
                    "date": calendar_day,
                    "day_number": calendar_day.day,
                    "in_month": calendar_day.month == month,
                    "is_today": calendar_day == today,
                    "is_selected": calendar_day == selected_date,
                    "appointment_count": len(day_appointments),
                    "has_appointments": bool(day_appointments),
                    "date_value": calendar_day.isoformat(),
                })

            calendar_weeks.append(week_days)

        previous_month = (
            date(year - 1, 12, 1)
            if month == 1
            else date(year, month - 1, 1)
        )

        next_month = (
            date(year + 1, 1, 1)
            if month == 12
            else date(year, month + 1, 1)
        )

        clinic_announcements = list(
            get_announcements_for_user(request.user)[:6]
        )

        active_departments = Department.objects.filter(is_active=True).order_by("name")
        all_announcements = ClinicAnnouncement.objects.select_related("department", "created_by")[:10]

        context = {
            "appointments": appointments,
            "referrals": referrals,
            "recent_appointments": appointments[:5],
            "recent_referrals": referrals[:5],
            "total_appointments": appointment_counts["total"],
            "total_referrals": referral_counts["total"],
            "pending_appointments": appointment_counts["pending"],
            "approved_appointments": appointment_counts["approved"],
            "rescheduled_appointments": appointment_counts["rescheduled"],
            "rejected_appointments": appointment_counts["rejected"],
            "completed_appointments": appointment_counts["completed"],
            "sent_referrals": referral_counts["approved"],
            "received_referrals": referral_counts["received"],
            "completed_referrals": referral_counts["completed"],
            "clinic_status": get_clinic_status(),
            "clinic_announcements": clinic_announcements,
            "calendar_weeks": calendar_weeks,
            "calendar_month": selected_month,
            "calendar_month_label": selected_month.strftime("%B %Y"),
            "calendar_previous_month": previous_month.strftime("%Y-%m"),
            "calendar_next_month": next_month.strftime("%Y-%m"),
            "calendar_selected_date": selected_date,
            "calendar_selected_date_value": selected_date.isoformat(),
            "calendar_selected_appointments": appointments_by_date.get(
                selected_date,
                [],
            ),
        }

        return render(
            request,
            "accounts/dashboard_clinic_staff.html",
            context,
        )

    logout(request)
    messages.error(
        request,
        "Your account has an invalid role. Please contact the clinic administrator.",
    )
    return redirect("accounts:login")


@login_required
def edit_profile(request):
    form_class = (
        StudentProfileUpdateForm
        if get_role(request.user) == "student"
        else UserUpdateForm
    )

    if request.method == "POST":
        form = form_class(
            request.POST,
            request.FILES,
            instance=request.user,
        )

        if form.is_valid():
            form.save()
            messages.success(
                request,
                "Your profile has been updated successfully.",
            )
            return redirect("accounts:profile")
    else:
        form = form_class(instance=request.user)

    return render(
        request,
        "accounts/edit_profile.html",
        {
            "form": form,
            "user": request.user,
        },
    )


@student_required
def request_checkup(request):
    clinic_status = get_clinic_status()

    if request.method == "POST":
        if not clinic_status.is_available:
            messages.error(
                request,
                "The clinic is currently unavailable. Please try again later.",
            )
            return redirect("accounts:request_checkup")

        form = StudentAppointmentForm(request.POST)

        if form.is_valid():
            appointment = form.save(commit=False)
            appointment.student = request.user
            appointment.status = "Pending"
            appointment.save()

            messages.success(
                request,
                "Your checkup request has been submitted successfully.",
            )
            return redirect("accounts:student_appointments")
    else:
        form = StudentAppointmentForm()

    return render(
        request,
        "accounts/request_checkup.html",
        {
            "form": form,
            "clinic_status": clinic_status,
        },
    )


def edit_student(request, student_id):
    student = get_object_or_404(
        User,
        pk=student_id,
        role="student",
        assigned_teachers__teacher=request.user,
    )

    if request.method == "POST":
        form = StudentUpdateForm(request.POST, instance=student)

        if form.is_valid():
            form.save()
            messages.success(
                request,
                "Student information updated successfully.",
            )
            return redirect("accounts:teacher_department")
    else:
        form = StudentUpdateForm(instance=student)

    return render(
        request,
        "accounts/edit_student.html",
        {
            "form": form,
            "student": student,
        },
    )


@require_POST
def remove_student(request, student_id):
    student = get_object_or_404(
        User,
        pk=student_id,
        role="student",
        assigned_teachers__teacher=request.user,
    )

    student_name = student.get_full_name() or student.username

    TeacherStudent.objects.filter(
        teacher=request.user,
        student=student,
    ).delete()

    messages.success(
        request,
        f"{student_name} has been removed from your assigned students.",
    )

    return redirect("accounts:teacher_department")


def teacher_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("accounts:login")

        if get_role(request.user) != "teacher":
            messages.error(
                request,
                "You are not authorized to access this page."
            )
            return redirect("accounts:dashboard")

        return view_func(request, *args, **kwargs)

    return wrapper


def teacher_department(request):
    dept_id = request.GET.get("department")

    preferred = ["DCS", "DIT", "DBM", "DGTT", "CCJE"]
    rank = {code: index for index, code in enumerate(preferred)}

    departments = list(
        Department.objects.filter(is_active=True)
        .prefetch_related("buildings__rooms", "courses")
    )

    departments.sort(
        key=lambda department: (
            rank.get(
                (department.code or "").strip().upper(),
                len(preferred),
            ),
            department.pk,
        )
    )

    for department_item in departments:
        department_buildings = list(department_item.buildings.all())
        department_item.building_total = len(department_buildings)
        department_item.room_total = sum(
            len(list(building.rooms.all()))
            for building in department_buildings
        )

        if department_item.room_total == 0:
            department_item.room_total = sum(
                building.total_rooms or 0
                for building in department_buildings
            )

    if dept_id:
        department = get_object_or_404(
            Department.objects.prefetch_related(
                "buildings__rooms",
                "courses",
            ),
            pk=dept_id,
            is_active=True,
        )

        dept_code = (department.code or "").strip()
        dept_name = department.name.strip()

        department_students = User.objects.filter(
            role="student",
            verification_status="verified",
        ).filter(
            Q(department__iexact=dept_code)
            | Q(department__iexact=dept_name)
            | Q(department__icontains=dept_name)
        ).distinct().order_by("last_name", "first_name")

        search = request.GET.get("search", "").strip()
        selected_course = request.GET.get("course", "").strip()
        selected_year = request.GET.get("year", "").strip()

        total_students = department_students.count()

        if search:
            department_students = department_students.filter(
                Q(first_name__icontains=search)
                | Q(middle_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(username__icontains=search)
                | Q(id_number__icontains=search)
                | Q(email__icontains=search)
            )

        if selected_course:
            department_students = department_students.filter(
                course__iexact=selected_course
            )

        if selected_year:
            department_students = department_students.filter(
                year_block__icontains=selected_year
            )

        courses = (
            User.objects.filter(
                role="student",
                course__isnull=False,
            )
            .exclude(course="")
            .values_list("course", flat=True)
            .distinct()
            .order_by("course")
        )

        year_options = (
            User.objects.filter(
                role="student",
                year_block__isnull=False,
            )
            .exclude(year_block="")
            .values_list("year_block", flat=True)
            .distinct()
            .order_by("year_block")
        )

        buildings = list(
            department.buildings.prefetch_related("rooms").all()
        )

        building_count = len(buildings)

        room_count = sum(
            len(list(building.rooms.all()))
            for building in buildings
        )

        if room_count == 0:
            room_count = sum(
                building.total_rooms or 0
                for building in buildings
            )

        faculty_count = User.objects.filter(
            role="teacher",
        ).filter(
            Q(department__iexact=dept_code)
            | Q(department__iexact=dept_name)
            | Q(department__icontains=dept_name)
        ).count()

        active_referral_count = Referral.objects.filter(
            department=department,
            status__iexact="Approved",
        ).count()

        return render(
            request,
            "accounts/teacher_department_detail.html",
            {
                "current": "teacher_department",
                "department": department,
                "students": department_students,
                "total_students": total_students,
                "courses": courses,
                "year_options": year_options,
                "search": search,
                "selected_course": selected_course,
                "selected_year": selected_year,
                "buildings": buildings,
                "building_count": building_count,
                "room_count": room_count,
                "faculty_count": faculty_count,
                "active_referral_count": active_referral_count,
            },
        )

    students = (
        User.objects.filter(
            assigned_teachers__teacher=request.user,
            role="student",
        )
        .distinct()
        .order_by("last_name", "first_name")
    )

    search = (
        request.GET.get("search")
        or request.GET.get("q")
        or request.GET.get("query")
        or ""
    ).strip()

    if search:
        students = students.filter(
            Q(first_name__icontains=search)
            | Q(middle_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(username__icontains=search)
            | Q(id_number__icontains=search)
            | Q(email__icontains=search)
            | Q(course__icontains=search)
            | Q(department__icontains=search)
            | Q(year_block__icontains=search)
        )

    return render(
        request,
        "accounts/teacher_department.html",
        {
            "students": students,
            "total_students": students.count(),
            "departments": departments,
            "unassigned": [],
            "search": search,
            "search_query": search,
            "courses": (
                User.objects.filter(role="student")
                .exclude(course="")
                .values_list("course", flat=True)
                .distinct()
                .order_by("course")
            ),
            "year_options": (
                User.objects.filter(role="student")
                .exclude(year_block="")
                .values_list("year_block", flat=True)
                .distinct()
                .order_by("year_block")
            ),
            "current": "teacher_department",
        },
    )


@teacher_required
def teacher_department_detail(request, pk):
    department = get_object_or_404(
        Department,
        pk=pk,
        is_active=True
    )

    department_filter = (
        Q(department__iexact=department.name)
        | Q(department__icontains=department.name)
    )

    if department.code and department.code.strip():
        department_filter |= Q(
            department__iexact=department.code.strip()
        )

    all_students = User.objects.filter(
        role="student",
        verification_status="verified",
    ).filter(
        department_filter
    ).order_by(
        "last_name",
        "first_name",
        "username"
    )

    total_students = all_students.count()

    year_options = [
        "1st Year",
        "2nd Year",
        "3rd Year",
        "4th Year",
    ]

    selected_year = request.GET.get("year", "").strip()
    search = request.GET.get("search", "").strip()

    students = all_students

    if selected_year:
        students = students.filter(
            year_block__icontains=selected_year
        )

    if search:
        students = students.filter(
            Q(first_name__icontains=search)
            | Q(middle_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(username__icontains=search)
            | Q(id_number__icontains=search)
        )

    buildings = list(
        department.buildings.prefetch_related("rooms").all()
    )

    building_count = len(buildings)
    room_count = 0

    for building in buildings:
        actual_rooms = list(building.rooms.all())

        if actual_rooms:
            room_count += len(actual_rooms)
        else:
            room_count += building.total_rooms or 0

    faculty_filter = (
        Q(department__iexact=department.name)
        | Q(department__icontains=department.name)
    )

    if department.code and department.code.strip():
        faculty_filter |= Q(
            department__iexact=department.code.strip()
        )

    faculty_list = User.objects.filter(
        role="teacher"
    ).filter(
        faculty_filter
    ).order_by(
        "last_name",
        "first_name"
    )

    recent_incidents = Referral.objects.filter(
        department=department
    ).select_related(
        "teacher"
    ).order_by(
        "-created_at"
    )[:5]

    active_referral_count = Referral.objects.filter(
        department=department,
        status__in=["Approved", "Received"]
    ).count()

    today = date.today()

    try:
        calendar_year = int(
            request.GET.get("calendar_year", today.year)
        )
        calendar_month = int(
            request.GET.get("calendar_month", today.month)
        )

        if calendar_month < 1 or calendar_month > 12:
            raise ValueError

        if calendar_year < 1900 or calendar_year > 9999:
            raise ValueError

    except (TypeError, ValueError):
        calendar_year = today.year
        calendar_month = today.month

    calendar_obj = calendar.Calendar(firstweekday=6)

    calendar_weeks = calendar_obj.monthdatescalendar(
        calendar_year,
        calendar_month
    )

    clinic_announcements = list(
        get_announcements_for_user(request.user, department=department)
    )

    previous_month = (
        calendar_year - 1 if calendar_month == 1 else calendar_year,
        12 if calendar_month == 1 else calendar_month - 1
    )

    next_month = (
        calendar_year + 1 if calendar_month == 12 else calendar_year,
        1 if calendar_month == 12 else calendar_month + 1
    )

    return render(
        request,
        "accounts/teacher_department_detail.html",
        {
            "current": "teacher_department",
            "department": department,

            "students": students,
            "total_students": total_students,
            "filtered_student_count": students.count(),
            "year_options": year_options,
            "selected_year": selected_year,
            "search": search,

            "buildings": buildings,
            "building_count": building_count,
            "room_count": room_count,

            "faculty_count": faculty_list.count(),
            "faculty_list": faculty_list,

            "active_referral_count": active_referral_count,
            "recent_incidents": recent_incidents,

            "today": today,
            "calendar_year": calendar_year,
            "calendar_month": calendar_month,
            "calendar_month_name": calendar.month_name[calendar_month],
            "calendar_weeks": calendar_weeks,
            "previous_month": previous_month,
            "next_month": next_month,
        },
    )


@admin_required
def staff_departments(request):
    if request.method == "POST":
        form = DepartmentForm(request.POST)

        if form.is_valid():
            department = form.save()

            messages.success(
                request,
                f"{department.name} was added successfully."
            )

            return redirect("accounts:staff_departments")
        else:
            messages.error(
                request,
                "Please correct the errors in the department form."
            )
    else:
        form = DepartmentForm()

    departments = (
        Department.objects
        .prefetch_related(
            "buildings__rooms",
            "courses",
        )
        .order_by("name")
    )

    buildings = (
        Building.objects
        .select_related("department")
        .prefetch_related("rooms")
        .order_by("department__name", "name")
    )

    rooms = (
        Room.objects
        .select_related(
            "building",
            "building__department",
        )
        .order_by(
            "building__department__name",
            "building__name",
            "floor",
            "room_number",
        )
    )

    courses = (
        Course.objects
        .select_related("department")
        .order_by("department__name", "code")
    )

    context = {
        "form": form,
        "departments": departments,
        "buildings": buildings,
        "rooms": rooms,
        "courses": courses,
    }

    return render(
        request,
        "accounts/staff_departments.html",
        context,
    )


@admin_required
def staff_department_detail(request, department_id):
    department = get_object_or_404(
        Department.objects.prefetch_related(
            "buildings__rooms",
            "courses",
        ),
        pk=department_id,
    )

    buildings = (
        department.buildings
        .prefetch_related("rooms")
        .order_by("name")
    )

    return render(
        request,
        "accounts/staff_department_detail.html",
        {
            "department": department,
            "buildings": buildings,
        },
    )


@admin_required
def staff_room_detail(request, room_id):
    room = get_object_or_404(
        Room.objects.select_related(
            "building",
            "building__department",
        ),
        pk=room_id,
    )

    return render(
        request,
        "accounts/staff_room_detail.html",
        {
            "room": room,
        },
    )


@admin_required
def staff_department_edit(request, department_id):
    department = get_object_or_404(
        Department,
        pk=department_id
    )

    if request.method == "POST":
        form = DepartmentForm(
            request.POST,
            instance=department
        )

        if form.is_valid():
            updated_department = form.save()

            messages.success(
                request,
                f"{updated_department.name} was updated successfully."
            )

            return redirect("accounts:staff_departments")
    else:
        form = DepartmentForm(instance=department)

    departments = Department.objects.prefetch_related(
        "buildings__rooms",
        "courses",
    ).order_by("name")

    buildings = Building.objects.select_related(
        "department",
    ).prefetch_related(
        "rooms",
    ).order_by("department__name", "name")

    rooms = Room.objects.select_related(
        "building",
        "building__department",
    ).order_by("floor", "room_number")

    courses = Course.objects.select_related(
        "department",
    ).order_by("department__name", "code")

    return render(
        request,
        "accounts/staff_departments.html",
        {
            "form": form,
            "departments": departments,
            "buildings": buildings,
            "rooms": rooms,
            "courses": courses,
            "editing_department": department,
        },
    )


@admin_required
@require_POST
def staff_department_toggle_status(request, department_id):
    department = get_object_or_404(
        Department,
        pk=department_id
    )

    department.is_active = not department.is_active
    department.save(update_fields=["is_active"])

    if department.is_active:
        messages.success(
            request,
            f"{department.name} has been activated."
        )
    else:
        messages.success(
            request,
            f"{department.name} has been deactivated."
        )

    return redirect("accounts:staff_departments")


@admin_required
def manage_department_object(request, kind, pk=None):
    configurations = {
        "department": (Department, DepartmentForm, "Department"),
        "building": (Building, BuildingForm, "Building"),
        "room": (Room, RoomForm, "Room"),
        "course": (Course, CourseForm, "Course"),
    }

    configuration = configurations.get(kind)

    if configuration is None:
        messages.error(
            request,
            "Invalid department management category.",
        )
        return redirect("accounts:staff_departments")

    model, form_class, label = configuration
    instance = None

    if pk is not None:
        instance = get_object_or_404(model, pk=pk)

    next_url = request.POST.get("next") or request.GET.get("next")

    if next_url and not url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        next_url = None

    if not next_url and instance:
        department_id = None

        if kind == "building":
            department_id = instance.department_id

        elif kind == "room":
            department_id = instance.building.department_id

        if department_id:
            next_url = reverse(
                "accounts:staff_department_detail",
                kwargs={"department_id": department_id},
            )

    if not next_url:
        next_url = reverse("accounts:staff_departments")

    if request.method == "POST":
        form = form_class(request.POST, instance=instance)

        if form.is_valid():
            form.save()
            action = "updated" if instance else "created"

            messages.success(
                request,
                f"{label} {action} successfully.",
            )

            return redirect(next_url)
    else:
        form = form_class(instance=instance)

    return render(
        request,
        "accounts/manage_department_object.html",
        {
            "form": form,
            "kind": kind,
            "label": label,
            "object": instance,
            "is_edit": instance is not None,
            "return_url": next_url,
        },
    )


@admin_required
@require_POST
def delete_department_object(request, kind, pk):
    configurations = {
        "department": (Department, "Department"),
        "building": (Building, "Building"),
        "room": (Room, "Room"),
        "course": (Course, "Course"),
    }

    configuration = configurations.get(kind)

    if configuration is None:
        messages.error(
            request,
            "Invalid department management category.",
        )
        return redirect("accounts:staff_departments")

    model, label = configuration
    instance = get_object_or_404(model, pk=pk)
    instance.delete()

    messages.success(
        request,
        f"{label} deleted successfully.",
    )
    return redirect("accounts:staff_departments")


@teacher_required
def teacher_referrals(request):
    search_query = (
        request.GET.get("q")
        or request.GET.get("search")
        or request.GET.get("query")
        or ""
    ).strip()

    status_filter = request.GET.get("status", "").strip().lower()

    all_referrals = Referral.objects.filter(
        teacher=request.user,
    ).select_related(
        "teacher",
        "department",
        "building",
        "room",
    )

    referrals = all_referrals

    if search_query:
        referrals = referrals.filter(
            Q(student_name__icontains=search_query)
            | Q(symptoms__icontains=search_query)
            | Q(concern__icontains=search_query)
        )

    if status_filter == "sent":
        referrals = referrals.filter(status__iexact="Approved")
    elif status_filter == "received":
        referrals = referrals.filter(status__iexact="Received")
    elif status_filter == "completed":
        referrals = referrals.filter(status__iexact="Completed")

    referrals_list = list(referrals.order_by("-created_at"))

    student_users = User.objects.filter(
        role="student",
    ).exclude(
        profile_picture="",
    ).exclude(
        profile_picture__isnull=True,
    ).order_by("-verification_status", "last_name", "first_name")

    student_by_name = {}
    for student in student_users:
        full_name_key = " ".join((student.get_full_name() or "").split()).casefold()
        username_key = " ".join((student.username or "").split()).casefold()
        if full_name_key and full_name_key not in student_by_name:
            student_by_name[full_name_key] = student
        if username_key and username_key not in student_by_name:
            student_by_name[username_key] = student

    for referral in referrals_list:
        name_key = " ".join((referral.student_name or "").split()).casefold()
        referral.matched_student = student_by_name.get(name_key)

    sent_count = all_referrals.filter(status__iexact="Approved").count()
    received_count = all_referrals.filter(status__iexact="Received").count()
    completed_count = all_referrals.filter(status__iexact="Completed").count()

    return render(
        request,
        "accounts/teacher_referrals.html",
        {
            "referrals": referrals_list,
            "query_str": search_query,
            "current_status": status_filter,
            "sent_count": sent_count,
            "received_count": received_count,
            "completed_count": completed_count,
        },
    )


@staff_position_required("admin", "nurse", "receptionist", "records")
def staff_referrals(request):
    all_referrals = Referral.objects.select_related(
        "teacher",
        "department",
        "building",
        "room",
    ).order_by("-created_at")

    search_query = (
        request.GET.get("q")
        or request.GET.get("search")
        or ""
    ).strip()

    status_filter = request.GET.get("status", "").strip().lower()
    department_filter = request.GET.get("department", "").strip()

    referrals = all_referrals

    if search_query:
        referrals = referrals.filter(
            Q(student_name__icontains=search_query)
            | Q(teacher__username__icontains=search_query)
            | Q(teacher__first_name__icontains=search_query)
            | Q(teacher__last_name__icontains=search_query)
            | Q(symptoms__icontains=search_query)
            | Q(concern__icontains=search_query)
            | Q(department__name__icontains=search_query)
            | Q(building__name__icontains=search_query)
            | Q(room__room_number__icontains=search_query)
        )

    if status_filter == "sent":
        referrals = referrals.filter(status__iexact="Approved")
    elif status_filter == "received":
        referrals = referrals.filter(status__iexact="Received")
    elif status_filter == "completed":
        referrals = referrals.filter(status__iexact="Completed")
    else:
        status_filter = ""

    departments = Department.objects.all().order_by("name")

    if department_filter:
        if department_filter.isdigit() and departments.filter(
            pk=department_filter
        ).exists():
            referrals = referrals.filter(
                department_id=department_filter
            )
        else:
            department_filter = ""

    sent_count = all_referrals.filter(
        status__iexact="Approved"
    ).count()

    received_count = all_referrals.filter(
        status__iexact="Received"
    ).count()

    completed_count = all_referrals.filter(
        status__iexact="Completed"
    ).count()

    context = {
        "referrals": referrals,
        "departments": departments,
        "query_str": search_query,
        "current_status": status_filter,
        "current_department": department_filter,
        "sent_count": sent_count,
        "received_count": received_count,
        "completed_count": completed_count,
    }

    return render(
        request,
        "accounts/staff_referrals.html",
        context,
    )


@teacher_required
def refer_student(request):
    if request.method == "POST":
        form = TeacherReferralForm(request.POST)

        if form.is_valid():
            referral = form.save(commit=False)
            referral.teacher = request.user
            referral.status = "Approved"
            referral.save()

            messages.success(
                request,
                "Emergency referral submitted successfully. Clinic staff has been notified instantly.",
            )
            return redirect("accounts:teacher_referrals")
    else:
        form = TeacherReferralForm()

    return render(
        request,
        "accounts/refer_student.html",
        {"form": form},
    )


@staff_position_required("admin", "nurse", "receptionist", "records")
def staff_emergency_alerts(request):
    alerts = Referral.objects.filter(
        status__iexact="Approved"
    ).select_related(
        "teacher",
        "department",
        "building",
        "room",
    ).order_by("-created_at")

    data = []

    for r in alerts:
        department = str(r.department) if r.department else ""
        building = str(r.building) if r.building else ""
        room = str(r.room) if r.room else ""
        campus_area = r.location or ""

        floor_label = ""

        if r.room and r.room.floor:
            floor_number = int(r.room.floor)

            suffix = (
                "st" if floor_number == 1 else
                "nd" if floor_number == 2 else
                "rd" if floor_number == 3 else
                "th"
            )

            floor_label = f"{floor_number}{suffix} Floor"

        location_parts = [
            part for part in [
                department,
                building,
                floor_label,
                room,
                campus_area,
            ]
            if part
        ]

        data.append({
            "id": r.id,
            "student_name": r.student_name or "Unidentified Student",
            "where": " · ".join(location_parts) or "Campus Main",
            "department": department,
            "building": building,
            "floor": floor_label,
            "room": room,
            "location": campus_area,
            "concern": r.symptoms or r.concern or "Immediate Medical Attention",
            "teacher": r.teacher.get_full_name() or r.teacher.username,
            "sent_at": r.created_at.strftime("%I:%M %p"),
        })

    return JsonResponse({"alerts": data})


@staff_position_required("admin", "nurse", "receptionist")
@require_POST
def staff_emergency_receive(request, pk):
    referral = get_object_or_404(Referral, pk=pk)
    referral.status = "Received"
    referral.received_by = request.user
    referral.received_at = timezone.now()
    referral.save()

    return JsonResponse({"status": "success", "message": "Referral acknowledged."})


@staff_position_required("admin", "nurse", "receptionist")
@require_POST
def update_appointment_status(request, pk, status):
    appointment = get_object_or_404(
        Appointment.objects.select_related("student"),
        pk=pk,
    )

    allowed_statuses = {"Approved", "Rejected", "Completed"}
    status = status.strip().title()

    if status not in allowed_statuses:
        messages.error(request, "Invalid appointment status.")
        return redirect("accounts:staff_appointments")

    if (
        status == "Completed"
        and request.user.staff_position not in {"admin", "nurse"}
    ):
        messages.error(
            request,
            "Only the Clinic Administrator and Nurse / Medical Staff can complete appointments.",
        )
        return redirect("accounts:staff_appointments")

    current_status = (appointment.status or "").strip().lower()

    if status in {"Approved", "Rejected"} and current_status != "pending":
        messages.error(
            request,
            f"This appointment cannot be {status.lower()} because its current status is "
            f"{appointment.get_status_display()}. Only pending appointments can be approved or rejected.",
        )
        return redirect("accounts:staff_appointments")

    if status == "Completed" and current_status not in {
        "approved",
        "rescheduled",
    }:
        messages.error(
            request,
            "Only approved or rescheduled appointments can be completed.",
        )
        return redirect("accounts:staff_appointments")

    appointment.status = status

    if status != "Rejected":
        appointment.rejection_reason = ""

    appointment.save()

    email_sent = send_appointment_notification(appointment)

    if appointment.student.email and not email_sent:
        messages.warning(
            request,
            "Appointment status was updated, but the notification email could not be sent.",
        )

    messages.success(
        request,
        f"Appointment status updated to {status}.",
    )

    return redirect("accounts:staff_appointments")


@staff_position_required("admin", "nurse", "receptionist")
@require_POST
def update_referral_status(request, pk, status):
    referral = get_object_or_404(
        Referral.objects.select_related(
            "teacher",
            "department",
            "building",
            "room",
        ),
        pk=pk,
    )

    allowed_statuses = {"Received", "Completed"}
    status = status.strip().title()

    if status not in allowed_statuses:
        messages.error(request, "Invalid referral status.")
        return redirect("accounts:staff_referrals")

    current_status = (referral.status or "").strip().lower()

    if status == "Received" and current_status != "approved":
        messages.error(
            request,
            "Only sent referrals can be marked as received.",
        )
        return redirect("accounts:staff_referrals")

    if status == "Completed" and current_status != "received":
        messages.error(
            request,
            "Only received referrals can be marked as completed.",
        )
        return redirect("accounts:staff_referrals")

    referral.status = status

    if status == "Received":
        referral.received_by = request.user
        referral.received_at = timezone.now()

    referral.save()

    messages.success(
        request,
        f"Referral status updated to {status}.",
    )

    return redirect("accounts:staff_referrals")


@staff_position_required("admin", "nurse", "receptionist", "records")
def staff_appointments(request):
    all_appointments = Appointment.objects.select_related(
        "student",
    ).order_by("-created_at")

    status_filter = request.GET.get("status", "").strip()
    search_query = (
        request.GET.get("q")
        or request.GET.get("search")
        or ""
    ).strip()

    appointments = all_appointments

    if status_filter:
        appointments = appointments.filter(
            status__iexact=status_filter
        )

    if search_query:
        search_terms = search_query.split()

        name_query = Q()
        for term in search_terms:
            name_query &= (
                Q(student__first_name__icontains=term)
                | Q(student__middle_name__icontains=term)
                | Q(student__last_name__icontains=term)
                | Q(student__username__icontains=term)
                | Q(student__id_number__icontains=term)
                | Q(concern__icontains=term)
            )

        appointments = appointments.filter(name_query).distinct()

    available_medicines = list(
        Medicine.objects.filter(
            is_active=True,
            stock_quantity__gt=0,
        ).order_by("name")
    )

    counts = get_status_counts(all_appointments)

    context = {
        "appointments": appointments,
        "status_filter": status_filter,
        "search_query": search_query,
        "total_appointments": counts["total"],
        "pending_appointments": counts["pending"],
        "approved_appointments": counts["approved"],
        "rescheduled_appointments": counts["rescheduled"],
        "rejected_appointments": counts["rejected"],
        "completed_appointments": counts["completed"],
        "available_medicines": available_medicines,
    }

    return render(
        request,
        "accounts/staff_appointments.html",
        context,
    )


@staff_position_required("admin", "nurse", "receptionist", "records")
def staff_appointment_alerts(request):
    pending_appointments = Appointment.objects.filter(
        status__iexact="Pending"
    ).select_related("student")

    latest_appointment_id = (
        Appointment.objects.order_by("-id")
        .values_list("id", flat=True)
        .first()
    ) or 0

    latest_pending = pending_appointments.order_by(
        "-created_at",
        "-id"
    ).first()

    notification = None

    if latest_pending:
        student = latest_pending.student

        notification = {
            "id": latest_pending.id,
            "student": (
                student.get_full_name().strip()
                or student.username
            ),
            "concern": latest_pending.concern,
            "created_at": latest_pending.created_at.isoformat(),
        }

    return JsonResponse({
        "pending_count": pending_appointments.count(),
        "latest_appointment_id": latest_appointment_id,
        "latest_pending": notification,
    })


@staff_position_required("admin", "nurse", "receptionist")
def reschedule_appointment(request, appointment_id):
    appointment = get_object_or_404(
        Appointment.objects.select_related("student"),
        pk=appointment_id,
    )

    if request.method == "POST":
        form = AppointmentRescheduleForm(
            request.POST,
            instance=appointment,
        )

        if form.is_valid():
            appointment = form.save(commit=False)
            appointment.status = "Rescheduled"
            appointment.staff_notes = form.cleaned_data["reason"]
            appointment.save()

            email_sent = send_appointment_notification(appointment)

            if appointment.student.email and not email_sent:
                messages.warning(
                    request,
                    "Appointment was rescheduled, but the notification email could not be sent.",
                )

            messages.success(
                request,
                "Appointment has been rescheduled successfully.",
            )
            return redirect("accounts:staff_appointments")
    else:
        form = AppointmentRescheduleForm(
            instance=appointment,
            initial={"reason": appointment.staff_notes or ""},
        )

    return render(
        request,
        "accounts/reschedule_appointment.html",
        {
            "appointment": appointment,
            "form": form,
        },
    )


class ClinicPasswordChangeView(PasswordChangeView):
    template_name = "accounts/password_change.html"
    success_url = reverse_lazy("accounts:profile")

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            "Your password has been changed successfully.",
        )
        return response


@staff_position_required("admin", "nurse")
def create_health_record(request, appointment_id):
    appointment = get_object_or_404(
        Appointment.objects.select_related("student"),
        pk=appointment_id,
    )

    destination = "accounts:staff_appointments"
    next_page = (request.POST.get("next_page") or request.GET.get("next_page") or "").strip()
    redirect_target = destination if next_page == "appointments" else "accounts:staff_health_records"

    if appointment.status != "Completed":
        messages.error(
            request,
            "A health record can only be created after the student has completed the checkup.",
        )
        return redirect(destination)

    existing_record = HealthRecord.objects.filter(
        appointment=appointment,
    ).first()

    if existing_record:
        return redirect(
            "accounts:edit_health_record",
            record_id=existing_record.id,
        )

    available_medicines = list(
        Medicine.objects.filter(
            is_active=True,
            stock_quantity__gt=0,
        ).order_by("name", "dosage_form")
    )

    selected_medicine_id = ""
    dispense_quantity = 1

    if request.method == "POST":
        form = HealthRecordForm(request.POST)
        selected_medicine_id = (request.POST.get("dispense_medicine") or "").strip()

        try:
            dispense_quantity = max(1, int(request.POST.get("dispense_quantity") or 1))
        except (TypeError, ValueError):
            dispense_quantity = 1

        if form.is_valid():
            with transaction.atomic():
                medicine_to_dispense = None

                if selected_medicine_id:
                    medicine_to_dispense = (
                        Medicine.objects.select_for_update()
                        .filter(pk=selected_medicine_id, is_active=True)
                        .first()
                    )

                    if not medicine_to_dispense:
                        messages.error(
                            request,
                            "The selected medicine is no longer available.",
                        )
                        if next_page == "appointments":
                            return redirect(destination)
                        return render(
                            request,
                            "accounts/create_health_record.html",
                            {
                                "form": form,
                                "appointment": appointment,
                                "available_medicines": available_medicines,
                                "selected_medicine_id": selected_medicine_id,
                                "dispense_quantity": dispense_quantity,
                            },
                        )

                    if medicine_to_dispense.stock_quantity < dispense_quantity:
                        messages.error(
                            request,
                            f"Insufficient stock for {medicine_to_dispense.name}. Only {medicine_to_dispense.stock_quantity} remaining.",
                        )
                        if next_page == "appointments":
                            return redirect(destination)
                        return render(
                            request,
                            "accounts/create_health_record.html",
                            {
                                "form": form,
                                "appointment": appointment,
                                "available_medicines": available_medicines,
                                "selected_medicine_id": selected_medicine_id,
                                "dispense_quantity": dispense_quantity,
                            },
                        )

                health_record = form.save(commit=False)
                health_record.appointment = appointment
                health_record.student = appointment.student
                health_record.recorded_by = request.user

                if medicine_to_dispense:
                    medicine_to_dispense.stock_quantity -= dispense_quantity
                    medicine_to_dispense.save(update_fields=["stock_quantity", "updated_at"])

                    dispensed_note = f"Dispensed: {medicine_to_dispense.name} x {dispense_quantity}"
                    existing_treatment = (health_record.treatment or "").strip()

                    if dispensed_note not in existing_treatment:
                        health_record.treatment = (
                            f"{existing_treatment}\n{dispensed_note}".strip()
                            if existing_treatment
                            else dispensed_note
                        )

                health_record.save()

            messages.success(
                request,
                "Health record created successfully.",
            )
            return redirect(redirect_target)
        elif next_page == "appointments":
            messages.error(
                request,
                "Please check your health record details and try again.",
            )
            return redirect(destination)
    else:
        form = HealthRecordForm()

    return render(
        request,
        "accounts/create_health_record.html",
        {
            "form": form,
            "appointment": appointment,
            "available_medicines": available_medicines,
            "selected_medicine_id": selected_medicine_id,
            "dispense_quantity": dispense_quantity,
        },
    )


@student_required
def student_health_records(request):
    health_records = HealthRecord.objects.filter(
        student=request.user,
    ).select_related(
        "appointment",
        "recorded_by",
    ).order_by("-created_at")

    return render(
        request,
        "accounts/student_health_records.html",
        {"health_records": health_records},
    )


@staff_position_required("admin", "nurse")
def issue_sick_note(request, appointment_id):
    appointment = get_object_or_404(
        Appointment.objects.select_related("student"),
        pk=appointment_id,
        status="Completed",
    )

    destination = "accounts:staff_appointments"

    health_record = get_object_or_404(
        HealthRecord,
        appointment=appointment,
    )

    existing_note = SickNote.objects.filter(
        appointment=appointment,
    ).first()

    if existing_note:
        messages.info(
            request,
            "A sick note has already been issued for this appointment.",
        )
        return redirect(destination)

    if request.method == "POST":
        form = SickNoteForm(request.POST)

        if form.is_valid():
            sick_note = form.save(commit=False)
            sick_note.appointment = appointment
            sick_note.issued_by = request.user
            sick_note.save()

            messages.success(
                request,
                "Sick note issued successfully.",
            )
            return redirect(destination)
    else:
        form = SickNoteForm()

    return render(
        request,
        "accounts/issue_sick_note.html",
        {
            "appointment": appointment,
            "health_record": health_record,
            "form": form,
        },
    )


@staff_position_required("admin", "nurse", "records")
def staff_health_records(request):
    health_records = HealthRecord.objects.select_related(
        "student",
        "appointment",
        "recorded_by",
    ).order_by("-created_at")

    return render(
        request,
        "accounts/staff_health_records.html",
        {"health_records": health_records},
    )


@staff_position_required("admin", "nurse", "records")
def view_health_record(request, record_id):
    record = get_object_or_404(
        HealthRecord.objects.select_related(
            "student",
            "appointment",
            "recorded_by",
        ),
        pk=record_id,
    )

    return render(
        request,
        "accounts/view_health_record.html",
        {"record": record},
    )


@staff_position_required("admin", "nurse")
def edit_health_record(request, record_id):
    record = get_object_or_404(
        HealthRecord.objects.select_related(
            "student",
            "appointment",
            "recorded_by",
        ),
        pk=record_id,
    )

    destination = "accounts:staff_appointments"
    next_page = (request.POST.get("next_page") or request.GET.get("next_page") or "").strip()
    redirect_target = destination if next_page == "appointments" else "accounts:staff_health_records"

    available_medicines = list(
        Medicine.objects.filter(
            is_active=True,
            stock_quantity__gt=0,
        ).order_by("name", "dosage_form")
    )

    selected_medicine_id = ""
    dispense_quantity = 1

    if request.method == "POST":
        form = HealthRecordForm(request.POST, instance=record)
        selected_medicine_id = (request.POST.get("dispense_medicine") or "").strip()

        try:
            dispense_quantity = max(1, int(request.POST.get("dispense_quantity") or 1))
        except (TypeError, ValueError):
            dispense_quantity = 1

        if form.is_valid():
            with transaction.atomic():
                medicine_to_dispense = None

                if selected_medicine_id:
                    medicine_to_dispense = (
                        Medicine.objects.select_for_update()
                        .filter(pk=selected_medicine_id, is_active=True)
                        .first()
                    )

                    if not medicine_to_dispense:
                        messages.error(
                            request,
                            "The selected medicine is no longer available.",
                        )
                        if next_page == "appointments":
                            return redirect(destination)
                        return render(
                            request,
                            "accounts/edit_health_record.html",
                            {
                                "record": record,
                                "form": form,
                                "available_medicines": available_medicines,
                                "selected_medicine_id": selected_medicine_id,
                                "dispense_quantity": dispense_quantity,
                            },
                        )

                    if medicine_to_dispense.stock_quantity < dispense_quantity:
                        messages.error(
                            request,
                            f"Insufficient stock for {medicine_to_dispense.name}. Only {medicine_to_dispense.stock_quantity} remaining.",
                        )
                        if next_page == "appointments":
                            return redirect(destination)
                        return render(
                            request,
                            "accounts/edit_health_record.html",
                            {
                                "record": record,
                                "form": form,
                                "available_medicines": available_medicines,
                                "selected_medicine_id": selected_medicine_id,
                                "dispense_quantity": dispense_quantity,
                            },
                        )

                record = form.save(commit=False)
                record.recorded_by = request.user

                if medicine_to_dispense:
                    medicine_to_dispense.stock_quantity -= dispense_quantity
                    medicine_to_dispense.save(update_fields=["stock_quantity", "updated_at"])

                    dispensed_note = f"Dispensed: {medicine_to_dispense.name} x {dispense_quantity}"
                    existing_treatment = (record.treatment or "").strip()

                    record.treatment = (
                        f"{existing_treatment}\n{dispensed_note}".strip()
                        if existing_treatment
                        else dispensed_note
                    )

                record.save()

            messages.success(
                request,
                "Health record updated successfully.",
            )
            return redirect(redirect_target)
        elif next_page == "appointments":
            messages.error(
                request,
                "Please check your health record details and try again.",
            )
            return redirect(destination)
    else:
        form = HealthRecordForm(instance=record)

    return render(
        request,
        "accounts/edit_health_record.html",
        {
            "record": record,
            "form": form,
            "available_medicines": available_medicines,
            "selected_medicine_id": selected_medicine_id,
            "dispense_quantity": dispense_quantity,
        },
    )


@admin_required
@require_POST
def toggle_clinic_status(request):
    clinic_status = get_clinic_status()
    clinic_status.is_available = not clinic_status.is_available
    clinic_status.save()

    if clinic_status.is_available:
        messages.success(request, "Clinic is now Available.")
    else:
        messages.success(request, "Clinic is now Unavailable.")

    return redirect("accounts:dashboard")


@student_required
def student_appointments(request):
    appointments = Appointment.objects.filter(
        student=request.user,
    ).order_by("-created_at")

    counts = get_status_counts(appointments)

    return render(
        request,
        "accounts/student_appointments.html",
        {
            "appointments": appointments,
            "pending_appointments": counts["pending"],
            "approved_appointments": counts["approved"],
            "rejected_appointments": counts["rejected"],
            "completed_appointments": counts["completed"],
            "rescheduled_appointments": counts["rescheduled"],
        },
    )


@student_required
def student_view_reschedule_reason(request, appointment_id):
    appointment = get_object_or_404(
        Appointment,
        pk=appointment_id,
        student=request.user,
        status="Rescheduled",
    )

    return render(
        request,
        "accounts/reschedule_reason.html",
        {"appointment": appointment},
    )


@student_required
def student_sick_notes(request):
    sick_notes = SickNote.objects.filter(
        appointment__student=request.user,
    ).select_related(
        "appointment",
        "issued_by",
    ).order_by("-issued_at")

    return render(
        request,
        "accounts/student_sick_notes.html",
        {"sick_notes": sick_notes},
    )


@login_required
def profile_view(request):
    role = get_role(request.user)

    if role == "student":
        return redirect("accounts:student_profile")

    return render(
        request,
        "accounts/profile.html",
        {
            "user": request.user,
            "role": role,
        },
    )


@student_required
def student_profile(request):
    if request.method == "POST":
        form = StudentProfileUpdateForm(
            request.POST,
            request.FILES,
            instance=request.user,
        )

        if form.is_valid():
            form.save()
            messages.success(
                request,
                "Your profile has been updated successfully.",
            )
            return redirect("accounts:student_profile")
    else:
        form = StudentProfileUpdateForm(instance=request.user)

    return render(
        request,
        "accounts/student_profile.html",
        {
            "form": form,
            "user": request.user,
        },
    )


@student_required
def view_sick_note(request, sick_note_id):
    sick_note = get_object_or_404(
        SickNote.objects.select_related(
            "appointment",
            "appointment__student",
            "appointment__health_record",
            "issued_by",
        ),
        pk=sick_note_id,
        appointment__student=request.user,
    )

    return render(
        request,
        "accounts/sick_note_detail.html",
        {
            "sick_note": sick_note,
            "health_record": sick_note.appointment.health_record,
        },
    )


def build_sick_note_presentation(sick_note):
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
    from pptx.dml.color import RGBColor

    appointment = sick_note.appointment
    student = appointment.student

    health_record = getattr(appointment, "health_record", None)

    student_name = student.get_full_name() or student.username

    symptoms = (
        health_record.symptoms.strip()
        if health_record and health_record.symptoms
        else "No symptoms recorded"
    )

    issued_by = (
        sick_note.issued_by.get_full_name()
        or sick_note.issued_by.username
        if sick_note.issued_by
        else "Clinic Staff"
    )

    appointment_date = (
        appointment.scheduled_date or appointment.preferred_date
    )

    appointment_time = (
        appointment.scheduled_time or appointment.preferred_time
    )

    issued_date = (
        sick_note.issued_at.strftime("%B %d, %Y")
        if sick_note.issued_at
        else "Not provided"
    )

    date_text = (
        appointment_date.strftime("%B %d, %Y")
        if appointment_date
        else "Not provided"
    )

    time_text = (
        appointment_time.strftime("%I:%M %p")
        if appointment_time
        else "Not provided"
    )

    navy = RGBColor(17, 38, 59)
    green = RGBColor(22, 128, 100)
    light_green = RGBColor(232, 246, 241)
    light_gray = RGBColor(245, 247, 249)
    border_gray = RGBColor(222, 228, 233)
    dark_text = RGBColor(39, 51, 63)
    muted_text = RGBColor(105, 117, 128)
    white = RGBColor(255, 255, 255)

    presentation = Presentation()

    presentation.slide_width = Inches(8.27)
    presentation.slide_height = Inches(11.69)

    slide = presentation.slides.add_slide(
        presentation.slide_layouts[6]
    )

    def add_rectangle(x, y, width, height, fill, radius=False):
        shape_type = (
            MSO_SHAPE.ROUNDED_RECTANGLE
            if radius
            else MSO_SHAPE.RECTANGLE
        )

        shape = slide.shapes.add_shape(
            shape_type,
            Inches(x),
            Inches(y),
            Inches(width),
            Inches(height),
        )

        shape.fill.solid()
        shape.fill.fore_color.rgb = fill
        shape.line.fill.background()

        return shape

    def add_text(
        value,
        x,
        y,
        width,
        height,
        size=11,
        color=dark_text,
        bold=False,
        alignment=PP_ALIGN.LEFT,
    ):
        textbox = slide.shapes.add_textbox(
            Inches(x),
            Inches(y),
            Inches(width),
            Inches(height),
        )

        frame = textbox.text_frame
        frame.clear()
        frame.word_wrap = True
        frame.margin_left = Inches(0)
        frame.margin_right = Inches(0)
        frame.margin_top = Inches(0)
        frame.margin_bottom = Inches(0)
        frame.vertical_anchor = MSO_ANCHOR.MIDDLE

        paragraph = frame.paragraphs[0]
        paragraph.text = str(value)
        paragraph.alignment = alignment
        paragraph.font.name = "Aptos"
        paragraph.font.size = Pt(size)
        paragraph.font.bold = bold
        paragraph.font.color.rgb = color

        return textbox

    def add_section_title(value, y):
        add_text(
            value.upper(),
            0.65,
            y,
            6.9,
            0.25,
            size=10,
            color=green,
            bold=True,
        )

    def add_detail(label, value, x, y, width):
        add_text(
            label,
            x,
            y,
            width,
            0.22,
            size=9,
            color=muted_text,
            bold=True,
        )

        add_text(
            value,
            x,
            y + 0.24,
            width,
            0.30,
            size=11,
            color=dark_text,
            bold=True,
        )

    add_rectangle(0, 0, 8.27, 1.75, navy)
    add_rectangle(0, 1.75, 8.27, 0.07, green)

    add_text(
        "CLINIC CONNECT",
        0.65,
        0.35,
        6.9,
        0.35,
        size=22,
        color=white,
        bold=True,
    )

    add_text(
        "SCHOOL CLINIC MANAGEMENT SYSTEM",
        0.67,
        0.78,
        6.9,
        0.22,
        size=9,
        color=RGBColor(194, 211, 220),
        bold=True,
    )

    add_text(
        "MEDICAL SICK NOTE",
        0.65,
        1.12,
        6.9,
        0.38,
        size=17,
        color=white,
        bold=True,
    )

    add_text(
        "OFFICIAL CLINIC DOCUMENT",
        0.65,
        1.52,
        6.9,
        0.15,
        size=8,
        color=RGBColor(194, 211, 220),
    )

    add_rectangle(
        0.65,
        2.05,
        1.55,
        0.34,
        light_green,
        radius=True,
    )

    add_text(
        "ISSUED SICK NOTE",
        0.75,
        2.08,
        1.35,
        0.25,
        size=8,
        color=green,
        bold=True,
        alignment=PP_ALIGN.CENTER,
    )

    add_text(
        f"Date Issued: {issued_date}",
        4.55,
        2.08,
        3.05,
        0.25,
        size=9,
        color=muted_text,
        alignment=PP_ALIGN.RIGHT,
    )

    add_section_title("Student Information", 2.65)

    add_rectangle(
        0.65,
        2.98,
        6.97,
        1.02,
        light_gray,
        radius=True,
    )

    add_detail(
        "STUDENT NAME",
        student_name,
        0.90,
        3.12,
        3.9,
    )

    add_detail(
        "STUDENT ID",
        student.id_number or "Not provided",
        4.75,
        3.12,
        2.55,
    )

    add_section_title("Appointment Information", 4.25)

    add_rectangle(
        0.65,
        4.58,
        6.97,
        1.32,
        light_gray,
        radius=True,
    )

    add_detail(
        "APPOINTMENT DATE",
        date_text,
        0.90,
        4.72,
        2.9,
    )

    add_detail(
        "APPOINTMENT TIME",
        time_text,
        4.35,
        4.72,
        2.8,
    )

    add_detail(
        "HEALTH CONCERN",
        appointment.concern or "Not provided",
        0.90,
        5.30,
        2.9,
    )

    add_detail(
        "APPOINTMENT STATUS",
        appointment.status,
        4.35,
        5.30,
        2.8,
    )

    add_section_title("Reported Symptoms", 6.15)

    add_rectangle(
        0.65,
        6.48,
        6.97,
        1.02,
        light_gray,
        radius=True,
    )

    add_text(
        symptoms,
        0.90,
        6.65,
        6.47,
        0.68,
        size=11,
        color=dark_text,
    )

    add_rectangle(
        0.65,
        7.78,
        6.97,
        0.95,
        light_green,
        radius=True,
    )

    add_text(
        "RECOMMENDED REST",
        0.90,
        7.94,
        3.5,
        0.20,
        size=9,
        color=green,
        bold=True,
    )

    days = sick_note.days_recommended

    add_text(
        f"{days} {'day' if days == 1 else 'days'}",
        0.90,
        8.19,
        5.9,
        0.32,
        size=17,
        color=navy,
        bold=True,
    )

    add_section_title("Additional Notes", 8.98)

    add_rectangle(
        0.65,
        9.30,
        6.97,
        0.75,
        light_gray,
        radius=True,
    )

    add_text(
        sick_note.notes or "No additional notes.",
        0.90,
        9.43,
        6.47,
        0.48,
        size=10,
        color=dark_text,
    )

    add_rectangle(
        0.65,
        10.30,
        6.97,
        0.015,
        border_gray,
    )

    add_text(
        "ISSUED BY",
        0.65,
        10.48,
        3.0,
        0.20,
        size=8,
        color=muted_text,
        bold=True,
    )

    add_text(
        issued_by,
        0.65,
        10.72,
        3.8,
        0.28,
        size=11,
        color=navy,
        bold=True,
    )

    add_text(
        "Clinic Staff",
        0.65,
        11.00,
        3.8,
        0.20,
        size=9,
        color=muted_text,
    )

    add_text(
        "CLINIC CONNECT  |  SCHOOL CLINIC",
        4.0,
        10.75,
        3.62,
        0.25,
        size=8,
        color=muted_text,
        alignment=PP_ALIGN.RIGHT,
    )

    return presentation, student_name


@student_required
def download_sick_note(request, sick_note_id):
    sick_note = get_object_or_404(
        SickNote.objects.select_related(
            "appointment",
            "appointment__student",
            "issued_by",
        ),
        pk=sick_note_id,
        appointment__student=request.user,
    )

    presentation, _ = build_sick_note_presentation(sick_note)

    response = HttpResponse(
        content_type=(
            "application/vnd.openxmlformats-officedocument."
            "presentationml.presentation"
        )
    )
    response["Content-Disposition"] = (
        f'attachment; filename="Sick_Note_{sick_note.id}.pptx"'
    )

    presentation.save(response)
    return response


@student_required
@require_POST
def email_sick_note(request, sick_note_id):
    sick_note = get_object_or_404(
        SickNote.objects.select_related(
            "appointment",
            "appointment__student",
            "issued_by",
        ),
        pk=sick_note_id,
        appointment__student=request.user,
    )

    if not request.user.email:
        messages.error(
            request,
            "Your account does not have an email address.",
        )
        return redirect(
            "accounts:view_sick_note",
            sick_note_id=sick_note.id,
        )

    presentation, student_name = build_sick_note_presentation(sick_note)
    pptx_file = BytesIO()
    presentation.save(pptx_file)
    pptx_file.seek(0)

    email = EmailMessage(
        subject="Clinic Connect - Sick Note",
        body=(
            f"Hello {student_name},\n\n"
            "Your sick note from Clinic Connect is attached to this email.\n\n"
            "Please contact the clinic if you have questions.\n\n"
            "Clinic Connect"
        ),
        from_email=None,
        to=[request.user.email],
    )

    email.attach(
        f"Sick_Note_{sick_note.id}.pptx",
        pptx_file.getvalue(),
        (
            "application/vnd.openxmlformats-officedocument."
            "presentationml.presentation"
        ),
    )

    try:
        if email.send(fail_silently=True) > 0:
            messages.success(
                request,
                f"The sick note has been sent to {request.user.email}.",
            )
        else:
            messages.error(request, "The email could not be sent.")
    except Exception:
        messages.error(
            request,
            "An error occurred while sending the email.",
        )

    return redirect(
        "accounts:view_sick_note",
        sick_note_id=sick_note.id,
    )


@admin_required
def staff_settings(request):
    clinic_status = get_clinic_status()
    total_staff = User.objects.filter(role="staff").count()
    total_teachers = User.objects.filter(role="teacher").count()
    total_departments = Department.objects.count()

    context = {
        "current": "settings",
        "clinic_status": clinic_status,
        "total_staff": total_staff,
        "total_teachers": total_teachers,
        "total_departments": total_departments,
    }
    return render(request, "accounts/staff_settings.html", context)


@admin_required
def admin_user_management(request):
    from django.db.models import Q, Value
    from django.db.models.functions import Concat

    all_users = User.objects.filter(
        role__in=["student", "teacher", "staff"]
    )

    users = all_users.annotate(
        full_name=Concat("first_name", Value(" "), "last_name"),
        full_name_with_middle=Concat(
            "first_name",
            Value(" "),
            "middle_name",
            Value(" "),
            "last_name",
        ),
    ).order_by("last_name", "first_name", "username")

    search_query = request.GET.get("q", "").strip()
    selected_role = request.GET.get("role", "").strip().lower()
    selected_status = request.GET.get("status", "").strip().lower()

    if search_query:
        users = users.filter(
            Q(full_name__icontains=search_query)
            | Q(full_name_with_middle__icontains=search_query)
            | Q(first_name__icontains=search_query)
            | Q(last_name__icontains=search_query)
            | Q(middle_name__icontains=search_query)
            | Q(username__icontains=search_query)
            | Q(email__icontains=search_query)
            | Q(id_number__icontains=search_query)
            | Q(department__icontains=search_query)
            | Q(course__icontains=search_query)
            | Q(staff_position__icontains=search_query)
            | Q(contact_number__icontains=search_query)
        )

    if selected_role in ["student", "teacher", "staff"]:
        users = users.filter(role=selected_role)

    if selected_status == "active":
        users = users.filter(is_active=True)
    elif selected_status == "inactive":
        users = users.filter(is_active=False)

    context = {
        "current": "admin_user_management",
        "users": users,
        "search_query": search_query,
        "selected_role": selected_role,
        "selected_status": selected_status,
        "total_users": all_users.count(),
        "total_students": all_users.filter(role="student").count(),
        "total_teachers": all_users.filter(role="teacher").count(),
        "total_clinic_staff": all_users.filter(role="staff").count(),
    }

    return render(
        request,
        "accounts/admin_user_management.html",
        context,
    )


@admin_required
def admin_user_detail(request, user_id):
    user_obj = get_object_or_404(
        User,
        pk=user_id,
        role__in=["student", "teacher", "staff"],
    )

    context = {
        "current": "admin_user_management",
        "user_obj": user_obj,
    }

    return render(
        request,
        "accounts/admin_user_detail.html",
        context,
    )


@admin_required
@require_POST
def toggle_user_status(request, user_id):
    user_obj = get_object_or_404(
        User,
        pk=user_id,
        role__in=["student", "teacher", "staff"],
    )

    if user_obj.pk == request.user.pk:
        messages.error(
            request,
            "You cannot change your own account status.",
        )
        return redirect("accounts:admin_user_management")

    if (
        user_obj.role == "staff"
        and user_obj.staff_position == "admin"
    ):
        messages.error(
            request,
            "The Clinic Administrator account cannot be deactivated or changed here.",
        )
        return redirect("accounts:admin_user_management")

    action = request.POST.get("action", "").strip().lower()

    if action == "deactivate":
        if not user_obj.is_active:
            messages.info(request, "This account is already inactive.")
        else:
            user_obj.is_active = False
            user_obj.save(update_fields=["is_active"])
            messages.success(
                request,
                f"{user_obj.get_full_name() or user_obj.username} has been deactivated.",
            )

    elif action == "activate":
        if user_obj.is_active:
            messages.info(request, "This account is already active.")
        else:
            user_obj.is_active = True
            user_obj.save(update_fields=["is_active"])
            messages.success(
                request,
                f"{user_obj.get_full_name() or user_obj.username} has been activated.",
            )

    else:
        messages.error(request, "Invalid account status action.")

    return redirect("accounts:admin_user_management")


@staff_position_required("admin", "nurse")
def staff_medicines(request):
    search_query = (request.GET.get("q") or "").strip()
    status_filter = (request.GET.get("status") or "").strip().lower()

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()

        if action == "add":
            name = " ".join((request.POST.get("name") or "").split())
            dosage_form = " ".join((request.POST.get("dosage_form") or "").split())

            try:
                stock_quantity = max(0, int(request.POST.get("stock_quantity") or 0))
            except (TypeError, ValueError):
                stock_quantity = 0

            try:
                reorder_level = max(0, int(request.POST.get("reorder_level") or 5))
            except (TypeError, ValueError):
                reorder_level = 5

            is_active = request.POST.get("is_active") == "on"

            if not name:
                messages.error(request, "Medicine name is required.")
            else:
                Medicine.objects.create(
                    name=name,
                    dosage_form=dosage_form,
                    stock_quantity=stock_quantity,
                    reorder_level=reorder_level,
                    is_active=is_active,
                )
                messages.success(request, f"{name} has been added to clinic inventory.")
            return redirect("accounts:staff_medicines")

        if action == "adjust":
            medicine_id = request.POST.get("medicine_id")
            medicine = get_object_or_404(Medicine, pk=medicine_id)

            try:
                delta = int(request.POST.get("delta") or 0)
            except (TypeError, ValueError):
                delta = 0

            new_quantity = max(0, medicine.stock_quantity + delta)
            medicine.stock_quantity = new_quantity
            medicine.save(update_fields=["stock_quantity", "updated_at"])
            messages.success(
                request,
                f"Updated {medicine.name} stock to {medicine.stock_quantity}.",
            )
            return redirect("accounts:staff_medicines")

        if action == "toggle_active":
            medicine_id = request.POST.get("medicine_id")
            medicine = get_object_or_404(Medicine, pk=medicine_id)
            medicine.is_active = not medicine.is_active
            medicine.save(update_fields=["is_active", "updated_at"])
            state_label = "active" if medicine.is_active else "inactive"
            messages.success(request, f"{medicine.name} is now marked as {state_label}.")
            return redirect("accounts:staff_medicines")

    all_medicines = list(Medicine.objects.all())
    medicines = all_medicines

    if search_query:
        q_lower = search_query.casefold()
        medicines = [
            med for med in medicines
            if q_lower in (med.name or "").casefold()
            or q_lower in (med.dosage_form or "").casefold()
        ]

    if status_filter == "in_stock":
        medicines = [med for med in medicines if med.stock_status == "In Stock"]
    elif status_filter == "low_stock":
        medicines = [med for med in medicines if med.stock_status == "Low Stock"]
    elif status_filter == "out_of_stock":
        medicines = [med for med in medicines if med.stock_status == "Out of Stock"]

    in_stock_count = sum(1 for med in all_medicines if med.stock_status == "In Stock")
    low_stock_count = sum(1 for med in all_medicines if med.stock_status == "Low Stock")
    out_of_stock_count = sum(1 for med in all_medicines if med.stock_status == "Out of Stock")

    return render(
        request,
        "accounts/staff_medicines.html",
        {
            "medicines": medicines,
            "query_str": search_query,
            "current_status": status_filter,
            "in_stock_count": in_stock_count,
            "low_stock_count": low_stock_count,
            "out_of_stock_count": out_of_stock_count,
        },
    )


def get_announcements_for_user(user, department=None):
    target_dept = department or getattr(user, 'department_obj', None)
    audience_filter = Q(audience='all')

    if getattr(user, 'role', None) == 'student':
        audience_filter |= Q(audience='student')
    elif getattr(user, 'role', None) == 'teacher':
        audience_filter |= Q(audience='teacher')
    elif getattr(user, 'role', None) == 'staff':
        audience_filter |= Q(audience='all') | Q(audience='student') | Q(audience='teacher') | Q(audience='department')

    if target_dept is not None:
        audience_filter |= Q(audience='department', department=target_dept)

    return ClinicAnnouncement.objects.filter(is_active=True).filter(audience_filter).select_related('department')


@staff_position_required("admin", "nurse", "receptionist")
def staff_announcements(request):
    active_departments = Department.objects.filter(is_active=True).order_by("name")
    all_announcements = ClinicAnnouncement.objects.select_related("department", "created_by")
    return render(
        request,
        "accounts/staff_announcements.html",
        {
            "active_departments": active_departments,
            "all_announcements": all_announcements,
        },
    )


@staff_position_required("admin", "nurse", "receptionist")
@require_POST
def create_clinic_announcement(request):
    title = " ".join((request.POST.get("title") or "").split())
    message = (request.POST.get("message") or "").strip()
    audience = (request.POST.get("audience") or "all").strip().lower()
    department_id = (request.POST.get("department") or "").strip()
    event_date_str = (request.POST.get("event_date") or "").strip()
    start_time_str = (request.POST.get("start_time") or "").strip()
    end_time_str = (request.POST.get("end_time") or "").strip()

    valid_audiences = {"all", "student", "teacher", "department"}
    if audience not in valid_audiences:
        audience = "all"

    if not title or not message:
        messages.error(request, "Announcement title and message are required.")
        return redirect("accounts:staff_announcements")

    department = None
    if audience == "department":
        if not department_id.isdigit():
            messages.error(request, "Please select a department for a department announcement.")
            return redirect("accounts:staff_announcements")
        department = Department.objects.filter(pk=int(department_id), is_active=True).first()
        if not department:
            messages.error(request, "Selected department was not found.")
            return redirect("accounts:staff_announcements")

    event_date = None
    if event_date_str:
        try:
            event_date = datetime.strptime(event_date_str, "%Y-%m-%d").date()
        except ValueError:
            messages.error(request, "Invalid event date format.")
            return redirect("accounts:staff_announcements")

    start_time = None
    if start_time_str:
        try:
            start_time = datetime.strptime(start_time_str, "%H:%M").time()
        except ValueError:
            messages.error(request, "Invalid start time format.")
            return redirect("accounts:staff_announcements")

    end_time = None
    if end_time_str:
        try:
            end_time = datetime.strptime(end_time_str, "%H:%M").time()
        except ValueError:
            messages.error(request, "Invalid end time format.")
            return redirect("accounts:staff_announcements")

    ClinicAnnouncement.objects.create(
        title=title,
        message=message,
        audience=audience,
        department=department,
        event_date=event_date,
        start_time=start_time,
        end_time=end_time,
        is_active=True,
        created_by=request.user,
    )

    messages.success(request, "Clinic announcement published.")
    return redirect("accounts:staff_announcements")


@staff_position_required("admin", "nurse", "receptionist")
@require_POST
def toggle_clinic_announcement(request, announcement_id):
    announcement = get_object_or_404(ClinicAnnouncement, pk=announcement_id)
    announcement.is_active = not announcement.is_active
    announcement.save(update_fields=["is_active"])

    state = "activated" if announcement.is_active else "hidden"
    messages.success(request, f"Announcement {state}.")
    return redirect("accounts:staff_announcements")


@staff_position_required("admin", "nurse", "receptionist")
@require_POST
def delete_clinic_announcement(request, announcement_id):
    announcement = get_object_or_404(ClinicAnnouncement, pk=announcement_id)
    announcement.delete()

    messages.success(request, "Announcement deleted.")
    return redirect("accounts:staff_announcements")