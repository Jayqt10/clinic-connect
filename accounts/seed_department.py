from accounts.models import Department

departments = [
    ("DCS", "Department of Computer Science"),
    ("DIT", "Department of Industrial Technology"),
    ("DBM", "Department of Business Management"),
    ("DGTT", "Department of General Teacher Training"),
    ("CCJE", "College of Criminal Justice Education"),
]  

for code, name in departments:
    department = (
        Department.objects.filter(name__iexact=name).first()
        or Department.objects.filter(code__iexact=code).first()
    )

    if department is None:
        department = Department(name=name)

    department.name = name
    department.code = code
    department.is_active = True
    department.save()

    print(department.pk, department.code, department.name)

print("Total departments:", Department.objects.count())