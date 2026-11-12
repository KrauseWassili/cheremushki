from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

from apps.bot.services.invites import is_group_member

NOT_GROUP_MEMBER_CODE = "not_group_member"


class IsActiveAuthenticated(BasePermission):
    """
    Nur eingeloggte und aktivierte Nutzer (E-Mail-Aktivierung bestanden).
    """

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active)


def can_view_directory(user) -> bool:
    """
    Darf dieser Nutzer das Mitgliederverzeichnis sehen?

    Einzige Definition der Regel: IsGroupMember prüft sie, MyProfileSerializer
    liefert sie als ``can_view_directory`` ans Frontend. Staff ist
    ausgenommen – Betreiber sehen die Profile ohnehin im Admin, und die
    Gruppen-Admins sind ohne Einladungslink beigetreten, haben also kein
    ``used=True``.
    """
    return user.is_staff or is_group_member(user.pk)


class NotGroupMember(PermissionDenied):
    """
    403 mit maschinenlesbarem ``code`` im Body.

    DRF rendert bei einem String-Detail nur ``{"detail": ...}``, der Code
    ginge verloren. Als Dict-Detail entsteht ``{"detail": ..., "code": ...}``
    – dieselbe Form wie SimpleJWTs ``token_not_valid``. So unterscheidet das
    Frontend „noch nicht in der Gruppe“ von anderen 403, ohne den Text zu
    vergleichen.
    """

    default_detail = (
        "Каталог участников открыт только для участников Telegram-группы. "
        "Заполни профиль — придёт приглашение в группу, а после вступления "
        "каталог откроется."
    )
    default_code = NOT_GROUP_MEMBER_CODE

    def __init__(self):
        super().__init__(
            detail={"detail": self.default_detail, "code": self.default_code},
            code=self.default_code,
        )


class IsGroupMember(BasePermission):
    """
    Verzeichnis nur für Mitglieder der Telegram-Gruppe (E2E F4).

    Muss in ``permission_classes`` hinter IsActiveAuthenticated stehen: Ohne
    gültigen Login soll 401 kommen, nicht dieser 403. Bewusst synchron –
    adrf prüft async-Permissions vor allen synchronen, die Reihenfolge ginge
    verloren. ``initial()`` läuft ohnehin in ``sync_to_async``, die
    ORM-Abfrage blockiert also nicht den Event-Loop.
    """

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if not can_view_directory(user):
            raise NotGroupMember()
        return True
