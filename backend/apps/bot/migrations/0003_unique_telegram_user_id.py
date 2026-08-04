from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bot", "0002_telegraminvite_profile_fields"),
    ]

    operations = [
        migrations.AlterField(
            model_name="telegraminvite",
            name="telegram_user_id",
            field=models.BigIntegerField(
                blank=True,
                help_text="Telegram-User-ID; pro Club-Account nur einmal erlaubt.",
                null=True,
                unique=True,
            ),
        ),
    ]
