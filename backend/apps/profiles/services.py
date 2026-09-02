"""
Nachschlagelisten für die Autocomplete Eingabe im Frontend.

Beide Listen sind Vorschläge: Über die Gültigkeit eines Tags
entscheidet weiterhin der Serializer gegen die Allowlist. Hier geht es nur
darum, dem Mitglied die Eingabe abzunehmen.
"""

from django.db.models import Case, Count, IntegerField, Q, QuerySet, When

from .hashtags import normalize_hashtag
from .models import MemberProfile, ProfileTag

# Jede dieser Queries läuft gegen eine wachsende Tabelle und wird pro Tastendruck
# aufgerufen ohne harte Obergrenze wäre das ein offener Tabellenscan.
DEFAULT_SUGGESTION_LIMIT = 20
MAX_SUGGESTION_LIMIT = 50

# Sortierrang: Präfixtreffer stehen vor reinen Teilstring Treffern. Wer "ди"
# tippt, erwartet "дизайн" oben und nicht "медицина".
_PREFIX_RANK = 0
_SUBSTRING_RANK = 1


def resolve_limit(raw_value: str | None) -> int:
    """
    Liest ?limit= und hält es in den erlaubten Grenzen.

    Ein unbrauchbarer Wert führt zum Default statt zu einem Fehler.
    """
    try:
        limit = int(raw_value)
    except (TypeError, ValueError):
        return DEFAULT_SUGGESTION_LIMIT
    if limit < 1:
        return DEFAULT_SUGGESTION_LIMIT
    return min(limit, MAX_SUGGESTION_LIMIT)


def visible_profiles() -> QuerySet[MemberProfile]:
    """
    Die Grundmenge des Verzeichnisses.
    """
    return MemberProfile.objects.filter(
        is_directory_visible=True,
        user__is_active=True,
    )


def suggest_tags(query: str = "", limit: int | None = None) -> list[dict]:
    """
    Liefert Tagvorschläge aus dem aktiven Vokabular.

    Ohne query sind es die meistgenutzten Tags, das Frontend braucht eine
    sinnvolle Startliste, bevor der Nutzer den ersten Buchstaben tippt.
    """
    limit = limit or DEFAULT_SUGGESTION_LIMIT
    query = (query or "").strip()

    # --- Nur Zuordnungen sichtbarer Profile zählen.
    usage_count = Count(
        "tagged_profiles",
        filter=Q(
            tagged_profiles__content_object__is_directory_visible=True,
            tagged_profiles__content_object__user__is_active=True,
        ),
        distinct=True,
    )

    queryset = ProfileTag.objects.filter(is_active=True).annotate(
        usage_count=usage_count
    )

    if query:
        # Auch auf dem Label suchen: Der Nutzer tippt "Веб-разработка", der
        # valide Name lautet "веб_разработка".
        queryset = queryset.filter(
            Q(name__icontains=query) | Q(label__icontains=query)
        ).annotate(
            match_rank=Case(
                When(
                    Q(name__istartswith=query) | Q(label__istartswith=query),
                    then=_PREFIX_RANK,
                ),
                default=_SUBSTRING_RANK,
                output_field=IntegerField(),
            )
        )
        queryset = queryset.order_by("match_rank", "-usage_count", "name")
    else:
        queryset = queryset.order_by("-usage_count", "name")

    return [
        {
            "name": tag.name,
            "label": tag.display_label,
            "hashtag": tag.hashtag,
            "usage_count": tag.usage_count,
        }
        for tag in queryset[:limit]
    ]


def suggest_cities(query: str = "", limit: int | None = None) -> list[dict]:
    """
    Liefert die tatsächlich im Verzeichnis vertretenen Städte.

    city ist ein Freitextfeld, eine Vorschlagsliste soll deshalb zeigen,
    wonach sich überhaupt filtern lässt.
    """
    limit = limit or DEFAULT_SUGGESTION_LIMIT
    query = (query or "").strip()

    queryset = visible_profiles().exclude(city="")
    if query:
        queryset = queryset.filter(city__icontains=query)

    rows = (
        queryset.values("city")
        .annotate(count=Count("id"))
        .order_by("-count", "city")[:limit]
    )

    return [
        {
            "name": row["city"],
            # Leerer Hashtag, wenn sich die Stadt nicht validieren lässt
            # die Stadt bleibt trotzdem filterbar.
            "hashtag": normalize_hashtag(row["city"]) or "",
            "count": row["count"],
        }
        for row in rows
    ]
