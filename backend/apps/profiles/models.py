from django.conf import settings
from django.db import models
from django.utils.text import slugify


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

    telegram_username = models.CharField(max_length=64, blank=True, default="")
    linkedin_url = models.URLField(blank=True, default="")
    website_url = models.URLField(blank=True, default="")
    contact_mode = models.CharField(
        max_length=16,
        choices=ContactMode.choices,
        default=ContactMode.REQUEST,
    )
    telegram_group_url = models.URLField(blank=True, default="")

    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    avatar_original = models.ImageField(
        upload_to="avatars/originals/", blank=True, null=True
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

    def compute_directory_ready(self) -> bool:
        required = [
            bool(self.avatar),
            bool(self.city.strip()),
            bool(self.headline.strip()),
            bool(self.bio.strip()),
            bool(self.can_help_with.strip()),
            bool(self.looking_for.strip()),
        ]
        return all(required) and self.user.is_active

    def refresh_directory_visibility(self, save: bool = True) -> None:
        ready = self.compute_directory_ready()
        if self.is_directory_visible != ready:
            self.is_directory_visible = ready
            if save:
                self.save(update_fields=["is_directory_visible"])

    def ensure_unique_slug(self, base: str | None = None) -> None:
        if self.slug:
            return
        source = base or f"{self.user.first_name}-{self.user.last_name}"
        base_slug = slugify(source) or f"member-{self.user.pk}"
        candidate = base_slug
        counter = 2
        while (
            MemberProfile.objects.filter(slug=candidate)
            .exclude(pk=self.pk)
            .exists()
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
