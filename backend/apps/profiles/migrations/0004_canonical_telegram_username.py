"""Bringt telegram_username auf die kanonische Form und verkürzt das Feld.

Reihenfolge ist wichtig: erst die Bestandsdaten bereinigen, dann max_length
verkleinern. Andersherum blieben Zeilen mit rohen URLs stehen und würden beim
nächsten full_clean() brechen.
"""

import logging

from django.db import migrations, models

logger = logging.getLogger(__name__)


def canonicalize_usernames(apps, schema_editor):
    from apps.profiles.telegram import normalize_telegram_username

    MemberProfile = apps.get_model("profiles", "MemberProfile")

    updated = []
    cleared = []
    queryset = MemberProfile.objects.exclude(telegram_username="").only(
        "id", "user_id", "telegram_username"
    )
    for profile in queryset.iterator():
        canonical = normalize_telegram_username(profile.telegram_username) or ""
        if canonical == profile.telegram_username:
            continue
        if not canonical:
            cleared.append((profile.user_id, profile.telegram_username))
        profile.telegram_username = canonical
        updated.append(profile)

    if updated:
        MemberProfile.objects.bulk_update(updated, ["telegram_username"])

    for user_id, original in cleared:
        # Bewusst laut: diese Mitglieder müssen ihren Handle neu eintragen.
        logger.warning(
            "telegram_username für user=%s nicht verwertbar und geleert: %r",
            user_id,
            original,
        )


def noop(apps, schema_editor):
    """Rückwärts ist nichts zu tun – die kanonische Form bleibt gültig."""


class Migration(migrations.Migration):

    dependencies = [
        ("profiles", "0003_alter_memberprofile_avatar_and_more"),
    ]

    operations = [
        migrations.RunPython(canonicalize_usernames, noop),
        migrations.AlterField(
            model_name="memberprofile",
            name="telegram_username",
            field=models.CharField(blank=True, default="", max_length=32),
        ),
    ]
