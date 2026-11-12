"""
Zustandsabfragen und -wechsel rund um die Telegram-Einladung.

Bewusst ohne Telegram-Call und ohne Task-Dispatch: Der Aufrufer
(Serializer, Admin) entscheidet, ob und wann ``send_telegram_invite_email``
angestoßen wird. Dass höchstens *ein Link* entsteht, garantiert allein der
Claim im Task. Die Dispatch-Sperre hier verhindert nur, dass kurz
hintereinander mehrere Tasks dieselbe Mail verschicken.
"""

from django.core.cache import cache
from django.db.models import Q

from ..models import TelegramInvite

# Länger als das volle Retry-Fenster von send_telegram_invite_email:
# 4 Versuche (max_retries=3) mit je bis zu 30 s Telegram-Timeout
# (API_TIMEOUT_SECONDS) plus 15 s Resend-Timeout (RESEND_TIMEOUT), dazu
# 3 × 30 s default_retry_delay – zusammen gut 4,5 Minuten. Zehn Minuten lassen
# Luft für Warteschlange und ein von Telegram genanntes retry_after. Solange
# ein Task noch läuft oder auf seinen Retry wartet, sieht jedes weitere
# Speichern ``invite_sent_at`` noch leer – ohne Sperre stieße es einen zweiten
# Task an, der nach dem Claim dieselbe Mail erneut verschickt.
INVITE_DISPATCH_DEBOUNCE_SECONDS = 10 * 60


def _invite_dispatch_key(user_id: int) -> str:
    return f"invite-dispatch:{user_id}"


def is_invite_pending(user_id: int) -> bool:
    """Steht für diesen Nutzer noch keine Einladung draußen?

    Falsch, sobald die Mail verschickt wurde (``invite_sent_at``) oder der
    Nutzer der Gruppe beigetreten ist (``used`` – gesetzt vom
    chat_member-Update oder von ``sync_telegram_profile``). Fehlt die
    Invite-Zeile ganz, ist die Einladung offen; der Task legt sie an.
    """
    return not TelegramInvite.objects.filter(
        Q(invite_sent_at__isnull=False) | Q(used=True), user_id=user_id
    ).exists()


def has_invite_been_sent(user_id: int) -> bool:
    """Ist die Einladungsmail nachweislich verschickt (``invite_sent_at``)?

    Einzige Definition von „versandt“ – Profil- und Account-Endpunkt melden
    sie als ``invite_sent`` bzw. ``has_telegram_invite`` ans Frontend.
    """
    return TelegramInvite.objects.filter(
        user_id=user_id, invite_sent_at__isnull=False
    ).exists()


def is_group_member(user_id: int) -> bool:
    """Ist der Nutzer der Telegram-Gruppe beigetreten?

    Signal ist ``used``, nicht ``telegram_user_id``: ``used`` setzen beide
    Beitrittswege (chat_member-Update und ``sync_telegram_profile
    --mark-joined``), die Telegram-ID fehlt beim manuellen Weg. Austritt oder
    Kick setzen ``used`` derzeit nicht zurück – das chat_member-Update dazu
    wird empfangen, aber verworfen. Nur die Kontolöschung
    (``purge_telegram_presence``) entzieht die Mitgliedschaft.
    """
    return TelegramInvite.objects.filter(user_id=user_id, used=True).exists()


def release_invite_for_resend(user_id: int) -> bool:
    """Gibt eine bereits versandte, aber ungenutzte Einladung erneut frei.

    Returns:
        ``False``, wenn der Nutzer der Gruppe schon beigetreten ist – dann
        gibt es nichts nachzuholen. Sonst ``True``.

    Zurückgesetzt wird nur ``invite_sent_at``, ``invite_link`` bleibt stehen:
    Der Task verschickt dann denselben ``member_limit=1``-Link noch einmal,
    es entsteht kein zusätzlicher Zugang zur Gruppe. Einen neuen Link zu
    erzeugen hieße, den alten vorher sicher zu widerrufen – und
    ``revoke_invite_link`` ist nur best effort. Zwei gültige Links für einen
    Account wären genau der Fehler, den der Claim verhindern soll.

    Als gefiltertes ``update``: Ein Beitritt, der parallel ``used`` setzt,
    wird nicht überschrieben.
    """
    if is_group_member(user_id):
        return False
    TelegramInvite.objects.filter(user_id=user_id, used=False).update(
        invite_sent_at=None
    )
    return True


def claim_invite_dispatch(user_id: int, *, force: bool = False) -> bool:
    """Darf jetzt ein Einladungs-Task angestoßen werden?

    Returns:
        ``True`` für den ersten Aufrufer innerhalb von
        ``INVITE_DISPATCH_DEBOUNCE_SECONDS``, danach ``False``.

    ``cache.add`` ist atomar (Redis ``SET NX``), daher gewinnt auch bei zwei
    gleichzeitigen Requests genau einer. Der Cache muss dafür zwischen Web
    und Worker geteilt sein wie für die übrigen Sperren. Geht der Schlüssel
    verloren (Redis-Neustart), droht höchstens eine doppelte Mail mit
    demselben Link – zusätzlichen Zugang verhindert der Claim im Task.

    ``force=True`` ist für die Admin-Action: Ein Betreiber, der ausdrücklich
    neu senden lässt, soll nicht an einer Sperre aus einem früheren Anlauf
    scheitern. Die Sperre wird dabei neu gesetzt, damit ein Speichern des
    Nutzers direkt danach keinen zweiten Task anstößt.
    """
    key = _invite_dispatch_key(user_id)
    if force:
        cache.set(key, 1, timeout=INVITE_DISPATCH_DEBOUNCE_SECONDS)
        return True
    return cache.add(key, 1, timeout=INVITE_DISPATCH_DEBOUNCE_SECONDS)
