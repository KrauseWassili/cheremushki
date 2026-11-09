from django.core.management.base import BaseCommand

from apps.profiles.models import ProfileTag
from apps.profiles.tag_vocabulary import (
    ALL_PROFILE_TAGS,
    find_name_collisions,
    seed_profile_tags,
)


class Command(BaseCommand):
    help = (
        "Legt das Vokabular für Profil Tags an (Start- und Community-Liste). "
        "Bestehende Tags bleiben unverändert."
    )

    def handle(self, *args, **options):
        collisions = find_name_collisions(ALL_PROFILE_TAGS)
        self._report_collisions(collisions)

        created, skipped = seed_profile_tags(ProfileTag, ALL_PROFILE_TAGS)
        unique_count = len(ALL_PROFILE_TAGS) - sum(
            len(labels) - 1 for labels in collisions.values()
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Profil-Tags: {created} angelegt, {skipped} bereits vorhanden "
                f"({unique_count} im Vokabular)."
            )
        )

    def _report_collisions(self, collisions: dict[str, list[str]]) -> None:
        # Gleicher Name mit gleichem Label ist eine harmlose Überschneidung der
        # Listen. Unterschiedliche Labels dagegen heißen: Eine Schreibweise
        # wird nie angelegt – das muss jemand im Vokabular auflösen.
        conflicting = {
            name: labels for name, labels in collisions.items() if len(set(labels)) > 1
        }
        for name, labels in sorted(conflicting.items()):
            self.stdout.write(
                self.style.WARNING(
                    f"Namenskollision {name!r}: {', '.join(labels)} – "
                    f"angelegt wird nur {labels[0]!r}."
                )
            )
        identical = len(collisions) - len(conflicting)
        if identical:
            self.stdout.write(
                f"{identical} Tags stehen in mehreren Listen (gleiches Label), "
                "werden einmal angelegt."
            )
