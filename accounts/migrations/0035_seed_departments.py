from django.contrib.auth.hashers import make_password
from django.db import migrations


def seed_departments_and_admin(apps, schema_editor):
    Department = apps.get_model("accounts", "Department")
    User = apps.get_model("accounts", "User")

    departments = [
        ("DCS", "Department of Computer Studies"),
        ("DIT", "Department of Industrial Technology"),
        ("DBM", "Department of Business Management"),
        ("DGTT", "Department of General Teacher Training"),
        ("CCJE", "College of Criminal Justice Education"),
    ]
    for code, name in departments:
        Department.objects.get_or_create(
            code=code,
            defaults={"name": name, "is_active": True},
        )

    admin_user, created = User.objects.get_or_create(
        username="clinicadmin",
        defaults={
            "first_name": "Clinic",
            "last_name": "Administrator",
            "email": "clinicadmin@nemsu.edu.ph",
            "role": "staff",
            "staff_position": "admin",
            "is_staff": True,
            "is_superuser": True,
            "is_active": True,
            "password": make_password("Admin@12345"),
        },
    )
    if not created:
        admin_user.role = "staff"
        admin_user.staff_position = "admin"
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.is_active = True
        admin_user.save()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0033_medicine_icon"),
    ]

    operations = [
        migrations.RunPython(seed_departments_and_admin, migrations.RunPython.noop),
    ]