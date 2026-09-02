from django import forms
from django.contrib import admin
from django.db.models import Count
from unfold.admin import ModelAdmin

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

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("tags")

    @admin.display(description="Tags")
    def tag_list(self, obj: MemberProfile) -> str:
        return ", ".join(tag.name for tag in obj.tags.all()) or "—"


@admin.register(ContactRequest)
class ContactRequestAdmin(ModelAdmin):
    list_display = ("from_user", "to_profile", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("from_user__email", "to_profile__slug")
