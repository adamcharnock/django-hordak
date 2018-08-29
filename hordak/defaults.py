from django.conf import settings

INTERNAL_CURRENCY = getattr(settings, "HORDAK_INTERNAL_CURRENCY", "EUR")

DEFAULT_CURRENCY = getattr(settings, "DEFAULT_CURRENCY", "EUR")

CURRENCIES = getattr(settings, "CURRENCIES", [])

DECIMAL_PLACES = getattr(settings, "HORDAK_DECIMAL_PLACES", 2)

MAX_DIGITS = getattr(settings, "HORDAK_MAX_DIGITS", 13)
