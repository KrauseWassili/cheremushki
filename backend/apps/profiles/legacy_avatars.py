"""
Einmaliges, idempotentes Aufräumen der Avatar-Altlasten.

Vor den Zufallsnamen hießen Avatare avatars/user-<id>.<ext> (plus Djangos
Kollisionsvarianten user-<id>_AbC123x.<ext>). Unter /media/ öffentlich
erreichbar, ließen sie sich per Durchzählen der User-ID abrufen, und sie
tragen noch die EXIF-Daten von vor der Bereinigung. Früher hat jeder Upload
und jede Kontolöschung das Verzeichnis nach solchen Dateien durchsucht – das
erledigt jetzt einmal pro Deploy cleanup_legacy_avatars (run_backend_prod.sh).
"""

import logging
import re
from dataclasses import dataclass, field

from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import Q

from .avatar_files import (
    AVATAR_DIR,
    AVATAR_ORIGINALS_DIR,
    InvalidAvatarImage,
    schedule_avatar_file_deletion,
    strip_image_metadata,
)
from .models import MemberProfile

logger = logging.getLogger(__name__)

# Verankert, damit nur das alte Schema passt und keine Zufallsnamen.
_LEGACY_FILE_NAME = re.compile(r"^user-\d+(?:_[A-Za-z0-9]+)?\.[A-Za-z0-9]+$")
_AVATAR_FIELDS = ("avatar", "avatar_original")


@dataclass
class LegacyAvatarCleanupReport:
    # (Profil-ID, Feld) mit Verweis auf eine nicht existierende Datei.
    cleared_fields: list[tuple[int, str]] = field(default_factory=list)
    # Profile, die durch das Leeren aus dem Verzeichnis gefallen sind.
    hidden_profile_ids: list[int] = field(default_factory=list)
    # Alter Name → neuer Name (im Dry-Run leer als Ziel).
    renamed_files: list[tuple[str, str]] = field(default_factory=list)
    # Referenzierte Altdateien, die Pillow nicht neu schreiben konnte.
    unreadable_files: list[str] = field(default_factory=list)
    deleted_files: list[str] = field(default_factory=list)


def is_legacy_avatar_path(name: str) -> bool:
    directory, _, file_name = name.rpartition("/")
    return directory in (AVATAR_DIR, AVATAR_ORIGINALS_DIR) and bool(
        _LEGACY_FILE_NAME.match(file_name)
    )


def cleanup_legacy_avatars(*, dry_run: bool) -> LegacyAvatarCleanupReport:
    """
    Reihenfolge ist wichtig: Erst tote Verweise leeren, dann referenzierte
    Altdateien umschreiben, zuletzt löschen, was danach niemand mehr
    referenziert. Andersherum würde eine noch referenzierte Datei gelöscht.
    """
    report = LegacyAvatarCleanupReport()
    _clear_missing_file_references(report, dry_run=dry_run)
    _rewrite_referenced_legacy_files(report, dry_run=dry_run)
    _delete_unreferenced_legacy_files(report, dry_run=dry_run)
    return report


def _clear_missing_file_references(
    report: LegacyAvatarCleanupReport, *, dry_run: bool
) -> None:
    """
    Leert avatar/avatar_original, wenn die Datei nicht (mehr) existiert.

    Bewusst ohne trigger_profile_side_effects: Ein geleerter Avatar macht das
    Profil höchstens unvollständig, nie vollständig – eine Einladung kann
    hier also nicht fällig werden, und Telegram-Aufrufe gehören nicht in
    einen Deploy-Schritt.
    """
    for profile_id in _profile_ids_with_avatar_files():
        with transaction.atomic():
            profile = (
                MemberProfile.objects.select_for_update(of=("self",))
                .select_related("user")
                .get(pk=profile_id)
            )
            missing = [
                name
                for name in _AVATAR_FIELDS
                if getattr(profile, name)
                and not default_storage.exists(getattr(profile, name).name)
            ]
            if not missing:
                continue
            report.cleared_fields.extend((profile.pk, name) for name in missing)
            logger.warning(
                "Profil %s verweist auf fehlende Avatar-Datei(en) %s – %s.",
                profile.pk,
                ", ".join(missing),
                "würde geleert" if dry_run else "wird geleert",
            )
            if dry_run:
                continue
            for name in missing:
                setattr(profile, name, None)
            profile.save(update_fields=missing)
            was_visible = profile.is_directory_visible
            profile.refresh_directory_visibility(save=True)
            if was_visible and not profile.is_directory_visible:
                report.hidden_profile_ids.append(profile.pk)
                logger.warning(
                    "Profil %s ist ohne Avatar unvollständig und nicht mehr im "
                    "Verzeichnis sichtbar.",
                    profile.pk,
                )


def _rewrite_referenced_legacy_files(
    report: LegacyAvatarCleanupReport, *, dry_run: bool
) -> None:
    """
    Schreibt referenzierte Altdateien ohne Metadaten unter Zufallsnamen neu.

    Die alte Datei wird erst nach dem Commit gelöscht (über die
    on_commit-Löschung des Profils), damit ein Rollback keinen Verweis ins
    Leere hinterlässt.
    """
    for profile_id in _profile_ids_with_avatar_files():
        with transaction.atomic():
            profile = MemberProfile.objects.select_for_update().get(pk=profile_id)
            changed: list[str] = []
            for name in _AVATAR_FIELDS:
                field_file = getattr(profile, name)
                if not field_file or not is_legacy_avatar_path(field_file.name):
                    continue
                old_name = field_file.name
                if dry_run:
                    # Fehlende Dateien hätte der echte Lauf vorher geleert.
                    if default_storage.exists(old_name):
                        report.renamed_files.append((old_name, ""))
                    continue
                try:
                    with default_storage.open(old_name, "rb") as handle:
                        cleaned = strip_image_metadata(handle)
                except InvalidAvatarImage as exc:
                    report.unreadable_files.append(old_name)
                    logger.error(
                        "Avatar-Altdatei %s (Profil %s) nicht lesbar, bleibt "
                        "unverändert: %s",
                        old_name,
                        profile.pk,
                        exc,
                    )
                    continue
                field_file.save(cleaned.name, cleaned, save=False)
                changed.append(name)
                report.renamed_files.append((old_name, field_file.name))
                schedule_avatar_file_deletion([old_name])
            if changed:
                profile.save(update_fields=changed)


def _delete_unreferenced_legacy_files(
    report: LegacyAvatarCleanupReport, *, dry_run: bool
) -> None:
    referenced = _referenced_file_names()
    # Umgeschriebene Altdateien sind hier schon per on_commit gelöscht und
    # tauchen in listdir nicht mehr auf; im Dry-Run sind sie noch
    # referenziert. In beiden Fällen landen sie nicht doppelt im Bericht.
    stale = sorted(_legacy_file_names() - referenced)
    for name in stale:
        if dry_run:
            report.deleted_files.append(name)
            continue
        try:
            default_storage.delete(name)
        except OSError as exc:
            logger.warning("Avatar-Altdatei %s nicht löschbar: %s", name, exc)
        else:
            report.deleted_files.append(name)


def _profile_ids_with_avatar_files() -> list[int]:
    # __gt="": weder NULL noch leerer String – beides heißt "kein Bild".
    return list(
        MemberProfile.objects.filter(Q(avatar__gt="") | Q(avatar_original__gt=""))
        .order_by("pk")
        .values_list("pk", flat=True)
    )


def _referenced_file_names() -> set[str]:
    names: set[str] = set()
    for avatar, original in MemberProfile.objects.values_list(
        "avatar", "avatar_original"
    ):
        names.update(name for name in (avatar, original) if name)
    return names


def _legacy_file_names() -> set[str]:
    names: set[str] = set()
    for directory in (AVATAR_DIR, AVATAR_ORIGINALS_DIR):
        try:
            _, files = default_storage.listdir(directory)
        except FileNotFoundError:
            continue
        names.update(
            f"{directory}/{name}" for name in files if _LEGACY_FILE_NAME.match(name)
        )
    return names
