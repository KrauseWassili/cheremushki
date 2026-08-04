from unfold.admin import ModelAdmin
from django.contrib import admin
from .models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(ModelAdmin):
    list_display = (
        "first_name",
        "last_name",
        "email",
        "is_active",
        "is_staff",
        "created_at",
        "updated_at",
    )
    list_filter = ("email", "is_active", "is_staff")
    search_fields = ("email", "first_name", "last_name")
    readonly_fields = (
        "is_active",
        "is_staff",
        "created_at",
        "updated_at",
    )
