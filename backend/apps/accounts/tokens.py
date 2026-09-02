from django.contrib.auth.tokens import PasswordResetTokenGenerator


class EmailChangeTokenGenerator(PasswordResetTokenGenerator):
    """
    Token generator for email change confirmation.
    """

    def _make_hash_value(self, user, timestamp):
        return f"{user.pk}{user.pending_email}{timestamp}"


email_change_token_generator = EmailChangeTokenGenerator()
