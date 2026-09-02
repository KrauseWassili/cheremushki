"""Schritt 3 von 3: Die alte JSONField-Spalte fällt weg.

Bewusst eine eigene Migration: Bis hierher lässt sich der Umstieg zurückrollen,
ohne dass Daten fehlen. Ab hier ist der Bestand nur noch in TaggedProfile.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("profiles", "0006_seed_and_migrate_profile_tags"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="memberprofile",
            name="legacy_tags",
        ),
    ]
