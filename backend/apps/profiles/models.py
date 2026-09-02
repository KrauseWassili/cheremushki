from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify
from taggit.managers import TaggableManager
from taggit.models import TagBase, TaggedItemBase

from .hashtags import (
    InvalidHashtag,
    build_hashtag,
    normalize_hashtag,
    parse_hashtag,
)


def avatar_upload_to(instance: "MemberProfile", filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "jpg"
    if ext not in {"jpg", "jpeg", "png", "webp"}:
        ext = "jpg"
    return f"avatars/user-{instance.user_id}.{ext}"


def avatar_original_upload_to(instance: "MemberProfile", filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "jpg"
    if ext not in {"jpg", "jpeg", "png", "webp"}:
        ext = "jpg"
    return f"avatars/originals/user-{instance.user_id}.{ext}"


# --- Die Pflichtfelder für die Aufnahme ins Verzeichnis
DIRECTORY_REQUIRED_FIELDS: tuple[str, ...] = (
    "avatar",
    "city",
    "headline",
    "bio",
    "can_help_with",
    "looking_for",
)


# Slugs, die im Verzeichnis-Router bereits eine Route belegen. Der Router
# registriert MemberProfileViewSet als Catch-all unter api/v1/profiles/ – ein
# Mitglied mit dem Slug "tags" wäre unter /profiles/tags/ nicht erreichbar,
# weil dort die @action liegt. Deshalb werden diese Slugs gar nicht erst
# vergeben.
RESERVED_SLUGS: frozenset[str] = frozenset({"user", "tags", "cities"})


class ProfileTag(TagBase):
    """
    Tag Vokabular für Mitgliederprofile.

    Strikte Allowlist: Mitglieder wählen aus dieser Tabelle aus, anlegen darf
    nur der Admin. name trägt immer die Hashtag Form, label den
    lesbaren Anzeigenamen für die Oberfläche.
    """

    label = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name="Anzeigename",
        help_text="Lesbare Schreibweise, z. B. Веб-разработка.",
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Aktiv",
        help_text="Inaktive Tags verschwinden aus Autocomplete und werden bei"
        "neuen Zuordnungen abgelehnt. Bestehende Zuordnungen bleiben bestehen.",
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Profil-Tag"
        verbose_name_plural = "Profil-Tags"
        indexes = [
            models.Index(fields=["is_active", "name"]),
        ]

    def __str__(self):
        return self.display_label

    @property
    def display_label(self) -> str:
        return str(self.label or self.name)

    @property
    def hashtag(self) -> str:
        return build_hashtag(self.name)

    def clean(self):
        """
        Validiert den Namen, bevor die Admin Validierung ihn prüft.

        Damit landen auch Admineingaben wie #IT oder Веб Разработка in der
        Form, die später im Telegram Post steht und die Unique-Prüfung des
        Formulars greift auf dem validierten Wert statt auf der Schreibweise.
        """
        super().clean()
        self.name = self._canonical_name()

    def save(self, *args, **kwargs):
        self.name = self._canonical_name()
        return super().save(*args, **kwargs)

    def slugify(self, tag, i=None):
        """
        Erzeugt den Slug aus der kanonischen Form statt aus dem Rohnamen.

        Djangos slugify() ohne allow_unicode wirft kyrillische Zeichen komplett
        weg 'Крипта' ergäbe einen leeren Slug und damit ab dem zweiten
        kyrillischen Tag eine Unique-Kollision. Der Fallback greift nur, wenn
        taggit uns einen nicht validierten Wert übergibt.
        """
        base = normalize_hashtag(tag) or slugify(tag, allow_unicode=True)
        return f"{base}_{i}" if i is not None else base

    def _canonical_name(self) -> str:
        try:
            return parse_hashtag(self.name)
        except InvalidHashtag as exc:
            raise ValidationError({"name": str(exc)}) from exc


class TaggedProfile(TaggedItemBase):
    """
    Through-Tabelle: echter FK statt ContentType-Lookup.

    Das spart pro Query den Join über django_content_type und erlaubt saubere
    Aggregate über die Nutzungshäufigkeit eines Tags.
    """

    tag = models.ForeignKey(
        ProfileTag,
        on_delete=models.CASCADE,
        related_name="tagged_profiles",
    )
    content_object = models.ForeignKey(
        "MemberProfile",
        on_delete=models.CASCADE,
        related_name="tagged_items",
    )

    class Meta:
        verbose_name = "Tag-Zuordnung"
        verbose_name_plural = "Tag-Zuordnungen"
        indexes = [
            models.Index(fields=["tag", "content_object"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tag", "content_object"],
                name="unique_tag_per_profile",
            )
        ]


class ContactMode(models.TextChoices):
    DIRECT = "direct", "Direkt"
    REQUEST = "request", "Anfrage"
    GROUP = "group", "Gruppe"
    CLOSED = "closed", "Geschlossen"


class MemberProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="member_profile",
    )
    slug = models.SlugField(max_length=80, unique=True, blank=True, default="")

    headline = models.CharField(max_length=200, blank=True, default="")
    city = models.CharField(max_length=120, blank=True, default="")
    profession = models.CharField(max_length=120, blank=True, default="")
    company = models.CharField(max_length=120, blank=True, default="")
    position = models.CharField(max_length=120, blank=True, default="")

    bio = models.TextField(blank=True, default="")
    can_help_with = models.TextField(blank=True, default="")
    looking_for = models.TextField(blank=True, default="")

    # Kuratiertes Vokabular über eine eigene Through-Tabelle. Nur der
    # Serializer setzt hier – und ausschließlich mit ProfileTag-Instanzen,
    # damit taggit keine unbekannten Tags anlegt.
    tags = TaggableManager(
        through=TaggedProfile,
        blank=True,
        verbose_name="Tags",
        help_text="Kuratierte Tags aus dem Vokabular.",
    )
    languages = models.JSONField(default=list, blank=True)
    achievements = models.JSONField(default=list, blank=True)

    # 32 = Telegrams Maximum. Der Wert wird kanonisch gespeichert (bare,
    # lowercase, ohne '@' und ohne URL) siehe apps.profiles.telegram.
    telegram_username = models.CharField(max_length=32, blank=True, default="")
    linkedin_url = models.URLField(blank=True, default="")
    website_url = models.URLField(blank=True, default="")
    contact_mode = models.CharField(
        max_length=16,
        choices=ContactMode.choices,
        default=ContactMode.REQUEST,
    )
    telegram_group_url = models.URLField(blank=True, default="")

    avatar = models.ImageField(upload_to=avatar_upload_to, blank=True, null=True)
    avatar_original = models.ImageField(
        upload_to=avatar_original_upload_to, blank=True, null=True
    )
    avatar_position_x = models.FloatField(default=0.5)
    avatar_position_y = models.FloatField(default=0.5)
    avatar_scale = models.FloatField(default=1.0)
    avatar_crop_size = models.FloatField(default=1.0)

    is_directory_visible = models.BooleanField(default=False)

    class Meta:
        ordering = ["slug"]
        verbose_name = "Mitgliederprofil"
        verbose_name_plural = "Mitgliederprofile"

    def __str__(self):
        return f"{self.slug} ({self.user.email})"

    def missing_directory_fields(self) -> list[str]:
        """
        Nennt die noch leeren Pflichtfelder in Formularreihenfolge.
        """
        missing = []
        for name in DIRECTORY_REQUIRED_FIELDS:
            value = getattr(self, name)
            # Der Avatar ist ein FieldFile: bool() prüft, ob eine Datei
            # zugeordnet ist. Die Textfelder brauchen strip(), damit ein
            # Leerzeichen nicht als Inhalt zählt.
            filled = bool(value) if name == "avatar" else bool(str(value).strip())
            if not filled:
                missing.append(name)
        return missing

    def compute_directory_ready(self) -> bool:
        return not self.missing_directory_fields() and self.user.is_active

    def refresh_directory_visibility(self, save: bool = True) -> bool:
        """
        Aktualisiert die Sichtbarkeit und meldet den Übergang.
        """
        ready = self.compute_directory_ready()
        became_ready = ready and not self.is_directory_visible
        if self.is_directory_visible != ready:
            self.is_directory_visible = ready
            if save:
                self.save(update_fields=["is_directory_visible"])
        return became_ready

    def anonymize(self) -> None:
        """
        Entfernt alle personenbezogenen Inhalte aus dem Profil bei Löschen.
        """
        for name in ("avatar", "avatar_original"):
            field = getattr(self, name)
            if field:
                # --- save=False: Es folgt ohnehin ein save() über alle Felder.
                field.delete(save=False)

        self.headline = ""
        self.city = ""
        self.profession = ""
        self.company = ""
        self.position = ""
        self.bio = ""
        self.can_help_with = ""
        self.looking_for = ""
        # clear() statt Zuweisung: Der TaggableManager ist kein Feld, dem man
        # eine Liste zuweisen kann – die Zuordnungen werden gelöscht, die
        # ProfileTag-Einträge selbst bleiben dem Vokabular erhalten.
        self.tags.clear()
        self.languages = []
        self.achievements = []
        self.telegram_username = ""
        self.linkedin_url = ""
        self.website_url = ""
        self.telegram_group_url = ""
        self.contact_mode = ContactMode.CLOSED
        self.is_directory_visible = False
        self.slug = f"deleted-{self.user_id}"

        # Der Bildzuschnitt beschreibt ein Bild, das es nicht mehr gibt. Kein
        # Personenbezug, aber auch kein Grund, ihn liegen zu lassen: Die Regel
        # "alles außer Primär- und Fremdschlüssel geht in den Ausgangszustand"
        # ist leichter zu verteidigen als eine Liste harmloser Ausnahmen.
        #
        # Die Werte kommen aus den Feld-Defaults und nicht als Literale –
        # ändert sich ein Default, folgt die Anonymisierung automatisch.
        for name in (
            "avatar_position_x",
            "avatar_position_y",
            "avatar_scale",
            "avatar_crop_size",
        ):
            setattr(self, name, self._meta.get_field(name).default)

        self.save()

    def ensure_unique_slug(self, base: str | None = None) -> None:
        if self.slug:
            return
        source = base or f"{self.user.first_name}-{self.user.last_name}"
        base_slug = slugify(source) or f"member-{self.user.pk}"
        candidate = base_slug
        counter = 2
        # Reservierte Slugs verhalten sich wie belegte: Ein Mitglied namens
        # "Tags" weicht auf "tags-2" aus, statt unter einer Route zu landen,
        # die der Router an eine @action vergibt.
        while (
            candidate in RESERVED_SLUGS
            or MemberProfile.objects.filter(slug=candidate).exclude(pk=self.pk).exists()
        ):
            candidate = f"{base_slug}-{counter}"
            counter += 1
        self.slug = candidate


class ContactRequestStatus(models.TextChoices):
    PENDING = "pending", "Ausstehend"
    SENT = "sent", "Gesendet"
    FAILED = "failed", "Fehlgeschlagen"


class ContactRequest(models.Model):
    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_contact_requests",
    )
    to_profile = models.ForeignKey(
        MemberProfile,
        on_delete=models.CASCADE,
        related_name="contact_requests",
    )
    message = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=16,
        choices=ContactRequestStatus.choices,
        default=ContactRequestStatus.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Kontaktanfrage"
        verbose_name_plural = "Kontaktanfragen"
        constraints = [
            models.UniqueConstraint(
                fields=["from_user", "to_profile"],
                name="unique_contact_request_per_pair",
            )
        ]

    def __str__(self):
        return f"{self.from_user_id} → {self.to_profile_id} ({self.status})"
