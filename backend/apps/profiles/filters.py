"""
Filter für das Mitgliederverzeichnis.
"""

import django_filters

from .hashtags import normalize_hashtag
from .models import MemberProfile

# Trennzeichen der Tag-Liste im Query-String: ?tags=it,крипта
TAG_FILTER_SEPARATOR = ","


class MemberProfileFilter(django_filters.FilterSet):
    """
    Verzeichnisfilter über Stadt und Tags.
    """

    tags = django_filters.CharFilter(
        method="filter_tags",
        label="Tags (kommasepariert, UND verknüpft)",
    )

    class Meta:
        model = MemberProfile
        fields = ["city"]

    def filter_tags(self, queryset, name, value):
        """
        Filtert auf Profile, die alle genannten Tags tragen.

        Die Werte laufen durch dieselbe Validierung wie beim Speichern, damit
        `?tags=%23IT` und `?tags=it` dasselbe finden. Ein unbekannter oder nicht
        validierbar Wert liefert ein leeres Ergebnis er beschreibt eine
        Menge, die es nicht gibt. Ein Fehler wäre hier die schlechtere Antwort:
        Filterwerte kommen aus der URL und dürfen die Liste nicht zerlegen.
        """
        raw_values = [
            part.strip() for part in value.split(TAG_FILTER_SEPARATOR) if part.strip()
        ]
        if not raw_values:
            return queryset

        for raw_value in raw_values:
            canonical = normalize_hashtag(raw_value)
            if canonical is None:
                return queryset.none()
            # Ein eigener filter() Aufruf pro Tag statt eines __in Filters: Über
            # eine MultiValueRelation erzeugt jeder Aufruf einen eigenen JOIN,
            # und damit muss jede Bedingung von einer anderen Zuordnungszeile
            # erfüllt werden – das ist die gewünschte UND Semantik. Ein
            # gemeinsamer __in Filter wäre zu ODER und bräuchte zusätzlich
            # distinct(), weil ein Profil dann mehrfach im Ergebnis stehen würde.
            queryset = queryset.filter(tags__name=canonical)

        return queryset
