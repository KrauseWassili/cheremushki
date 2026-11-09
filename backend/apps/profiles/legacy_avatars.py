"""
Idempotentes Aufräumen der Avatar-Altlasten.

Vor den Zufallsnamen hießen Avatare avatars/user-<id>.<ext> (plus Djangos
Kollisionsvarianten user-<id>_AbC123x.<ext>). Unter /media/ öffentlich
erreichbar, ließen sie sich per Durchzählen der User-ID abrufen, und sie
tragen noch die EXIF-Daten von vor der Bereinigung. Früher hat jeder Upload
und jede Kontolöschung das Verzeichnis nach solchen Dateien durchsucht – das
erledigt jetzt cleanup_legacy_avatars bei jedem Produktionsstart
(run_backend_prod.sh, dort nicht fatal).

Verweise auf fehlende Dateien werden nur mit clear_missing geleert: Fehlt
beim Start das Media-Volume (falsch gemountet, leer neu angelegt), sähen
sonst alle Avatare "tot" aus, und ein automatischer Lauf würde sie aus der
Datenbank tilgen. Dagegen zusätzlich zwei Riegel, siehe
_ensure_avatar_files_present und _ensure_plausible_missing_ratio.
"""

import io
import logging
import posixpath
from dataclasses import dataclass, field

from django.core.exceptions import SuspiciousFileOperation
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import Q

from .avatar_files import (
    AVATAR_DIR,
    AVATAR_ORIGINALS_DIR,
    IMAGE_DECODE_ERRORS,
    InvalidAvatarImage,
    is_legacy_avatar_file_name,
    is_legacy_avatar_path,
    schedule_avatar_file_deletion,
    strip_image_metadata,
)
from .models import MemberProfile

logger = logging.getLogger(__name__)

_AVATAR_FIELDS = ("avatar", "avatar_original")
# Ab diesem Anteil toter Verweise ist eher das Volume kaputt als der Bestand:
# Dann leert --clear-missing nur mit --force.
MAX_MISSING_REFERENCE_RATIO = 0.2
# Was Storage-Zugriffe auf einen einzelnen, womöglich kaputten Eintrag werfen
# können. SuspiciousFileOperation: ein Name in der DB, der aus MEDIA_ROOT
# herauszeigt – der Lauf geht mit dem nächsten Eintrag weiter.
_STORAGE_ERRORS = (OSError, SuspiciousFileOperation)
_UNPROCESSABLE_IMAGE_ERRORS = (InvalidAvatarImage, *IMAGE_DECODE_ERRORS)


class LegacyAvatarCleanupAborted(Exception):
    """
    Der Bestand sieht nicht plausibel aus – es wurde nichts verändert.
    """


@dataclass(frozen=True)
class _AvatarReference:
    profile_id: int
    field_name: str
    file_name: str


@dataclass
class LegacyAvatarCleanupReport:
    # (Profil-ID, Feld) mit Verweis auf eine nicht existierende Datei –
    # gefunden, unabhängig davon, ob geleert wurde.
    missing_references: list[tuple[int, str]] = field(default_factory=list)
    # Davon tatsächlich geleert (bzw. im Dry-Run: würden geleert).
    cleared_fields: list[tuple[int, str]] = field(default_factory=list)
    # Profile, die durch das Leeren aus dem Verzeichnis gefallen sind.
    hidden_profile_ids: list[int] = field(default_factory=list)
    # Ohne Metadaten neu geschrieben: alter → neuer Name (Dry-Run: Ziel leer).
    renamed_files: list[tuple[str, str]] = field(default_factory=list)
    # Für Pillow unverarbeitbar, Rohbytes unter Zufallsnamen verschoben.
    moved_files: list[tuple[str, str]] = field(default_factory=list)
    # Storage-Fehler: Datei bzw. Verweis blieb unverändert.
    failed_files: list[str] = field(default_factory=list)
    deleted_files: list[str] = field(default_factory=list)


def cleanup_legacy_avatars(
    *, dry_run: bool, clear_missing: bool = False, force: bool = False
) -> LegacyAvatarCleanupReport:
    """
    Reihenfolge ist wichtig: Erst prüfen (ohne Schreibzugriff), dann tote
    Verweise leeren, dann referenzierte Altdateien umschreiben, zuletzt
    löschen, was danach niemand mehr referenziert. Andersherum würde eine
    noch referenzierte Datei gelöscht.

    Wirft LegacyAvatarCleanupAborted, bevor irgendetwas geändert wurde.
    """
    report = LegacyAvatarCleanupReport()
    references = _avatar_references()
    _ensure_avatar_files_present(references)
    missing = _find_missing_references(references, report)
    if clear_missing:
        _ensure_plausible_missing_ratio(
            missing_count=len(missing), total=len(references), force=force
        )
        _clear_missing_file_references(missing, report, dry_run=dry_run)
    missing_names = {reference.file_name for reference in missing}
    _rewrite_referenced_legacy_files(report, missing_names, dry_run=dry_run)
    _delete_unreferenced_legacy_files(report, dry_run=dry_run)
    return report


def _ensure_avatar_files_present(references: list[_AvatarReference]) -> None:
    """
    Bricht ab, wenn Profile Avatare haben, das Verzeichnis aber leer ist.

    Das ist kein Bestand, den man aufräumt, sondern ein fehlendes oder frisch
    leer angelegtes Media-Volume – jeder weitere Schritt würde auf dieser
    Grundlage falsch entscheiden. Gilt auch mit --force.
    """
    if not references or _has_any_avatar_file():
        return
    raise LegacyAvatarCleanupAborted(
        f"{len(references)} Avatar-Verweise in der Datenbank, aber unter "
        f"MEDIA_ROOT/{AVATAR_DIR} liegt keine Datei – ist das Media-Volume "
        "gemountet? Abbruch ohne Änderungen."
    )


def _ensure_plausible_missing_ratio(
    *, missing_count: int, total: int, force: bool
) -> None:
    if force or not total or missing_count / total <= MAX_MISSING_REFERENCE_RATIO:
        return
    raise LegacyAvatarCleanupAborted(
        f"{missing_count} von {total} Avatar-Verweisen zeigen auf fehlende "
        f"Dateien (mehr als {MAX_MISSING_REFERENCE_RATIO:.0%}) – eher ein "
        "Problem mit dem Media-Volume als mit dem Bestand. Abbruch ohne "
        "Änderungen; bewusst leeren mit --clear-missing --force."
    )


def _find_missing_references(
    references: list[_AvatarReference], report: LegacyAvatarCleanupReport
) -> list[_AvatarReference]:
    missing: list[_AvatarReference] = []
    for reference in references:
        try:
            exists = default_storage.exists(reference.file_name)
        except _STORAGE_ERRORS as exc:
            report.failed_files.append(reference.file_name)
            logger.error(
                "Avatar-Verweis %s (Profil %s) nicht prüfbar: %s",
                reference.file_name,
                reference.profile_id,
                exc,
            )
            continue
        if not exists:
            missing.append(reference)
            report.missing_references.append(
                (reference.profile_id, reference.field_name)
            )
    return missing


def _clear_missing_file_references(
    missing: list[_AvatarReference],
    report: LegacyAvatarCleanupReport,
    *,
    dry_run: bool,
) -> None:
    """
    Leert avatar/avatar_original, wenn die Datei nicht (mehr) existiert.

    Bewusst ohne trigger_profile_side_effects: Ein geleerter Avatar macht das
    Profil höchstens unvollständig, nie vollständig – eine Einladung kann
    hier also nicht fällig werden, und Telegram-Aufrufe gehören nicht in
    einen Deploy-Schritt.
    """
    for profile_id in sorted({reference.profile_id for reference in missing}):
        with transaction.atomic():
            profile = (
                MemberProfile.objects.select_for_update(of=("self",))
                .select_related("user")
                .get(pk=profile_id)
            )
            # Unter Sperre erneut prüfen: Ein Upload kann den Verweis seit
            # dem Scan ersetzt haben.
            cleared = [
                name
                for name in _AVATAR_FIELDS
                if _is_dead_reference(getattr(profile, name).name)
            ]
            if not cleared:
                continue
            report.cleared_fields.extend((profile.pk, name) for name in cleared)
            logger.warning(
                "Profil %s verweist auf fehlende Avatar-Datei(en) %s – %s.",
                profile.pk,
                ", ".join(cleared),
                "würde geleert" if dry_run else "wird geleert",
            )
            if dry_run:
                continue
            for name in cleared:
                setattr(profile, name, None)
            profile.save(update_fields=cleared)
            was_visible = profile.is_directory_visible
            profile.refresh_directory_visibility(save=True)
            if was_visible and not profile.is_directory_visible:
                report.hidden_profile_ids.append(profile.pk)
                logger.warning(
                    "Profil %s ist ohne Avatar unvollständig und nicht mehr im "
                    "Verzeichnis sichtbar.",
                    profile.pk,
                )


def _is_dead_reference(file_name: str | None) -> bool:
    if not file_name:
        return False
    try:
        return not default_storage.exists(file_name)
    except _STORAGE_ERRORS:
        # Schon beim Scan als Fehler gemeldet; im Zweifel nicht leeren.
        return False


def _rewrite_referenced_legacy_files(
    report: LegacyAvatarCleanupReport,
    missing_names: set[str],
    *,
    dry_run: bool,
) -> None:
    """
    Bringt referenzierte Altdateien unter Zufallsnamen.

    Lesbare Bilder werden ohne Metadaten neu geschrieben. Was Pillow nicht
    verarbeiten kann (kaputt, Format außerhalb der Allowlist), wird mit
    unveränderten Bytes verschoben – liegen bleiben darf es unter dem
    erratbaren Namen nicht, und löschen würde dem Mitglied den Avatar
    nehmen. Die alte Datei wird erst nach dem Commit gelöscht (über die
    on_commit-Löschung des Profils), damit ein Rollback keinen Verweis ins
    Leere hinterlässt.
    """
    for profile_id in _legacy_reference_profile_ids():
        with transaction.atomic():
            profile = MemberProfile.objects.select_for_update().get(pk=profile_id)
            changed: list[str] = []
            for name in _AVATAR_FIELDS:
                field_file = getattr(profile, name)
                old_name = field_file.name
                if (
                    not field_file
                    or not is_legacy_avatar_path(old_name)
                    or old_name in missing_names
                ):
                    continue
                if dry_run:
                    report.renamed_files.append((old_name, ""))
                    continue
                if _replace_legacy_file(field_file, report, profile_id=profile.pk):
                    changed.append(name)
                    schedule_avatar_file_deletion([old_name])
            if changed:
                profile.save(update_fields=changed)


def _replace_legacy_file(
    field_file, report: LegacyAvatarCleanupReport, *, profile_id: int
) -> bool:
    """
    Schreibt eine Altdatei unter Zufallsnamen; False bei Storage-Fehlern.
    """
    old_name = field_file.name
    try:
        with default_storage.open(old_name, "rb") as handle:
            raw = handle.read()
    except _STORAGE_ERRORS as exc:
        _record_failure(report, old_name, profile_id=profile_id, exc=exc)
        return False

    try:
        content = strip_image_metadata(io.BytesIO(raw))
    except _UNPROCESSABLE_IMAGE_ERRORS as exc:
        logger.error(
            "Avatar-Altdatei %s (Profil %s) nicht als Bild verarbeitbar, wird "
            "unverändert unter Zufallsnamen verschoben: %s",
            old_name,
            profile_id,
            exc,
        )
        # Der Dateiname liefert upload_to die Endung, der Name selbst wird
        # durch einen Zufallsnamen ersetzt.
        content = ContentFile(raw, name=posixpath.basename(old_name))
        target = report.moved_files
    else:
        target = report.renamed_files

    try:
        field_file.save(content.name, content, save=False)
    except _STORAGE_ERRORS as exc:
        _record_failure(report, old_name, profile_id=profile_id, exc=exc)
        return False
    target.append((old_name, field_file.name))
    return True


def _record_failure(
    report: LegacyAvatarCleanupReport,
    file_name: str,
    *,
    profile_id: int,
    exc: Exception,
) -> None:
    report.failed_files.append(file_name)
    logger.error(
        "Avatar-Altdatei %s (Profil %s) nicht bearbeitbar, bleibt unverändert: %s",
        file_name,
        profile_id,
        exc,
    )


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
        except _STORAGE_ERRORS as exc:
            report.failed_files.append(name)
            logger.warning("Avatar-Altdatei %s nicht löschbar: %s", name, exc)
        else:
            report.deleted_files.append(name)


def _avatar_references() -> list[_AvatarReference]:
    # __gt="": weder NULL noch leerer String – beides heißt "kein Bild".
    rows = (
        MemberProfile.objects.filter(Q(avatar__gt="") | Q(avatar_original__gt=""))
        .order_by("pk")
        .values_list("pk", *_AVATAR_FIELDS)
    )
    return [
        _AvatarReference(profile_id, field_name, file_name)
        for profile_id, *file_names in rows
        for field_name, file_name in zip(_AVATAR_FIELDS, file_names)
        if file_name
    ]


def _legacy_reference_profile_ids() -> list[int]:
    return sorted(
        {
            reference.profile_id
            for reference in _avatar_references()
            if is_legacy_avatar_path(reference.file_name)
        }
    )


def _referenced_file_names() -> set[str]:
    return {reference.file_name for reference in _avatar_references()}


def _list_avatar_files() -> set[str]:
    names: set[str] = set()
    for directory in (AVATAR_DIR, AVATAR_ORIGINALS_DIR):
        try:
            _, files = default_storage.listdir(directory)
        except FileNotFoundError:
            continue
        names.update(f"{directory}/{name}" for name in files)
    return names


def _has_any_avatar_file() -> bool:
    return bool(_list_avatar_files())


def _legacy_file_names() -> set[str]:
    return {
        name
        for name in _list_avatar_files()
        if is_legacy_avatar_file_name(name.rpartition("/")[2])
    }
