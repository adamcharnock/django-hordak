from django.conf import settings

INTERNAL_CURRENCY = getattr(settings, 'HORDAK_INTERNAL_CURRENCY', 'EUR')
