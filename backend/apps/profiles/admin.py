from functools import partial

from django import forms
from django.contrib import admin, messages
from django.db import transaction
from django.db.models import Count
from unfold.admin import ModelAdmin

from apps.bot.services.invites import (
    claim_invite_dispatch,
    release_invite_for_resend,
)
from apps.bot.tasks.email import send_telegram_invite_email

from .models import ContactRequest, MemberProfile, ProfileTag


@admin.register(ProfileTag)
class ProfileTagAdmin(ModelAdmin):
    """
    Pflege des Vokabulars die einzige Stelle, an der Tags
    entstehen. Mitglieder können nur auswählen.
    """

    list_display = ("name", "label", "is_active", "usage_count")
    list_editable = ("is_active",)
    list_filter = ("is_active",)
    search_fields = ("name", "label")
    ordering = ("name",)
    readonly_fields = ("slug",)
    fields = ("name", "label", "is_active", "slug")

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(usage_count=Count("tagged_profiles", distinct=True))
        )

    @admin.display(description="Profile", ordering="usage_count")
    def usage_count(self, obj: ProfileTag) -> int:
        return obj.usage_count


class MemberProfileAdminForm(forms.ModelForm):
    """
    Tags als Auswahl statt als Freitextfeld.

    taggit liefert von Haus aus ein kommasepariertes Textfeld, das für jeden
    unbekannten Wert einen neuen Tag anlegt. Das ist genau das, was die
    Allowlist verhindern soll und es würde hier zusätzlich in einen
    IntegrityError laufen, sobald die Validierung des neuen Namens auf einen
    bestehenden Tag trifft. Neue Tags entstehen ausschließlich im ProfileTag Admin.
    """

    tags = forms.ModelMultipleChoiceField(
        queryset=ProfileTag.objects.filter(is_active=True),
        required=False,
        label="Tags",
        help_text="Nur aktive Tags des Vokabulars.",
    )

    class Meta:
        model = MemberProfile
        fields = "__all__"


@admin.register(MemberProfile)
class MemberProfileAdmin(ModelAdmin):
    form = MemberProfileAdminForm
    list_display = (
        "slug",
        "user",
        "city",
        "tag_list",
        "contact_mode",
        "is_directory_visible",
    )
    list_filter = ("contact_mode", "is_directory_visible", "city")
    search_fields = (
        "slug",
        "user__email",
        "user__first_name",
        "user__last_name",
        "tags__name",
        "tags__label",
    )

    actions = ("resend_telegram_invite",)

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("tags")

    @admin.display(description="Tags")
    def tag_list(self, obj: MemberProfile) -> str:
        return ", ".join(tag.name for tag in obj.tags.all()) or "—"

    @admin.action(description="Telegram-Einladung erneut senden")
    def resend_telegram_invite(self, request, queryset) -> None:
        """
        Stößt die Einladung für die gewählten Profile erneut an.

        Für den Fall, dass die Mail zwar als versandt gilt, aber nie ankam
        (Spam, Tippfehler) – ein gescheiterter Versand holt sich beim nächsten
        Speichern des Profils von selbst nach. Was zurückgesetzt wird und
        warum der Link bleibt, steht bei ``release_invite_for_resend``. Die
        Vollständigkeit prüft der Task ohnehin selbst; hier wird sie nur
        vorab gefiltert, damit die Rückmeldung stimmt.
        """
        queued = incomplete = joined = 0
        for profile in queryset.select_related("user"):
            if not profile.compute_directory_ready():
                incomplete += 1
                continue
            if not release_invite_for_resend(profile.user_id):
                joined += 1
                continue
            # Ausdrücklich angeforderter Neuversand: Eine Dispatch-Sperre
            # aus einem früheren Anlauf gilt hier nicht. force setzt sie
            # neu, damit ein Speichern des Nutzers direkt danach nicht
            # einen zweiten Task mit derselben Mail anstößt.
            claim_invite_dispatch(profile.user_id, force=True)
            # Erst nach dem Commit: Der Worker soll das zurückgesetzte
            # invite_sent_at sehen, nicht den alten Stand.
            transaction.on_commit(
                partial(send_telegram_invite_email.delay, profile.user_id)
            )
            queued += 1

        self.message_user(
            request,
            f"Einladung angestoßen: {queued}. Übersprungen – Profil "
            f"unvollständig: {incomplete}, Gruppe bereits beigetreten: {joined}.",
            messages.SUCCESS if queued else messages.WARNING,
        )


@admin.register(ContactRequest)
class ContactRequestAdmin(ModelAdmin):
    list_display = ("from_user", "to_profile", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("from_user__email", "to_profile__slug")
