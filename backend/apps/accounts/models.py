from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import PermissionsMixin
from django.db import models

from .managers import UserManager


class CustomUser(AbstractBaseUser, PermissionsMixin):
    """
    Custom User Model.
    """

    customer_number = models.CharField(
        "Kundennummer",
        max_length=16,
        unique=True,
        blank=True,
        null=True,
    )
    email = models.EmailField(unique=True)  # unique
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)

    street = models.CharField("Straße", max_length=255)
    street_no = models.CharField("Hausnummer", max_length=255, blank=True)
    zip_code = models.CharField("PLZ", max_length=5)
    city = models.CharField("Ort", max_length=255)
    country = models.CharField("Land", max_length=255, default="Deutschland")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    is_staff = models.BooleanField(
        "staff status",
        default=False,
        help_text="Designates whether the user can log into this admin site.",
    )
    is_active = models.BooleanField(
        "active",
        default=False,
        help_text=(
            "Designates whether this user should be treated as active. "
            "Unselect this instead of deleting accounts."
        ),
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    objects = UserManager()

    class Meta:
        ordering = ["email"]
        verbose_name = "Benutzer"
        verbose_name_plural = "Benutzer"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def __str__(self):
        return self.email

    def clean(self):
        super().clean()
        self.email = self.__class__.objects.normalize_email(self.email)
