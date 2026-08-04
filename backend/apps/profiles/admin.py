from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import ContactRequest, MemberProfile


@admin.register(MemberProfile)
class MemberProfileAdmin(ModelAdmin):
    list_display = (
        "slug",
        "user",
        "city",
        "contact_mode",
        "is_directory_visible",
    )
    list_filter = ("contact_mode", "is_directory_visible", "city")
    search_fields = ("slug", "user__email", "user__first_name", "user__last_name")


@admin.register(ContactRequest)
class ContactRequestAdmin(ModelAdmin):
    list_display = ("from_user", "to_profile", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("from_user__email", "to_profile__slug")
