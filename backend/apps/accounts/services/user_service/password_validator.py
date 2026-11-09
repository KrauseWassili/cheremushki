"""
Zusätzliche Passwortregeln.

Die Meldungen sind direkt russisch und ohne gettext: Eine russische msgid
über gettext zu schicken übersetzt nichts, und die Oberfläche ist
ausschließlich russisch. Nebenwirkung: Auch der (deutsche) Admin zeigt diese
Hinweise beim Passwortwechsel auf Russisch – bewusst in Kauf genommen.
"""

import re

from django.core.exceptions import ValidationError


class EntirelyAlphabeticPasswordValidator:
    @staticmethod
    def validate(password, user=None):
        if not any(character.isdigit() for character in password):
            raise ValidationError(
                "Пароль должен содержать хотя бы одну цифру.",
                code="password_has_no_numbers",
            )

    @staticmethod
    def get_help_text():
        return "Пароль должен содержать хотя бы одну цифру."


class EntirelyNonCapitalLetterPasswordValidator:
    @staticmethod
    def validate(password, user=None):
        if not any(character.isupper() for character in password):
            raise ValidationError(
                "Пароль должен содержать хотя бы одну заглавную букву.",
                code="password_has_no_capital_letters",
            )

    @staticmethod
    def get_help_text():
        return "Пароль должен содержать хотя бы одну заглавную букву."


class NoSmallLetterPasswordValidator:
    @staticmethod
    def validate(password, user=None):
        if not any(character.islower() for character in password):
            raise ValidationError(
                "Пароль должен содержать хотя бы одну строчную букву.",
                code="password_has_no_small_letters",
            )

    @staticmethod
    def get_help_text():
        return "Пароль должен содержать хотя бы одну строчную букву."


class EntirelyNoneSpecialCharactersPasswordValidator:
    @staticmethod
    def validate(password, user=None):
        if not re.search("[^A-Za-z0-9]", password):
            raise ValidationError(
                "Пароль должен содержать хотя бы один специальный символ.",
                code="password_has_no_special_characters",
            )

    @staticmethod
    def get_help_text():
        return "Пароль должен содержать хотя бы один специальный символ."
