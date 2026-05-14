# Gutted: seeding moved to python manage.py seed_app_data

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("badges", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            migrations.RunPython.noop,
            migrations.RunPython.noop,
        ),
    ]
