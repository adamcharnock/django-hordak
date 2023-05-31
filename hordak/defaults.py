from django.conf import settings


INTERNAL_CURRENCY = getattr(settings, "HORDAK_INTERNAL_CURRENCY", "EUR")


def get_internal_currency():
    return INTERNAL_CURRENCY


DEFAULT_CURRENCY = getattr(settings, "DEFAULT_CURRENCY", "EUR")


def default_currency():
    return DEFAULT_CURRENCY


CURRENCIES = getattr(settings, "HORDAK_CURRENCIES", getattr(settings, "CURRENCIES", []))


# Expected to be an array of currencies ["EUR", "USD", "GBP"]
def project_currencies() -> list:
    default_currs = getattr(
        settings, "HORDAK_CURRENCIES", getattr(settings, "CURRENCIES", [])
    )

    if callable(default_currs):
        return default_currs()

    return default_currs


DECIMAL_PLACES = getattr(settings, "HORDAK_DECIMAL_PLACES", 2)

MAX_DIGITS = getattr(settings, "HORDAK_MAX_DIGITS", 13)
