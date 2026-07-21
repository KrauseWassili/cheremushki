import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


class EntirelyAlphabeticPasswordValidator:
    @staticmethod
    def validate(password, user=None):
        if not any(character.isdigit() for character in password):
            raise ValidationError(
                _("Das Passwort muss Ziffern enthalten"),
                code="password_has_no_numbers",
            )

    @staticmethod
    def get_help_text():
        return _("Dein Passwort muss mindestens eine Ziffer enthalten.")


class EntirelyNonCapitalLetterPasswordValidator:
    @staticmethod
    def validate(password, user=None):
        if not any(character.isupper() for character in password):
            raise ValidationError(
                _("Das Passwort muss mindestens einen großen Buchstaben enthalten"),
                code="password_has_no_capital_letters",
            )

    @staticmethod
    def get_help_text():
        return _("Das Passwort muss mindestens einen großen Buchstaben enthalten.")


class NoSmallLetterPasswordValidator:
    @staticmethod
    def validate(password, user=None):
        if not any(character.islower() for character in password):
            raise ValidationError(
                _("Das Passwort muss mindestens einen kleinen Buchstaben enthalten"),
                code="password_has_no_small_letters",
            )

    @staticmethod
    def get_help_text():
        return _("Das Passwort muss mindestens einen kleinen Buchstaben enthalten.")


class EntirelyNoneSpecialCharactersPasswordValidator:
    @staticmethod
    def validate(password, user=None):
        if not re.search("[^A-Za-z0-9]", password):
            raise ValidationError(
                _("Das Passwort muss mindestens ein Sonderzeichen enthalten"),
                code="password_has_no_special_characters",
            )

    @staticmethod
    def get_help_text():
        return _("Das Passwort muss mindestens ein Sonderzeichen enthalten.")
