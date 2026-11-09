from django.core.management.base import BaseCommand

from apps.profiles.legacy_avatars import cleanup_legacy_avatars


class Command(BaseCommand):
    help = (
        "Räumt Avatar-Altlasten auf: referenzierte user-<id>-Dateien werden "
        "ohne Metadaten unter Zufallsnamen neu geschrieben, nicht referenzierte "
        "gelöscht, Verweise auf fehlende Dateien geleert. Idempotent – läuft "
        "bei jedem Produktionsstart."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Nur anzeigen, was passieren würde – nichts schreiben oder löschen.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        report = cleanup_legacy_avatars(dry_run=dry_run)

        prefix = "[Dry-Run] " if dry_run else ""
        for profile_id, field_name in report.cleared_fields:
            self.stdout.write(
                f"{prefix}Profil {profile_id}: {field_name} zeigt auf fehlende "
                "Datei, geleert."
            )
        for old_name, new_name in report.renamed_files:
            target = new_name or "<Zufallsname>"
            self.stdout.write(f"{prefix}Umgeschrieben: {old_name} -> {target}")
        for name in report.deleted_files:
            self.stdout.write(f"{prefix}Gelöscht: {name}")
        for name in report.unreadable_files:
            self.stdout.write(
                self.style.ERROR(f"Nicht lesbar, unverändert gelassen: {name}")
            )
        if report.hidden_profile_ids:
            ids = ", ".join(str(pk) for pk in report.hidden_profile_ids)
            self.stdout.write(
                self.style.WARNING(
                    f"Nicht mehr im Verzeichnis sichtbar (Avatar fehlt): {ids}"
                )
            )
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}Avatar-Altlasten: {len(report.cleared_fields)} Verweise "
                f"geleert, {len(report.renamed_files)} Dateien umgeschrieben, "
                f"{len(report.deleted_files)} gelöscht, "
                f"{len(report.unreadable_files)} nicht lesbar."
            )
        )
