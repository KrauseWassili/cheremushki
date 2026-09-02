from django.core.management.base import BaseCommand

from apps.profiles.models import ProfileTag
from apps.profiles.tag_vocabulary import INITIAL_PROFILE_TAGS, seed_profile_tags


class Command(BaseCommand):
    help = "Legt das Startvokabular für Profil Tags an. Bestehende Tags bleiben unverändert."

    def handle(self, *args, **options):
        created, skipped = seed_profile_tags(ProfileTag)

        self.stdout.write(
            self.style.SUCCESS(
                f"Profil-Tags: {created} angelegt, {skipped} bereits vorhanden "
                f"({len(INITIAL_PROFILE_TAGS)} im Vokabular)."
            )
        )
