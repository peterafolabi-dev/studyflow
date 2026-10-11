from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('planner', '0006_badge_studystreak_xplog_userbadge'),
    ]

    operations = [
        migrations.AddField(
            model_name='userbadge',
            name='celebration_seen',
            field=models.BooleanField(default=False),
        ),
    ]