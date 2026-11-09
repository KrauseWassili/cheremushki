"""
Vokabular für ProfileTag und das Seeding dazu.

Eigenes Modul, weil mehrere Aufrufer dieselben Listen brauchen: die
Datenmigrationen (0006 für das Startvokabular, 0008 für die Erweiterung) und
der Management-Command (frische Datenbanken). Eine zweite Kopie einer Liste
würde über kurz oder lang auseinanderlaufen.

Die Listen sind append-only: Eine Datenmigration importiert sie, eine
Änderung an einer bereits angewandten Liste würde also nur noch frische
Datenbanken erreichen und Bestand und Neuinstallation auseinanderlaufen
lassen. Neue Tags kommen deshalb in eine neue Liste mit eigener Migration.

Das Seeding nimmt die Modellklasse als Argument, damit die Migration ihr
historisches Modell übergeben kann und nicht am Import des aktuellen Modells
hängt.
"""

from collections import defaultdict
from collections.abc import Iterable

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


# Erweiterung um das Vokabular der Community (vormals
# tags_ru_alphabetical.csv). Nur Anzeigenamen: Der Name ergibt sich per
# parse_hashtag, z. B. "Бухгалтерский учёт" -> "бухгалтерский_учёт".
# 14 Einträge decken sich mit INITIAL_PROFILE_TAGS (gleicher Name, gleiches
# Label) – sie bleiben drin, damit die Liste der Quelle 1:1 entspricht; das
# Seeding überspringt sie. Alte Tags werden bewusst nicht deaktiviert:
# Profile können sie bereits tragen.
_COMMUNITY_PROFILE_TAG_LABELS: tuple[str, ...] = (
    "IT-инфраструктура",
    "Авиация и космос",
    "Автоматизация",
    "Автоматизация производства",
    "Автомобильная отрасль",
    "Активный отдых",
    "Альпинизм и скалолазание",
    "Архитектура",
    "Аудит",
    "Банковское дело",
    "Бег",
    "Бизнес и управление",
    "Биотехнологии",
    "Благотворительность",
    "Боевые искусства",
    "Брендинг",
    "Бухгалтерский учёт",
    "Веб-технологии",
    "Велоспорт",
    "Видеоигры",
    "Викторины и интеллектуальные игры",
    "Водные виды спорта",
    "Возобновляемая энергетика",
    "Волонтёрство",
    "Выпечка",
    "Гастрономия",
    "Городская инфраструктура",
    "Городское планирование",
    "Государственное управление",
    "Данные и аналитика",
    "Дизайн",
    "Дизайн и творчество",
    "Железнодорожный транспорт",
    "Журналистика",
    "Здоровый образ жизни",
    "Зимние виды спорта",
    "Издательское дело",
    "Изобразительное искусство",
    "Изучение языков",
    "Инвестиции",
    "Инженерия",
    "Интернет вещей",
    "Информационные технологии",
    "Искусственный интеллект",
    "Искусство и культура",
    "Исследование рынка",
    "История",
    "Йога",
    "Кемпинг",
    "Кибербезопасность",
    "Кино",
    "Климатические технологии",
    "Консалтинг",
    "Корпоративные коммуникации",
    "Космос",
    "Кофе",
    "Кулинария",
    "Лидерство",
    "Литература",
    "Логистика и цепочки поставок",
    "Маркетинг",
    "Материалы и технологии производства",
    "Машиностроение",
    "Медиа",
    "Медицина и здравоохранение",
    "Международный бизнес",
    "Межкультурное общение",
    "Мобильные технологии",
    "Морская отрасль",
    "Музыка",
    "Музыкальная индустрия",
    "Налоги",
    "Наставничество",
    "Настольные игры",
    "Наука",
    "Наука и исследования",
    "Недвижимость",
    "Некоммерческие организации",
    "Нетворкинг",
    "Облачные технологии",
    "Образование",
    "Обучение и развитие",
    "Общественные инициативы",
    "Операционное управление",
    "Организационное развитие",
    "Парусный спорт",
    "Пешие походы",
    "Писательство",
    "Пищевая индустрия",
    "Плавание",
    "Политика и общество",
    "Портовая деятельность",
    "Право",
    "Предпринимательство",
    "Преподавание",
    "Природа",
    "Продажи",
    "Промышленное производство",
    "Психология",
    "Публичные выступления",
    "Путешествия",
    "Разработка программного обеспечения",
    "Реклама",
    "Рекрутинг",
    "Робототехника",
    "Розничная торговля",
    "Рукоделие",
    "Садоводство",
    "Саморазвитие",
    "Связи с общественностью",
    "Сделай сам",
    "Социальная работа",
    "Социальное предпринимательство",
    "Стартапы",
    "Стратегия",
    "Страхование",
    "Строительство",
    "Судостроение",
    "Танцы",
    "Театр",
    "Теннис",
    "Технологии",
    "Транспорт",
    "Туризм и гостиничный бизнес",
    "Управление качеством",
    "Управление персоналом",
    "Управление продуктами",
    "Управление проектами",
    "Устойчивое развитие",
    "Устойчивый образ жизни",
    "Фармацевтика",
    "Философия",
    "Финансы",
    "Фитнес",
    "Фото и видео",
    "Фотография",
    "Футбол",
    "Цифровая трансформация",
    "Цифровой маркетинг",
    "Чтение",
    "Шахматы",
    "Экология",
    "Экономика",
    "Электронная коммерция",
    "Электротехника и электроника",
    "Энергетика",
    "Языки",
)
COMMUNITY_PROFILE_TAGS: tuple[tuple[str, str], ...] = tuple(
    (label, label) for label in _COMMUNITY_PROFILE_TAG_LABELS
)

# Alles, was der Management-Command anlegt. Das Startvokabular steht vorn: Bei
# einer Namenskollision gewinnt der erste Eintrag (sein Label).
ALL_PROFILE_TAGS: tuple[tuple[str, str], ...] = (
    INITIAL_PROFILE_TAGS + COMMUNITY_PROFILE_TAGS
)


def find_name_collisions(
    vocabulary: Iterable[tuple[str, str]],
) -> dict[str, list[str]]:
    """
    Kanonische Namen, auf die mehr als ein Eintrag fällt, mit allen Labels.

    get_or_create legt pro Name nur einen Tag an. Weichen die Labels
    voneinander ab, geht eine Schreibweise still verloren – das soll der
    Command sichtbar machen.
    """
    labels_by_name: dict[str, list[str]] = defaultdict(list)
    for raw_name, label in vocabulary:
        labels_by_name[parse_hashtag(raw_name)].append(label)
    return {name: labels for name, labels in labels_by_name.items() if len(labels) > 1}


def seed_profile_tags(
    tag_model, vocabulary: Iterable[tuple[str, str]] = INITIAL_PROFILE_TAGS
) -> tuple[int, int]:
    """
    Legt das Vokabular an, ohne Bestehendes zu verändern.

    Ein erneuter Lauf ergänzt nur, was fehlt. Bestehende Tags bleiben unangetastet
    insbesondere is_active und ein im Admin angepasstes Label, die sonst bei jedem
    Deploy zurückgesetzt werden würden.

    Der Default bleibt INITIAL_PROFILE_TAGS, weil Migration 0006 die Funktion
    ohne Vokabular aufruft – ein anderer Default würde deren Verhalten auf
    frischen Datenbanken nachträglich ändern. Doppelte Namen innerhalb des
    Vokabulars zählen nur einmal.
    """
    created_count = 0
    skipped_count = 0
    seen_names: set[str] = set()

    for raw_name, label in vocabulary:
        name = parse_hashtag(raw_name)
        if name in seen_names:
            continue
        seen_names.add(name)
        _, created = tag_model.objects.get_or_create(
            name=name,
            defaults={"label": label, "slug": name, "is_active": True},
        )
        if created:
            created_count += 1
        else:
            skipped_count += 1

    return created_count, skipped_count
