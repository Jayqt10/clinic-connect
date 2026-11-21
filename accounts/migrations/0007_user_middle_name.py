
from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [ 
        ('accounts', '0006_user_section_alter_referral_student_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='middle_name',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]
