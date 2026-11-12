"""
Ersetzt die alten member-<user_id>-Slugs durch sprechende (E2E F6).

Bis hierhin ergab slugify() für kyrillische Namen einen leeren String, und der
Fallback member-<user_id> legte die fortlaufende User-ID offen. Angefasst
werden nur Slugs, die exakt diesem Fallback entsprechen – also member-<Ziffern>
mit genau der eigenen user_id. Ein selbst gewählter Slug wie member-7 bei
user_id 12 bleibt stehen.

Gelöschte Konten (deleted-<pk>@deleted.local) bekommen deleted-<user_id> wie
in MemberProfile.anonymize() statt eines Slugs aus dem Platzhalternamen.
anonymize() setzt das seit jeher selbst; der Zweig ist nur Absicherung.

Die Slug-Logik kommt aus apps.profiles.slugs – einem Modul ohne
Modellimport, wie 0004 es mit apps.profiles.telegram hält.
"""

import logging
import re

from django.db import migrations

logger = logging.getLogger(__name__)

# Konvention aus AccountDeleteViewSet: deleted-<pk>@deleted.local. Als Literal,
# damit die Migration auch nach einer späteren Änderung dasselbe tut.
DELETED_EMAIL_SUFFIX = "@deleted.local"
_PK_FALLBACK_SLUG = re.compile(r"member-(\d+)")


def _is_pk_fallback(slug: str, user_id: int) -> bool:
    match = _PK_FALLBACK_SLUG.fullmatch(slug)
    return bool(match) and int(match.group(1)) == user_id


def regenerate_pk_fallback_slugs(apps, schema_editor):
    from apps.profiles.slugs import slug_base, unique_slug

    MemberProfile = apps.get_model("profiles", "MemberProfile")

    candidates = [
        profile
        for profile in MemberProfile.objects.filter(slug__startswith="member-")
        .select_related("user")
        .only(
            "id",
            "slug",
            "user__id",
            "user__email",
            "user__first_name",
            "user__last_name",
        )
        .iterator()
        if _is_pk_fallback(profile.slug, profile.user_id)
    ]
    if not candidates:
        return

    # Einmal alle Slugs laden statt pro Kandidat zu fragen; neu vergebene
    # kommen dazu, damit zwei gleichnamige Mitglieder nicht denselben Slug
    # erhalten. Die alten member-<id>-Slugs bleiben drin – sie sind bis zum
    # bulk_update noch belegt.
    taken = set(MemberProfile.objects.values_list("slug", flat=True))
    for profile in candidates:
        if profile.user.email.endswith(DELETED_EMAIL_SUFFIX):
            # Auch hier gegen taken: deleted-<id> kann von Hand vergeben sein.
            base = f"deleted-{profile.user_id}"
        else:
            base = slug_base(f"{profile.user.first_name}-{profile.user.last_name}")
        profile.slug = unique_slug(base, taken.__contains__)
        taken.add(profile.slug)

    MemberProfile.objects.bulk_update(candidates, ["slug"])
    logger.info("Profil-Slugs neu erzeugt: %s", len(candidates))


class Migration(migrations.Migration):
    dependencies = [
        ("profiles", "0008_seed_community_profile_tags"),
    ]

    operations = [
        # Reverse = noop: Die alten Slugs legten die User-ID offen, ein
        # Zurückrollen soll sie nicht wiederherstellen. Die neuen Slugs sind
        # auch mit dem älteren Code gültig.
        migrations.RunPython(regenerate_pk_fallback_slugs, migrations.RunPython.noop),
    ]
