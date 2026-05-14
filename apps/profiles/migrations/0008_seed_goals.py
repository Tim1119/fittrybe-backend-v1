# Gutted: seeding moved to python manage.py seed_app_data

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("profiles", "0007_goal_remove_gymprofile_wizard_completed_and_more"),
    ]

    operations = [
        migrations.RunPython(
            migrations.RunPython.noop,
            migrations.RunPython.noop,
        ),
    ]
