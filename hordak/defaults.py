from django.conf import settings


INTERNAL_CURRENCY = getattr(settings, "HORDAK_INTERNAL_CURRENCY", "EUR")


def get_internal_currency():
    return INTERNAL_CURRENCY


DEFAULT_CURRENCY = getattr(settings, "DEFAULT_CURRENCY", "EUR")

CURRENCIES = getattr(settings, "HORDAK_CURRENCIES", getattr(settings, "CURRENCIES", []))


def default_currencies():
    default_currs = getattr(
        settings, "HORDAK_CURRENCIES", getattr(settings, "CURRENCIES", [])
    )

    if callable(default_currs):
        return default_currs()

    return default_currs


DECIMAL_PLACES = getattr(settings, "HORDAK_DECIMAL_PLACES", 2)

MAX_DIGITS = getattr(settings, "HORDAK_MAX_DIGITS", 13)
