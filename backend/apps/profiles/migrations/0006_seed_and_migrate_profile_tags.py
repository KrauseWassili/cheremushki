"""Schritt 2 von 3: Vokabular seeden und Bestandstags übernehmen.

Die Kanonisierung und das Startvokabular werden aus dem App-Code importiert
statt hier kopiert. Das ist bei Datenmigrationen sonst heikel, hier aber
vertretbar: `parse_hashtag` und `INITIAL_PROFILE_TAGS` haben keinen Bezug zu
Modellen oder Schema, sie sind reine Daten bzw. eine reine Funktion. Eine
Kopie würde bedeuten, dass eine spätere Korrektur der Kanonisierung Bestand
und Neueingaben auseinanderlaufen lässt.

Der Bestand in `legacy_tags` ist freier Text. Werte, die sich nicht
kanonisieren lassen (nur Emojis, nur Ziffern), werden nicht stillschweigend
verworfen, sondern geloggt – ein Mitglied soll seinen Tag im Zweifel
wiederfinden können.
"""

import logging

from django.db import migrations

logger = logging.getLogger(__name__)


def seed_and_migrate_tags(apps, schema_editor):
    from apps.profiles.hashtags import InvalidHashtag, parse_hashtag
    from apps.profiles.tag_vocabulary import seed_profile_tags

    ProfileTag = apps.get_model("profiles", "ProfileTag")
    TaggedProfile = apps.get_model("profiles", "TaggedProfile")
    MemberProfile = apps.get_model("profiles", "MemberProfile")

    created, skipped = seed_profile_tags(ProfileTag)
    logger.info(
        "Profil-Tag-Vokabular geseedet: %s neu, %s bereits vorhanden",
        created,
        skipped,
    )

    # Cache über den kanonischen Namen: Der Bestand enthält viele Wiederholungen
    # derselben Tags über alle Profile hinweg.
    tags_by_name: dict[str, object] = {
        tag.name: tag for tag in ProfileTag.objects.all()
    }

    assignments = []
    queryset = MemberProfile.objects.exclude(legacy_tags=[]).only(
        "id", "user_id", "legacy_tags"
    )
    for profile in queryset.iterator():
        seen: set[str] = set()
        for raw_value in profile.legacy_tags or []:
            try:
                name = parse_hashtag(str(raw_value))
            except InvalidHashtag as exc:
                logger.warning(
                    "legacy_tags: Wert %r von user=%s nicht übernehmbar (%s)",
                    raw_value,
                    profile.user_id,
                    exc,
                )
                continue
            if name in seen:
                continue
            seen.add(name)

            tag = tags_by_name.get(name)
            if tag is None:
                # Bestandstag außerhalb des Startvokabulars: Er wird ins
                # Vokabular übernommen, damit keine Zuordnung verloren geht.
                # Der Admin kann ihn danach zusammenführen oder deaktivieren.
                tag = ProfileTag.objects.create(
                    name=name, slug=name, label="", is_active=True
                )
                tags_by_name[name] = tag
                logger.info("legacy_tags: Tag %r ins Vokabular übernommen", name)

            assignments.append(
                TaggedProfile(tag_id=tag.pk, content_object_id=profile.pk)
            )

    if assignments:
        TaggedProfile.objects.bulk_create(assignments, ignore_conflicts=True)
    logger.info("legacy_tags: %s Zuordnungen übernommen", len(assignments))


def restore_legacy_tags(apps, schema_editor):
    """
    Rückwärts: Zuordnungen zurück nach `legacy_tags` schreiben.

    Nötig, weil 0007 die alte Spalte löscht: Wer die ganze Kette zurückrollt,
    bekommt von 0007 eine leere Spalte und würde ohne diesen Schritt ohne Tags
    dastehen. Zurück kommt die kanonische Form, nicht die ursprüngliche
    Schreibweise – die ist nach dem Umstieg nirgends mehr gespeichert.
    """
    TaggedProfile = apps.get_model("profiles", "TaggedProfile")
    MemberProfile = apps.get_model("profiles", "MemberProfile")

    names_by_profile: dict[int, list[str]] = {}
    rows = TaggedProfile.objects.values_list("content_object_id", "tag__name")
    for profile_id, name in rows.iterator():
        names_by_profile.setdefault(profile_id, []).append(name)

    profiles = MemberProfile.objects.filter(pk__in=names_by_profile).only(
        "id", "legacy_tags"
    )
    restored = []
    for profile in profiles:
        profile.legacy_tags = sorted(names_by_profile[profile.pk])
        restored.append(profile)
    if restored:
        MemberProfile.objects.bulk_update(restored, ["legacy_tags"])

    TaggedProfile.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("profiles", "0005_profile_tag_vocabulary"),
    ]

    operations = [
        migrations.RunPython(seed_and_migrate_tags, restore_legacy_tags),
    ]
