from django.db import models, transaction


class GlobalIdentifier(models.Model):
    key = models.CharField(max_length=50, unique=True)
    value = models.BigIntegerField(default=0)

    class Meta:
        verbose_name = "Global Identifier"
        verbose_name_plural = "Global Identifiers"

    def __str__(self) -> str:
        return f"{self.key}={self.value}"

    @staticmethod
    def next(key: str, default=None) -> int:
        """
        Return the next value for the given key.
        On first use, returns `default` (or 1 if not provided).
        """
        with transaction.atomic():
            identifier, created = GlobalIdentifier.objects.get_or_create(
                key=key,
                defaults={"value": default if default is not None else 1},
            )
            if created:
                return identifier.value

            identifier = GlobalIdentifier.objects.select_for_update().get(
                pk=identifier.pk
            )
            identifier.value += 1
            identifier.save(update_fields=["value"])
            return identifier.value

    @staticmethod
    def next_n(key: str, count=1, default=None) -> range:
        """
        Return the next `count` values for the given key as a range.
        """
        if count < 1:
            raise ValueError("count must be at least 1")

        start_default = default if default is not None else 1

        with transaction.atomic():
            identifier, created = GlobalIdentifier.objects.get_or_create(
                key=key,
                defaults={"value": start_default + count - 1},
            )

            if created:
                return range(start_default, start_default + count)

            identifier = GlobalIdentifier.objects.select_for_update().get(
                pk=identifier.pk
            )
            start_value = identifier.value + 1
            identifier.value = start_value + count - 1
            identifier.save(update_fields=["value"])
            return range(start_value, identifier.value + 1)
