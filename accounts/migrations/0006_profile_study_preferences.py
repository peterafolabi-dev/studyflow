from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('accounts', '0005_userpresence')]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='weekly_study_goal_hours',
            field=models.PositiveSmallIntegerField(default=8),
        ),
        migrations.AddField(
            model_name='profile',
            name='preferred_study_time',
            field=models.CharField(
                choices=[('morning', 'Morning'), ('afternoon', 'Afternoon'), ('evening', 'Evening'), ('flexible', 'Flexible')],
                default='flexible', max_length=12,
            ),
        ),
    ]
