from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0022_remove_sicknote_diagnosis'),
    ]

    operations = [
        migrations.RenameField(
            model_name='user',
            old_name='enrollment_status',
            new_name='verification_status',
        ),
        migrations.RenameField(
            model_name='user',
            old_name='enrollment_evidence',
            new_name='verification_evidence',
        ),
        migrations.AlterField(
            model_name='user',
            name='verification_evidence',
            field=models.FileField(
                blank=True,
                null=True,
                upload_to='student_verification_evidence/',
            ),
        ),
        migrations.AlterField(
            model_name='referral',
            name='student_name',
            field=models.CharField(blank=True, max_length=255),
        ),
    ]
