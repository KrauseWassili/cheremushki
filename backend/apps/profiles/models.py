from django.conf import settings
from django.db import models
from django.utils.text import slugify


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

    tags = models.JSONField(default=list, blank=True)
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
        self.tags = []
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
        while MemberProfile.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
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
