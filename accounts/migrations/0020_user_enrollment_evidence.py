
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0019_user_enrollment_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='enrollment_evidence',
            field=models.FileField(
                blank=True,
                null=True,
                upload_to='student_enrollment_evidence/',
            ),
        ),
    ]
