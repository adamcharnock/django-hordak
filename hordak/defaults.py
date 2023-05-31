from django.conf import settings


INTERNAL_CURRENCY = getattr(settings, "HORDAK_INTERNAL_CURRENCY", "EUR")

get_internal_currency = INTERNAL_CURRENCY


DEFAULT_CURRENCY = getattr(settings, "DEFAULT_CURRENCY", "EUR")


def default_currency():
    return DEFAULT_CURRENCY


CURRENCIES = getattr(settings, "HORDAK_CURRENCIES", getattr(settings, "CURRENCIES", []))


# Expected to be an array of currencies ["EUR", "USD", "GBP"]
def project_currencies() -> list:
    project_currs = CURRENCIES

    if callable(project_currs):
        return project_currs()

    return project_currs


DECIMAL_PLACES = getattr(settings, "HORDAK_DECIMAL_PLACES", 2)

MAX_DIGITS = getattr(settings, "HORDAK_MAX_DIGITS", 13)
