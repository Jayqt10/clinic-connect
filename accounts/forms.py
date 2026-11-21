
from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.validators import FileExtensionValidator
from django.contrib.auth.forms import UserCreationForm
from django.utils import timezone
from django.db.models.functions import Lower, Trim
import re

from .models import (
    User,
    Department,
    Building,
    Room,
    Course,
    Appointment,
    Referral,
    HealthRecord,
    SickNote,
)


class StudentAppointmentForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = [
            "concern",
            "preferred_date",
            "preferred_time",
        ]

        labels = {
            "concern": "Health Concern",
            "preferred_date": "Preferred Date",
            "preferred_time": "Preferred Time",
        }

        widgets = {
            "concern": forms.Textarea(attrs={
                "rows": 4,
                "placeholder": "Enter your health concern...",
            }),
            "preferred_date": forms.DateInput(attrs={
                "type": "date",
            }),
            "preferred_time": forms.TimeInput(attrs={
                "type": "time",
            }),
        }



class SignUpForm(UserCreationForm):
    YEAR_CHOICES = [
        ("", "Select Year Level"),
        ("1st Year", "1st Year"),
        ("2nd Year", "2nd Year"),
        ("3rd Year", "3rd Year"),
        ("4th Year", "4th Year"),
    ]

    block = forms.CharField(
        max_length=10,
        required=True,
        widget=forms.TextInput(attrs={
            "placeholder": "Enter your block (e.g., G)",
            "autocomplete": "off",
        }),
    )

    verification_evidence = forms.FileField(
        required=True,
        label="Upload Student ID",
        help_text="Accepted formats: JPG, PNG, WEBP, or PDF. Maximum size: 5 MB.",
        widget=forms.ClearableFileInput(attrs={
            "accept": ".jpg,.jpeg,.png,.webp,.pdf",
        }),
    )

    department = forms.ChoiceField(
        choices=[("", "Select Department")],
        required=True,
        label="Department",
        widget=forms.Select(attrs={
            "class": "select-field",
            "id": "id_department",
        }),
    )

    course = forms.CharField(
        max_length=200,
        required=True,
        label="Course",
        widget=forms.TextInput(attrs={
            "class": "select-field",
            "id": "id_course",
            "placeholder": "Enter your course (e.g., BSIT, BSCS)",
            "autocomplete": "off",
        }),
    )

    year_block = forms.ChoiceField(
        choices=YEAR_CHOICES,
        required=True,
        label="Year Level",
        widget=forms.Select(attrs={
            "class": "select-field",
        }),
    )

    class Meta:
        model = User
        fields = (
            "username",
            "email",
            "first_name",
            "middle_name",
            "last_name",
            "id_number",
            "sex",
            "department",
            "course",
            "year_block",
        )

        labels = {
            "username": "Username",
            "email": "Email Address",
            "first_name": "First Name",
            "middle_name": "Middle Name",
            "last_name": "Last Name",
            "id_number": "Student ID",
            "sex": "Sex",
            "department": "Department",
            "course": "Course",
            "year_block": "Year Level",
        }

        widgets = {
            "username": forms.TextInput(attrs={
                "placeholder": "Enter username",
                "autocomplete": "username",
            }),
            "email": forms.EmailInput(attrs={
                "placeholder": "Enter email address",
                "autocomplete": "email",
            }),
            "first_name": forms.TextInput(attrs={
                "placeholder": "Enter first name",
                "autocomplete": "given-name",
            }),
            "middle_name": forms.TextInput(attrs={
                "placeholder": "Enter middle name",
            }),
            "last_name": forms.TextInput(attrs={
                "placeholder": "Enter last name",
                "autocomplete": "family-name",
            }),
            "id_number": forms.TextInput(attrs={
                "placeholder": "Enter student ID",
            }),
            "sex": forms.Select(choices=[
                ("", "Select Sex"),
                ("Male", "Male"),
                ("Female", "Female"),
            ]),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        departments = Department.objects.filter(
            is_active=True
        ).order_by("name")

        self.fields["department"].choices = [
            ("", "Select Department"),
            *[
                (str(department.pk), department.name)
                for department in departments
            ],
        ]

        self.fields["email"].required = True
        self.fields["id_number"].required = True
        self.fields["sex"].required = True
        self.fields["department"].required = True
        self.fields["course"].required = True
        self.fields["year_block"].required = True

        self.fields["password1"].widget.attrs.update({
            "placeholder": "Create a password",
            "autocomplete": "new-password",
            "minlength": "8",
        })

        self.fields["password2"].widget.attrs.update({
            "placeholder": "Confirm your password",
            "autocomplete": "new-password",
            "minlength": "8",
        })

    def clean_block(self):
        block = self.cleaned_data.get("block", "").strip().upper()

        if not block:
            raise forms.ValidationError("Block is required.")

        if not re.fullmatch(r"[A-Z0-9-]{1,10}", block):
            raise forms.ValidationError(
                "Enter a valid block using letters, numbers, or hyphens."
            )

        return block

    def clean_course(self):
        course = self.cleaned_data.get("course", "").strip()

        if not course:
            raise forms.ValidationError("Course is required.")

        return course

    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip().lower()

        if not email:
            raise forms.ValidationError(
                "Email address is required."
            )

        duplicates = User.objects.annotate(
            normalized=Lower(Trim("email"))
        ).filter(
            normalized=email
        )

        if self.instance.pk:
            duplicates = duplicates.exclude(
                pk=self.instance.pk
            )

        if duplicates.exists():
            raise forms.ValidationError(
                "An account with this email address already exists."
            )

        return email

    def clean_id_number(self):
        id_number = self.cleaned_data.get(
            "id_number", ""
        ).strip().upper()

        if not id_number:
            raise forms.ValidationError(
                "Student ID is required."
            )

        duplicates = User.objects.filter(
            role="student"
        ).annotate(
            normalized=Lower(Trim("id_number"))
        ).filter(
            normalized=id_number.lower()
        )

        if self.instance.pk:
            duplicates = duplicates.exclude(
                pk=self.instance.pk
            )

        if duplicates.exists():
            raise forms.ValidationError(
                "This Student ID is already registered."
            )

        return id_number

    def clean_verification_evidence(self):
        uploaded_file = self.cleaned_data.get(
            "verification_evidence"
        )

        if not uploaded_file:
            return uploaded_file

        allowed_types = {
            "image/jpeg",
            "image/png",
            "image/webp",
            "application/pdf",
        }

        if uploaded_file.size > 5 * 1024 * 1024:
            raise forms.ValidationError(
                "The student ID file must not exceed 5 MB."
            )

        if uploaded_file.content_type not in allowed_types:
            raise forms.ValidationError(
                "Upload a JPG, PNG, WEBP, or PDF file."
            )

        return uploaded_file

    def clean(self):
        cleaned_data = super().clean()

        department_id = cleaned_data.get("department")

        department = Department.objects.filter(
            pk=department_id,
            is_active=True,
        ).first() if department_id else None

        if department_id and not department:
            self.add_error(
                "department",
                "Please select a valid active department.",
            )

        if not cleaned_data.get("department") and "department" not in self.errors:
            self.add_error(
                "department",
                "Department is required.",
            )

        if not cleaned_data.get("course") and "course" not in self.errors:
            self.add_error(
                "course",
                "Course is required.",
            )

        if not cleaned_data.get("year_block") and "year_block" not in self.errors:
            self.add_error(
                "year_block",
                "Year Level is required.",
            )

        if department:
            cleaned_data["department"] = department

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)

        department = self.cleaned_data["department"]
        course = self.cleaned_data["course"]
        block = self.cleaned_data["block"]

        user.department = department.code or department.name
        user.course = course.strip()
        user.block = block
        user.year_block = self.cleaned_data["year_block"]

        if commit:
            user.save()
            self.save_m2m()

        return user


class ProfilePictureField(forms.ImageField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("required", False)
        kwargs.setdefault("label", "Profile Picture")
        kwargs.setdefault(
            "help_text",
            "Optional. JPG, JPEG, PNG, or WEBP. Maximum size: 5 MB."
        )
        kwargs.setdefault(
            "validators",
            [
                FileExtensionValidator(
                    allowed_extensions=["jpg", "jpeg", "png", "webp"]
                )
            ],
        )
        kwargs.setdefault(
            "widget",
            forms.ClearableFileInput(attrs={
                "accept": ".jpg,.jpeg,.png,.webp",
            })
        )
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        uploaded_file = super().clean(data, initial)

        if uploaded_file and uploaded_file is not False:
            if uploaded_file.size > 5 * 1024 * 1024:
                raise forms.ValidationError(
                    "Profile picture must not exceed 5 MB."
                )

        return uploaded_file


class UserUpdateForm(forms.ModelForm):
    profile_picture = ProfilePictureField()

    class Meta:
        model = User
        fields = (
            "first_name",
            "middle_name",
            "last_name",
            "email",
            "id_number",
            "sex",
            "contact_number",
            "profile_picture",
            "department",
        )

        labels = {
            "first_name": "First Name",
            "middle_name": "Middle Name",
            "last_name": "Last Name",
            "email": "Email Address",
            "id_number": "ID Number",
            "sex": "Gender",
            "contact_number": "Contact Number",
            "profile_picture": "Profile Picture",
            "department": "Department",
        }

        widgets = {
            "first_name": forms.TextInput(attrs={
                "placeholder": "Enter first name",
            }),
            "middle_name": forms.TextInput(attrs={
                "placeholder": "Enter middle name",
            }),
            "last_name": forms.TextInput(attrs={
                "placeholder": "Enter last name",
            }),
            "email": forms.EmailInput(attrs={
                "placeholder": "Enter email address",
            }),
            "id_number": forms.TextInput(attrs={
                "placeholder": "Enter ID number",
            }),
            "sex": forms.Select(choices=[
                ("", "Select Gender"),
                ("Male", "Male"),
                ("Female", "Female"),
            ]),
            "contact_number": forms.TextInput(attrs={
                "placeholder": "Enter contact number",
            }),
            "department": forms.TextInput(attrs={
                "placeholder": "Enter department",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        role = getattr(self.instance, "role", "student")

        common_fields = [
            "first_name",
            "middle_name",
            "last_name",
            "email",
            "id_number",
            "sex",
            "contact_number",
            "profile_picture",
        ]

        if role == "teacher":
            allowed_fields = common_fields + ["department"]
        else:
            allowed_fields = common_fields

        for field_name in list(self.fields):
            if field_name not in allowed_fields:
                self.fields.pop(field_name)

        self.fields["email"].required = True

    def clean_email(self):
        email = (
            self.cleaned_data.get("email") or ""
        ).strip().lower()

        if not email:
            raise forms.ValidationError(
                "Email address is required."
            )

        duplicates = User.objects.annotate(
            normalized=Lower(Trim("email"))
        ).filter(
            normalized=email
        )

        if self.instance.pk:
            duplicates = duplicates.exclude(
                pk=self.instance.pk
            )

        if duplicates.exists():
            raise forms.ValidationError(
                "An account with this email address already exists."
            )

        return email

    def clean_id_number(self):
        id_number = (
            self.cleaned_data.get("id_number") or ""
        ).strip()

        if (
            getattr(self.instance, "role", None) == "student"
            and id_number
        ):
            id_number = id_number.upper()

            duplicates = User.objects.filter(
                role="student"
            ).annotate(
                normalized=Lower(Trim("id_number"))
            ).filter(
                normalized=id_number.lower()
            )

            if self.instance.pk:
                duplicates = duplicates.exclude(
                    pk=self.instance.pk
                )

            if duplicates.exists():
                raise forms.ValidationError(
                    "This Student ID is already registered."
                )

        return id_number


class StudentProfileUpdateForm(forms.ModelForm):
    profile_picture = ProfilePictureField()

    class Meta:
        model = User

        fields = (
            "first_name",
            "middle_name",
            "last_name",
            "email",
            "id_number",
            "contact_number",
            "sex",
            "course",
            "year_block",
            "profile_picture",
        )

        labels = {
            "first_name": "First Name",
            "middle_name": "Middle Name",
            "last_name": "Last Name",
            "email": "Email Address",
            "id_number": "Student ID",
            "contact_number": "Contact Number",
            "sex": "Sex",
            "course": "Course",
            "year_block": "Year/Block",
            "profile_picture": "Profile Picture",
        }

        widgets = {
            "first_name": forms.TextInput(attrs={
                "placeholder": "Enter first name",
            }),
            "middle_name": forms.TextInput(attrs={
                "placeholder": "Enter middle name",
            }),
            "last_name": forms.TextInput(attrs={
                "placeholder": "Enter last name",
            }),
            "email": forms.EmailInput(attrs={
                "placeholder": "Enter student email",
            }),
            "id_number": forms.TextInput(attrs={
                "placeholder": "Enter student ID",
            }),
            "contact_number": forms.TextInput(attrs={
                "placeholder": "Enter contact number",
            }),
            "sex": forms.Select(choices=[
                ("", "Select Sex"),
                ("Male", "Male"),
                ("Female", "Female"),
            ]),
            "course": forms.TextInput(attrs={
                "placeholder": "Enter your course",
            }),
            "year_block": forms.TextInput(attrs={
                "placeholder": "Enter year/block",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["email"].required = True
        self.fields["id_number"].required = True
        self.fields["course"].required = True
        self.fields["year_block"].required = True

    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip().lower()

        if not email:
            raise forms.ValidationError(
                "Email address is required."
            )

        duplicates = User.objects.annotate(
            normalized=Lower(Trim("email"))
        ).filter(
            normalized=email
        ).exclude(
            pk=self.instance.pk
        )

        if duplicates.exists():
            raise forms.ValidationError(
                "An account with this email address already exists."
            )

        return email

    def clean_id_number(self):
        id_number = self.cleaned_data.get(
            "id_number", ""
        ).strip().upper()

        if not id_number:
            raise forms.ValidationError(
                "Student ID is required."
            )

        duplicates = User.objects.filter(
            role="student"
        ).annotate(
            normalized=Lower(Trim("id_number"))
        ).filter(
            normalized=id_number.lower()
        ).exclude(
            pk=self.instance.pk
        )

        if duplicates.exists():
            raise forms.ValidationError(
                "This Student ID is already registered."
            )

        return id_number

class StudentUpdateForm(forms.ModelForm):
    class Meta:
        model = User

        fields = (
            "first_name",
            "middle_name",
            "last_name",
            "email",
            "id_number",
            "sex",
            "course",
            "department",
            "year_block",
            "contact_number",
        )

        labels = {
            "first_name": "First Name",
            "middle_name": "Middle Name",
            "last_name": "Last Name",
            "email": "Email",
            "id_number": "Student ID",
            "sex": "Sex",
            "course": "Course",
            "department": "Department",
            "year_block": "Year/Block",
            "contact_number": "Contact Number",
        }

        widgets = {
            "first_name": forms.TextInput(attrs={
                "placeholder": "Enter first name",
            }),
            "middle_name": forms.TextInput(attrs={
                "placeholder": "Enter middle name",
            }),
            "last_name": forms.TextInput(attrs={
                "placeholder": "Enter last name",
            }),
            "email": forms.EmailInput(attrs={
                "placeholder": "Enter student email",
            }),
            "id_number": forms.TextInput(attrs={
                "placeholder": "Enter student ID",
            }),
            "sex": forms.Select(choices=[
                ("", "Select Sex"),
                ("Male", "Male"),
                ("Female", "Female"),
            ]),
            "course": forms.TextInput(attrs={
                "placeholder": "Enter course",
            }),
            "year_block": forms.TextInput(attrs={
                "placeholder": "Enter year/block",
            }),
            "contact_number": forms.TextInput(attrs={
                "placeholder": "Enter contact number",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        choices = [("", "Select Department")]

        for dept in Department.objects.filter(
            is_active=True
        ).order_by("name"):
            choices.append((dept.code or dept.name, dept.name))

        current = (
            (self.instance.department or "").strip()
            if self.instance else ""
        )

        if current and current not in [value for value, _ in choices]:
            choices.append((current, current))

        self.fields["department"] = forms.ChoiceField(
            label="Department",
            choices=choices,
            required=False,
        )

        self.fields["email"].required = True

    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip().lower()

        if not email:
            raise forms.ValidationError(
                "Email address is required."
            )

        duplicates = User.objects.annotate(
            normalized=Lower(Trim("email"))
        ).filter(
            normalized=email
        ).exclude(
            pk=self.instance.pk
        )

        if duplicates.exists():
            raise forms.ValidationError(
                "An account with this email address already exists."
            )

        return email

    def clean_id_number(self):
        id_number = self.cleaned_data.get(
            "id_number", ""
        ).strip().upper()

        if id_number:
            duplicates = User.objects.filter(
                role="student"
            ).annotate(
                normalized=Lower(Trim("id_number"))
            ).filter(
                normalized=id_number.lower()
            ).exclude(
                pk=self.instance.pk
            )

            if duplicates.exists():
                raise forms.ValidationError(
                    "This Student ID is already registered."
                )

        return id_number


class AddStudentForm(forms.Form):
    id_number = forms.CharField(
        max_length=50,
        label="Student ID",
        widget=forms.TextInput(attrs={
            "class": "student-input",
            "placeholder": "Enter student ID",
        }),
    )

    first_name = forms.CharField(
        max_length=150,
        label="First Name",
        widget=forms.TextInput(attrs={
            "class": "student-input",
            "placeholder": "Enter first name",
        }),
    )

    middle_name = forms.CharField(
        max_length=100,
        label="Middle Name",
        required=False,
        widget=forms.TextInput(attrs={
            "class": "student-input",
            "placeholder": "Enter middle name",
        }),
    )

    last_name = forms.CharField(
        max_length=150,
        label="Last Name",
        widget=forms.TextInput(attrs={
            "class": "student-input",
            "placeholder": "Enter last name",
        }),
    )

    sex = forms.ChoiceField(
        label="Sex",
        choices=[
            ("", "Select Sex"),
            ("Male", "Male"),
            ("Female", "Female"),
        ],
        widget=forms.Select(attrs={
            "class": "student-select",
        }),
    )

    course = forms.CharField(
        max_length=100,
        label="Course",
        widget=forms.TextInput(attrs={
            "class": "student-input",
            "placeholder": "Enter course",
        }),
    )

    year_block = forms.CharField(
        max_length=100,
        label="Year/Block",
        widget=forms.TextInput(attrs={
            "class": "student-input",
            "placeholder": "Enter year/block",
        }),
    )

    email = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={
            "class": "student-input",
            "placeholder": "Enter student email",
        }),
    )

    contact_number = forms.CharField(
        max_length=20,
        label="Contact Number",
        required=False,
        widget=forms.TextInput(attrs={
            "class": "student-input",
            "placeholder": "Enter contact number (optional)",
        }),
    )

    def clean_id_number(self):
        value = self.cleaned_data["id_number"].strip().upper()

        if not value:
            raise forms.ValidationError(
                "Please enter the student ID."
            )

        duplicates = User.objects.filter(
            role="student"
        ).annotate(
            normalized=Lower(Trim("id_number"))
        ).filter(
            normalized=value.lower()
        )

        if duplicates.exists():
            raise forms.ValidationError(
                "This Student ID is already registered."
            )

        return value

    def clean_first_name(self):
        value = self.cleaned_data["first_name"].strip()

        if not value:
            raise forms.ValidationError("Please enter the first name.")

        return value

    def clean_middle_name(self):
        return self.cleaned_data.get("middle_name", "").strip()

    def clean_last_name(self):
        value = self.cleaned_data["last_name"].strip()

        if not value:
            raise forms.ValidationError("Please enter the last name.")

        return value

    def clean_sex(self):
        value = self.cleaned_data.get("sex")

        if not value:
            raise forms.ValidationError("Please select the student sex.")

        return value

    def clean_course(self):
        value = self.cleaned_data["course"].strip()

        if not value:
            raise forms.ValidationError("Please enter the course.")

        return value

    def clean_year_block(self):
        value = self.cleaned_data["year_block"].strip()

        if not value:
            raise forms.ValidationError("Please enter the year/block.")

        return value

    def clean_email(self):
        value = self.cleaned_data["email"].strip().lower()

        if not value:
            raise forms.ValidationError(
                "Please enter the student email."
            )

        duplicates = User.objects.annotate(
            normalized=Lower(Trim("email"))
        ).filter(
            normalized=value
        )

        if duplicates.exists():
            raise forms.ValidationError(
                "An account with this email address already exists."
            )

        return value

    def clean_contact_number(self):
        return self.cleaned_data.get("contact_number", "").strip()


class RoomSelect(forms.Select):
    def create_option(
        self,
        name,
        value,
        label,
        selected,
        index,
        subindex=None,
        attrs=None,
    ):
        option = super().create_option(
            name,
            value,
            label,
            selected,
            index,
            subindex,
            attrs,
        )

        instance = getattr(value, "instance", None)

        if instance is not None:
            option["attrs"]["data-building"] = str(
                instance.building_id or ""
            )
            option["attrs"]["data-floor"] = str(instance.floor)

        return option


class BuildingSelect(forms.Select):
    def create_option(
        self,
        name,
        value,
        label,
        selected,
        index,
        subindex=None,
        attrs=None,
    ):
        option = super().create_option(
            name,
            value,
            label,
            selected,
            index,
            subindex,
            attrs,
        )

        instance = getattr(value, "instance", None)

        if instance is not None:
            option["attrs"]["data-department"] = str(
                instance.department_id
            )

        return option


class RoomSelect(forms.Select):
    def create_option(
        self,
        name,
        value,
        label,
        selected,
        index,
        subindex=None,
        attrs=None,
    ):
        option = super().create_option(
            name,
            value,
            label,
            selected,
            index,
            subindex,
            attrs,
        )

        instance = getattr(value, "instance", None)

        if instance is not None:
            option["attrs"]["data-building"] = str(
                instance.building_id or ""
            )
            option["attrs"]["data-floor"] = str(instance.floor)

        return option

class TeacherReferralForm(forms.ModelForm):
    floor = forms.ChoiceField(
        label="Floor",
        required=False,
        choices=[("", "Select Floor")],
        widget=forms.Select(attrs={
            "class": "emergency-control",
            "id": "id_floor",
        }),
    )

    class Meta:
        model = Referral
        fields = [
            "student_name",
            "department",
            "building",
            "room",
            "location",
            "symptoms",
        ]

        widgets = {
            "student_name": forms.TextInput(attrs={
                "class": "emergency-control",
                "placeholder": "Enter student's full name (optional)",
            }),
            "department": forms.Select(attrs={
                "class": "emergency-control",
            }),
            "building": BuildingSelect(attrs={
                "class": "emergency-control",
            }),
            "room": RoomSelect(attrs={
                "class": "emergency-control",
            }),
            "location": forms.HiddenInput(attrs={
                "id": "id_location",
            }),
            "symptoms": forms.Textarea(attrs={
                "class": "emergency-control",
                "rows": 4,
                "placeholder": "Describe the emergency (optional)...",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        optional_fields = [
            "student_name",
            "department",
            "building",
            "room",
            "location",
            "symptoms",
        ]

        for field_name in optional_fields:
            self.fields[field_name].required = False

        self.fields["department"].queryset = Department.objects.filter(
            is_active=True
        ).order_by("name")

        self.fields["building"].queryset = Building.objects.select_related(
            "department"
        ).order_by("name")

        self.fields["room"].queryset = Room.objects.select_related(
            "building"
        ).order_by("room_number")

        department_id = self.data.get("department") if self.is_bound else None
        building_id = self.data.get("building") if self.is_bound else None
        floor_value = self.data.get("floor") if self.is_bound else None

        if department_id:
            self.fields["building"].queryset = (
                self.fields["building"].queryset.filter(
                    department_id=department_id
                )
            )

        if building_id:
            self.fields["room"].queryset = (
                self.fields["room"].queryset.filter(
                    building_id=building_id
                )
            )

        if floor_value:
            self.fields["room"].queryset = (
                self.fields["room"].queryset.filter(
                    floor=floor_value
                )
            )

        if self.is_bound:
            selected_building = building_id
            selected_room = self.data.get("room")
            selected_floor = floor_value

        elif self.instance.pk:
            selected_building = self.instance.building_id
            selected_room = self.instance.room_id
            selected_floor = (
                self.instance.room.floor
                if self.instance.room
                else None
            )

            if selected_building:
                self.fields["room"].queryset = (
                    self.fields["room"].queryset.filter(
                        building_id=selected_building
                    )
                )

        else:
            selected_building = None
            selected_room = None
            selected_floor = None

        floors = (
            Room.objects.filter(
                building_id=selected_building
            )
            .values_list("floor", flat=True)
            .distinct()
            .order_by("floor")
            if selected_building
            else []
        )

        self.fields["floor"].choices = [
            ("", "Select Floor")
        ] + [
            (
                str(floor),
                f"{floor}{'st' if floor == 1 else 'nd' if floor == 2 else 'rd' if floor == 3 else 'th'} Floor",
            )
            for floor in floors
        ]

        if selected_floor:
            self.fields["floor"].initial = str(selected_floor)

        if selected_room:
            self.fields["room"].initial = selected_room

        if selected_building:
            self.fields["building"].initial = selected_building

    def clean(self):
        cleaned_data = super().clean()

        department = cleaned_data.get("department")
        building = cleaned_data.get("building")
        room = cleaned_data.get("room")
        floor = cleaned_data.get("floor")

        if building and department and building.department_id != department.id:
            self.add_error(
                "building",
                "The selected building does not belong to the selected department."
            )

        if room and building and room.building_id != building.id:
            self.add_error(
                "room",
                "The selected room does not belong to the selected building."
            )

        if room and floor and str(room.floor) != str(floor):
            self.add_error(
                "room",
                "The selected room does not belong to the selected floor."
            )

        return cleaned_data


class AppointmentRescheduleForm(forms.ModelForm):
    reason = forms.CharField(
        label="Reason for Rescheduling",
        required=True,
        max_length=500,
        widget=forms.Textarea(attrs={
            "class": "form-textarea",
            "rows": 4,
            "placeholder": "Enter the reason for rescheduling this appointment...",
            "maxlength": "500",
        }),
    )

    class Meta:
        model = Appointment

        fields = [
            "scheduled_date",
            "scheduled_time",
            "staff_notes",
        ]

        labels = {
            "scheduled_date": "New Appointment Date",
            "scheduled_time": "New Appointment Time",
            "staff_notes": "Clinic Staff Notes",
        }

        widgets = {
            "scheduled_date": forms.DateInput(attrs={
                "type": "date",
            }),
            "scheduled_time": forms.TimeInput(attrs={
                "type": "time",
            }),
            "staff_notes": forms.Textarea(attrs={
                "rows": 4,
                "placeholder": "Enter any instructions or notes for the student...",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.pk:
            self.fields["reason"].initial = (
                self.instance.staff_notes or ""
            )

    def clean_scheduled_date(self):
        date = self.cleaned_data["scheduled_date"]

        if date < timezone.localdate():
            raise forms.ValidationError(
                "The new appointment date cannot be in the past."
            )

        return date

    def clean_reason(self):
        reason = self.cleaned_data["reason"].strip()

        if not reason:
            raise forms.ValidationError(
                "Please provide a reason for rescheduling."
            )

        return reason


class HealthRecordForm(forms.ModelForm):
    class Meta:
        model = HealthRecord

        fields = [
            "symptoms",
            "treatment",
            "notes",
        ]

        labels = {
            "symptoms": "Symptoms",
            "treatment": "Treatment",
            "notes": "Additional Notes",
        }

        widgets = {
            "symptoms": forms.Textarea(attrs={
                "rows": 3,
                "placeholder": "Enter the student symptoms...",
            }),
            "treatment": forms.Textarea(attrs={
                "rows": 3,
                "placeholder": "Enter the treatment or medication...",
            }),
            "notes": forms.Textarea(attrs={
                "rows": 2,
                "placeholder": "Enter additional notes...",
            }),
        }


class SickNoteForm(forms.ModelForm):
    class Meta:
        model = SickNote

        fields = [
            "days_recommended",
            "notes",
        ]

        labels = {
            "days_recommended": "Recommended Rest (Days)",
            "notes": "Additional Notes",
        }

        widgets = {
            "days_recommended": forms.NumberInput(attrs={
                "min": 1,
                "placeholder": "Enter recommended rest days",
            }),
            "notes": forms.Textarea(attrs={
                "rows": 3,
                "placeholder": "Additional notes (optional)...",
            }),
        }




class AuthorizedUserForm(forms.ModelForm):
    STAFF_POSITION_CHOICES = User.STAFF_POSITION_CHOICES

    DEPARTMENT_CHOICES = [
        ("", "Select Department"),
        ("DIT", "DIT"),
        ("DBM", "DBM"),
        ("DGTT", "DGTT"),
        ("CCJE", "CCJE"),
        ("DCS", "DCS"),
    ]

    role = forms.ChoiceField(
        label="Account Type",
        choices=[
            ("", "Select Account Type"),
            ("teacher", "Teacher"),
            ("staff", "Clinic Staff"),
        ],
        required=True,
        widget=forms.Select(),
    )

    id_number = forms.CharField(
        label="Teacher ID / Employee Number",
        required=False,
        max_length=50,
        widget=forms.TextInput(attrs={
            "placeholder": "Enter identification number",
            "autocomplete": "off",
        }),
    )

    department = forms.ChoiceField(
        label="Department",
        choices=DEPARTMENT_CHOICES,
        required=False,
        widget=forms.Select(),
    )

    staff_position = forms.ChoiceField(
        label="Staff Position",
        choices=[("", "Select Staff Position")] + list(STAFF_POSITION_CHOICES),
        required=False,
        widget=forms.Select(),
    )

    sex = forms.ChoiceField(
        label="Gender",
        choices=[
            ("", "Select Gender"),
            ("Male", "Male"),
            ("Female", "Female"),
        ],
        required=True,
        widget=forms.Select(),
    )

    contact_number = forms.CharField(
        label="Contact Number",
        required=False,
        max_length=20,
        widget=forms.TextInput(attrs={
            "placeholder": "Enter contact number",
            "autocomplete": "tel",
        }),
    )

    password1 = forms.CharField(
        label="Password",
        required=True,
        widget=forms.PasswordInput(attrs={
            "placeholder": "Create a password",
            "autocomplete": "new-password",
            "class": "password-input",
        }),
    )

    password2 = forms.CharField(
        label="Confirm Password",
        required=True,
        widget=forms.PasswordInput(attrs={
            "placeholder": "Confirm your password",
            "autocomplete": "new-password",
            "class": "password-input",
        }),
    )

    class Meta:
        model = User
        fields = [
            "first_name",
            "middle_name",
            "last_name",
            "role",
            "id_number",
            "department",
            "staff_position",
            "sex",
            "contact_number",
            "email",
            "username",
        ]

        labels = {
            "first_name": "First Name",
            "middle_name": "Middle Name",
            "last_name": "Last Name",
            "contact_number": "Contact Number",
            "email": "Email Address",
            "username": "Username",
        }

        widgets = {
            "first_name": forms.TextInput(attrs={
                "placeholder": "Enter first name",
                "autocomplete": "given-name",
            }),
            "middle_name": forms.TextInput(attrs={
                "placeholder": "Enter middle name",
                "autocomplete": "additional-name",
            }),
            "last_name": forms.TextInput(attrs={
                "placeholder": "Enter last name",
                "autocomplete": "family-name",
            }),
            "contact_number": forms.TextInput(attrs={
                "placeholder": "Enter contact number",
                "autocomplete": "tel",
            }),
            "email": forms.EmailInput(attrs={
                "placeholder": "Enter email address",
                "autocomplete": "email",
            }),
            "username": forms.TextInput(attrs={
                "placeholder": "Create a username",
                "autocomplete": "username",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["first_name"].required = True
        self.fields["middle_name"].required = False
        self.fields["last_name"].required = True

        selected_role = (
            self.data.get(self.add_prefix("role"))
            or self.initial.get("role")
            or ""
        )

        if selected_role == "teacher":
            self.fields["id_number"].label = "Teacher ID"
            self.fields["id_number"].widget.attrs["placeholder"] = "Enter Teacher ID"

        elif selected_role == "staff":
            self.fields["id_number"].label = "Employee Number"
            self.fields["id_number"].widget.attrs["placeholder"] = "Enter Employee Number"

    def clean_middle_name(self):
        return (self.cleaned_data.get("middle_name") or "").strip()

    def clean_contact_number(self):
        return (self.cleaned_data.get("contact_number") or "").strip()

    def clean_role(self):
        role = (self.cleaned_data.get("role") or "").strip().lower()

        if role not in ("teacher", "staff"):
            raise forms.ValidationError(
                "Please select whether the account is for a Teacher or Clinic Staff."
            )

        return role

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()

        if not email:
            raise forms.ValidationError(
                "Email address is required."
            )

        duplicates = User.objects.annotate(
            normalized=Lower(Trim("email"))
        ).filter(
            normalized=email
        )

        if self.instance.pk:
            duplicates = duplicates.exclude(pk=self.instance.pk)

        if duplicates.exists():
            raise forms.ValidationError(
                "An account with this email address already exists."
            )

        return email

    def clean_id_number(self):
        id_number = (self.cleaned_data.get("id_number") or "").strip()

        if not id_number:
            return id_number

        duplicates = User.objects.annotate(
            normalized=Lower(Trim("id_number"))
        ).filter(
            normalized=id_number.lower()
        )

        if self.instance.pk:
            duplicates = duplicates.exclude(pk=self.instance.pk)

        if duplicates.exists():
            raise forms.ValidationError(
                "This identification number is already registered."
            )

        return id_number

    def clean_password1(self):
        password = self.cleaned_data.get("password1")

        if password:
            validate_password(password)

        return password

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")

        if password1 and password2 and password1 != password2:
            raise forms.ValidationError(
                "Passwords do not match."
            )

        return password2

    def clean(self):
        cleaned_data = super().clean()

        role = cleaned_data.get("role")
        id_number = cleaned_data.get("id_number")
        department = cleaned_data.get("department")
        staff_position = cleaned_data.get("staff_position")

        if role in ("teacher", "staff") and not id_number:
            self.add_error(
                "id_number",
                "Identification number is required."
            )

        if role == "teacher":
            if not department:
                self.add_error(
                    "department",
                    "Please select a department for the teacher."
                )

            cleaned_data["staff_position"] = None

        elif role == "staff":
            if not staff_position:
                self.add_error(
                    "staff_position",
                    "Please select a staff position."
                )

            cleaned_data["department"] = None

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)

        role = self.cleaned_data["role"]

        user.role = role
        user.middle_name = self.cleaned_data.get("middle_name") or None
        user.id_number = self.cleaned_data["id_number"]
        user.contact_number = self.cleaned_data.get("contact_number") or None
        user.set_password(self.cleaned_data["password1"])

        user.department = (
            self.cleaned_data.get("department")
            if role == "teacher"
            else None
        )

        user.staff_position = (
            self.cleaned_data.get("staff_position")
            if role == "staff"
            else None
        )

        user.verification_status = "verified"
        user.year_block = None
        user.block = None

        if commit:
            user.save()
            self.save_m2m()

        return user




class StyledModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                continue

            field.widget.attrs.setdefault("class", "form-field")


class DepartmentForm(StyledModelForm):
    class Meta:
        model = Department
        fields = ["name", "code", "is_active"]

        labels = {
            "name": "Department Name",
            "code": "Department Code",
            "is_active": "Active",
        }

        widgets = {
            "name": forms.TextInput(attrs={
                "placeholder": "e.g. Department of Computer Science",
            }),
            "code": forms.TextInput(attrs={
                "placeholder": "e.g. DCS",
            }),
            "is_active": forms.CheckboxInput(),
        }

    def clean_name(self):
        value = self.cleaned_data["name"].strip()

        if not value:
            raise forms.ValidationError(
                "Please enter the department name."
            )

        return value

    def clean_code(self):
        value = self.cleaned_data["code"].strip().upper()

        if not value:
            raise forms.ValidationError(
                "Please enter the department code."
            )

        return value


class BuildingForm(StyledModelForm):
    class Meta:
        model = Building
        fields = ["department", "name"]

        labels = {
            "department": "Department",
            "name": "Building Name",
        }

        widgets = {
            "department": forms.Select(),
            "name": forms.TextInput(attrs={
                "placeholder": "e.g. Technology Building",
            }),
        }

    def clean_name(self):
        value = self.cleaned_data["name"].strip()

        if not value:
            raise forms.ValidationError(
                "Please enter the building name."
            )

        return value


class RoomForm(StyledModelForm):
    class Meta:
        model = Room
        fields = ["building", "floor", "room_number", "room_name"]

        labels = {
            "building": "Building",
            "floor": "Floor",
            "room_number": "Room Number",
            "room_name": "Room Name",
        }

        widgets = {
            "building": forms.Select(),
            "floor": forms.NumberInput(attrs={
                "min": 1,
            }),
            "room_number": forms.TextInput(attrs={
                "placeholder": "e.g. 101",
            }),
            "room_name": forms.TextInput(attrs={
                "placeholder": "Optional room name",
            }),
        }

    def clean_floor(self):
        value = self.cleaned_data["floor"]

        if value < 1:
            raise forms.ValidationError(
                "Floor must be at least 1."
            )

        return value

    def clean_room_number(self):
        value = self.cleaned_data["room_number"].strip()
        building = self.cleaned_data.get("building")

        if not value:
            raise forms.ValidationError(
                "Please enter the room number."
            )

        if building and Room.objects.filter(
            building=building,
            room_number=value
        ).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(
                "This room number already exists in the selected building."
            )

        return value


class CourseForm(StyledModelForm):
    class Meta:
        model = Course
        fields = ["department", "code", "name"]

        labels = {
            "department": "Department",
            "code": "Course Code",
            "name": "Course Name",
        }

        widgets = {
            "code": forms.TextInput(attrs={
                "placeholder": "e.g. BSCS",
            }),
            "name": forms.TextInput(attrs={
                "placeholder": "e.g. Bachelor of Science in Computer Science",
            }),
        }

    def clean_code(self):
        value = self.cleaned_data["code"].strip()

        if not value:
            raise forms.ValidationError(
                "Please enter the course code."
            )

        return value

    def clean_name(self):
        value = self.cleaned_data["name"].strip()

        if not value:
            raise forms.ValidationError(
                "Please enter the course name."
            )

        return value
