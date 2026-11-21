
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0018_alter_user_id_number'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='enrollment_status',
            field=models.CharField(
                blank=True,
                choices=[
                    ('pending', 'Pending Verification'),
                    ('verified', 'Verified'),
                    ('rejected', 'Rejected'),
                ],
                default='pending',
                max_length=20,
            ),
        ),
    ]
