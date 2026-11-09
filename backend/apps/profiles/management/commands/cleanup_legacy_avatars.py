import logging

from django.core.management.base import BaseCommand, CommandError

from apps.profiles.legacy_avatars import (
    MAX_MISSING_REFERENCE_RATIO,
    LegacyAvatarCleanupAborted,
    cleanup_legacy_avatars,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Räumt Avatar-Altlasten auf: referenzierte user-<id>-Dateien werden "
        "ohne Metadaten unter Zufallsnamen neu geschrieben (nicht als Bild "
        "lesbare unverändert unter Zufallsnamen verschoben), nicht "
        "referenzierte gelöscht. Verweise auf fehlende Dateien werden nur "
        "gemeldet, geleert nur mit --clear-missing. Bricht ohne Änderungen ab, "
        "wenn Profile Avatare haben, das Avatar-Verzeichnis aber leer ist. "
        "Idempotent – läuft bei jedem Produktionsstart (ohne --clear-missing)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Nur anzeigen, was passieren würde – nichts schreiben oder löschen.",
        )
        parser.add_argument(
            "--clear-missing",
            action="store_true",
            help=(
                "Verweise auf fehlende Dateien leeren (Profil kann dadurch aus "
                "dem Verzeichnis fallen). Nur manuell, nie im Startskript."
            ),
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help=(
                "Mit --clear-missing auch leeren, wenn mehr als "
                f"{MAX_MISSING_REFERENCE_RATIO:.0%} der Verweise tot sind."
            ),
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        clear_missing = options["clear_missing"]
        try:
            report = cleanup_legacy_avatars(
                dry_run=dry_run, clear_missing=clear_missing, force=options["force"]
            )
        except LegacyAvatarCleanupAborted as exc:
            logger.error("Avatar-Cleanup abgebrochen: %s", exc)
            raise CommandError(str(exc)) from exc

        prefix = "[Dry-Run] " if dry_run else ""
        cleared = set(report.cleared_fields)
        for profile_id, field_name in report.missing_references:
            if (profile_id, field_name) in cleared:
                outcome = "geleert."
            elif clear_missing:
                outcome = "inzwischen ersetzt, nicht geleert."
            else:
                outcome = "nicht geleert (dafür --clear-missing)."
            self.stdout.write(
                f"{prefix}Profil {profile_id}: {field_name} zeigt auf fehlende "
                f"Datei, {outcome}"
            )
        for old_name, new_name in report.renamed_files:
            target = new_name or "<Zufallsname>"
            self.stdout.write(f"{prefix}Umgeschrieben: {old_name} -> {target}")
        for old_name, new_name in report.moved_files:
            self.stdout.write(
                self.style.WARNING(
                    f"Nicht lesbar, unverändert verschoben: {old_name} -> {new_name}"
                )
            )
        for name in report.deleted_files:
            self.stdout.write(f"{prefix}Gelöscht: {name}")
        for name in report.failed_files:
            self.stdout.write(self.style.ERROR(f"Fehler, unverändert: {name}"))
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
                f"{len(report.moved_files)} unverändert verschoben, "
                f"{len(report.deleted_files)} gelöscht, "
                f"{len(report.failed_files)} Fehler, "
                f"{len(report.missing_references)} tote Verweise gefunden."
            )
        )
