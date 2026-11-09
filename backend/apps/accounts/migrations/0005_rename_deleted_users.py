"""
Bereits gelöschte Konten bekommen den russischen Anzeigenamen.

Bis zur Umstellung hat die Kontolöschung "Gelöscht Nutzer" gesetzt; der Name
kann in der Oberfläche auftauchen (z. B. als Absender alter Kontaktanfragen).
Die Werte stehen hier als Literale und nicht als Import aus
apps.accounts.views: Eine Migration muss auch dann noch dasselbe tun, wenn
sich die Konstanten später ändern.
"""

from django.db import migrations

# Konvention aus AccountDeleteViewSet: deleted-<pk>@deleted.local.
DELETED_EMAIL_SUFFIX = "@deleted.local"
DELETED_USER_FIRST_NAME = "Удалённый"
DELETED_USER_LAST_NAME = "пользователь"


def rename_deleted_users(apps, schema_editor):
    CustomUser = apps.get_model("accounts", "CustomUser")
    CustomUser.objects.filter(email__endswith=DELETED_EMAIL_SUFFIX).update(
        first_name=DELETED_USER_FIRST_NAME, last_name=DELETED_USER_LAST_NAME
    )


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_customuser_pending_email"),
    ]

    operations = [
        # Reverse = noop: Der alte deutsche Name war ein Fehler, ein
        # Zurückrollen des Schemas soll ihn nicht wiederherstellen.
        migrations.RunPython(rename_deleted_users, migrations.RunPython.noop),
    ]
