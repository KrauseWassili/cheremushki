from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bot", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="telegraminvite",
            name="telegram_user_id",
            field=models.BigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="telegraminvite",
            name="profile_message_id",
            field=models.BigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="telegraminvite",
            name="profile_chat_id",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="telegraminvite",
            name="profile_thread_id",
            field=models.BigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="telegraminvite",
            name="profile_photo_file_id",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="telegraminvite",
            name="profile_posted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="telegraminvite",
            name="profile_synced_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="telegraminvite",
            name="reminder_count",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="telegraminvite",
            name="last_reminder_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
