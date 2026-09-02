"""Schritt 1 von 3: Tag-Vokabular anlegen, altes JSONField beiseite legen.

Der Umstieg ist in drei Migrationen geteilt, damit zwischen Schema und
Datenübernahme ein Rollback-Punkt liegt: 0005 baut nur auf, 0006 überträgt die
Daten, 0007 löscht die alte Spalte. Bricht die Übernahme, steht der Bestand
noch unverändert in `legacy_tags`.

RenameField statt AddField+RemoveField: Postgres benennt die Spalte um, ohne
sie neu zu schreiben – und der Bestand ist ohne Kopieren erhalten.
"""

import django.db.models.deletion
import taggit.managers
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("profiles", "0004_canonical_telegram_username"),
    ]

    operations = [
        migrations.RenameField(
            model_name="memberprofile",
            old_name="tags",
            new_name="legacy_tags",
        ),
        migrations.CreateModel(
            name="ProfileTag",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "name",
                    models.CharField(max_length=100, unique=True, verbose_name="name"),
                ),
                (
                    "slug",
                    models.SlugField(
                        allow_unicode=True,
                        max_length=100,
                        unique=True,
                        verbose_name="slug",
                    ),
                ),
                (
                    "label",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="Lesbare Schreibweise, z. B. „Веб-разработка“. "
                        "Leer = der kanonische Name wird angezeigt.",
                        max_length=100,
                        verbose_name="Anzeigename",
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        help_text="Inaktive Tags verschwinden aus Autocomplete und "
                        "werden bei neuen Zuordnungen abgelehnt. Bestehende "
                        "Zuordnungen bleiben bestehen.",
                        verbose_name="Aktiv",
                    ),
                ),
            ],
            options={
                "verbose_name": "Profil-Tag",
                "verbose_name_plural": "Profil-Tags",
                "ordering": ["name"],
                "indexes": [
                    models.Index(
                        fields=["is_active", "name"],
                        name="profiles_pr_is_acti_4ed359_idx",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="TaggedProfile",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "content_object",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="tagged_items",
                        to="profiles.memberprofile",
                    ),
                ),
                (
                    "tag",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="tagged_profiles",
                        to="profiles.profiletag",
                    ),
                ),
            ],
            options={
                "verbose_name": "Tag-Zuordnung",
                "verbose_name_plural": "Tag-Zuordnungen",
            },
        ),
        migrations.AddField(
            model_name="memberprofile",
            name="tags",
            field=taggit.managers.TaggableManager(
                blank=True,
                help_text="Kuratierte Tags aus dem Vokabular.",
                through="profiles.TaggedProfile",
                to="profiles.ProfileTag",
                verbose_name="Tags",
            ),
        ),
        migrations.AddIndex(
            model_name="taggedprofile",
            index=models.Index(
                fields=["tag", "content_object"], name="profiles_ta_tag_id_0e7723_idx"
            ),
        ),
        migrations.AddConstraint(
            model_name="taggedprofile",
            constraint=models.UniqueConstraint(
                fields=("tag", "content_object"), name="unique_tag_per_profile"
            ),
        ),
    ]
