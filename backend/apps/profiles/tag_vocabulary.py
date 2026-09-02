"""
Startvokabular für ProfileTag und das Seeding dazu.

Eigenes Modul, weil zwei Aufrufer dieselbe Liste brauchen: die Datenmigration
(einmalig beim Umstieg vom freien JSONField) und der Management-Command
(frische Datenbanken, spätere Ergänzungen). Eine zweite Kopie der Liste würde
über kurz oder lang auseinanderlaufen.

Das Seeding nimmt die Modellklasse als Argument, damit die Migration ihr
historisches Modell übergeben kann und nicht am Import des aktuellen Modells
hängt.
"""

from .hashtags import parse_hashtag

# Startvokabular für die russischsprachige Community in Bremen: (Name, Label).
# Der Name wird beim Speichern validiert, hier steht die lesbare Form, damit
# die Liste im Diff verständlich bleibt.
INITIAL_PROFILE_TAGS: tuple[tuple[str, str], ...] = (
    ("IT", "IT"),
    ("веб-разработка", "Веб-разработка"),
    ("дизайн", "Дизайн"),
    ("маркетинг", "Маркетинг"),
    ("продажи", "Продажи"),
    ("HR", "HR"),
    ("финансы", "Финансы"),
    ("инвестиции", "Инвестиции"),
    ("крипта", "Крипта"),
    ("налоги", "Налоги"),
    ("юристы", "Юристы"),
    ("недвижимость", "Недвижимость"),
    ("стартапы", "Стартапы"),
    ("логистика", "Логистика"),
    ("медицина", "Медицина"),
    ("психология", "Психология"),
    ("образование", "Образование"),
    ("языки", "Языки"),
    ("переезд", "Переезд"),
    ("дети", "Дети"),
    ("спорт", "Спорт"),
    ("музыка", "Музыка"),
    ("фото", "Фото"),
    ("видео", "Видео"),
    ("авто", "Авто"),
    ("ремонт", "Ремонт"),
    ("красота", "Красота"),
    ("еда", "Еда"),
    ("путешествия", "Путешествия"),
    ("наука", "Наука"),
)


def seed_profile_tags(tag_model) -> tuple[int, int]:
    """
    Legt das Startvokabular an, ohne Bestehendes zu verändern.

    Ein erneuter Lauf ergänzt nur, was fehlt. Bestehende Tags bleiben unangetastet
    insbesondere is_active und ein im Admin angepasstes Label, die sonst bei jedem
    Deploy zurückgesetzt werden würden.
    """
    created_count = 0
    skipped_count = 0

    for raw_name, label in INITIAL_PROFILE_TAGS:
        name = parse_hashtag(raw_name)
        _, created = tag_model.objects.get_or_create(
            name=name,
            defaults={"label": label, "slug": name, "is_active": True},
        )
        if created:
            created_count += 1
        else:
            skipped_count += 1

    return created_count, skipped_count
