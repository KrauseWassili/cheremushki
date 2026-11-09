"""Erweitert das Tag-Vokabular um COMMUNITY_PROFILE_TAGS.

Als Datenmigration und nicht nur über `manage.py seed_profile_tags`, weil der
Deploy den Command nicht ausführt – bestehende Datenbanken bekämen die neuen
Tags sonst nie. Rein additiv: Alte Tags werden weder geändert noch
deaktiviert, Profile können sie bereits tragen.

Importiert die Liste und das Seeding aus dem App-Code, aus demselben Grund
wie 0006 (reine Daten bzw. reine Funktion ohne Modellbezug). Die Liste ist
deshalb append-only, siehe tag_vocabulary.py.
"""

import logging

from django.db import migrations

logger = logging.getLogger(__name__)


def seed_community_tags(apps, schema_editor):
    from apps.profiles.tag_vocabulary import COMMUNITY_PROFILE_TAGS, seed_profile_tags

    ProfileTag = apps.get_model("profiles", "ProfileTag")
    created, skipped = seed_profile_tags(ProfileTag, COMMUNITY_PROFILE_TAGS)
    logger.info(
        "Community-Tag-Vokabular geseedet: %s neu, %s bereits vorhanden",
        created,
        skipped,
    )


def remove_unused_community_tags(apps, schema_editor):
    """
    Rückwärts: nur Tags entfernen, die kein Profil trägt.

    Ein Löschen zugeordneter Tags würde per CASCADE die Zuordnungen der
    Mitglieder mitnehmen – das ist bei einem Rollback schlimmer als ein paar
    übrig gebliebene Vokabular-Einträge. Namen aus dem Startvokabular bleiben
    immer stehen, die gehören 0006.

    Achtung: Die Migration merkt sich nicht, welche Tags sie selbst angelegt
    hat. Ein gleichnamiger, unbenutzter Tag, den ein Admin schon vor 0008
    angelegt hatte (seed_profile_tags hat ihn dann nur übersprungen), wird
    beim Rückwärtslauf ebenfalls gelöscht.
    """
    from apps.profiles.hashtags import parse_hashtag
    from apps.profiles.tag_vocabulary import (
        COMMUNITY_PROFILE_TAGS,
        INITIAL_PROFILE_TAGS,
    )

    ProfileTag = apps.get_model("profiles", "ProfileTag")
    initial_names = {parse_hashtag(raw_name) for raw_name, _ in INITIAL_PROFILE_TAGS}
    community_only_names = {
        parse_hashtag(raw_name) for raw_name, _ in COMMUNITY_PROFILE_TAGS
    } - initial_names

    removable = ProfileTag.objects.filter(
        name__in=community_only_names, tagged_profiles__isnull=True
    )
    deleted, _ = removable.delete()
    kept = ProfileTag.objects.filter(name__in=community_only_names).count()
    logger.info(
        "Community-Tags zurückgerollt: %s entfernt, %s bleiben (in Benutzung)",
        deleted,
        kept,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("profiles", "0007_remove_memberprofile_legacy_tags"),
    ]

    operations = [
        migrations.RunPython(seed_community_tags, remove_unused_community_tags),
    ]
