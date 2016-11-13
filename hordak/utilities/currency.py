import logging
from decimal import Decimal

import requests
from datetime import date, timedelta
from django.core.cache import cache

from hordak import defaults


_INTERNAL_CURRENCY = 'EUR'

logger = logging.getLogger(__name__)


def _cache_key(currency, date):
    return '{}-{}-{}'.format(_INTERNAL_CURRENCY, currency, date)


def _cache_timeout(date_):
    if date_ == date.today():
        # Cache today's rates for 24 hours only, as we will
        # want to get average dates again once trading is over
        return 3600 * 24
    else:
        # None = cache forever
        return None


class BaseBackend(object):
    supported_currencies = []

    def __init__(self):
        if _INTERNAL_CURRENCY not in self.supported_currencies:
            raise ValueError('Currency specified by INTERNAL_CURRENCY '
                             'is not supported by this backend: '.format(_INTERNAL_CURRENCY))

    def cache_rate(self, currency, date, rate):
        """
        Use the cache rates returned by your backend
        """
        if currency not in self.supported_currencies:
            logger.warn('Tried to cache unsupported currency "{}". Ignoring.'.format(currency))
        else:
            cache.set(_cache_key(currency, date), str(rate), _cache_timeout(date))

    def get_rate(self, currency, date):
        """Get the exchange rate for ``currency`` against ``_INTERNAL_CURRENCY``"""
        if currency == _INTERNAL_CURRENCY:
            return Decimal(1)

        cached = cache.get(_cache_key(currency, date))
        if cached:
            return cached
        else:
            # Expect self._get_rate() to implement caching
            return self._get_rate(currency, date)

    def _get_rate(self, currency, date):
        """Get the exchange rate for ``currency`` against ``_INTERNAL_CURRENCY``

        You should implement this in any custom backend. For each currency
        provided you should call ``self.cache_rate()``.

        Returns:

            Decimal
        """
        raise NotImplementedError()

    def ensure_supported(self, currency):
        if currency not in self.supported_currencies:
            raise ValueError('Currency not supported by backend: {}'.format(currency))



class FixerBackend(BaseBackend):
    """Use fixer.io for currency conversions"""
    supported_currencies = ['AUD', 'BGN', 'BRL', 'CAD', 'CHF', 'CNY', 'CZK', 'DKK', 'GBP', 'HKD', 'HRK', 'HUF', 'IDR',
                            'ILS', 'INR', 'JPY', 'KRW', 'MXN', 'MYR', 'NOK', 'NZD', 'PHP', 'PLN', 'RON', 'RUB', 'SEK',
                            'SGD', 'THB', 'TRY', 'ZAR', 'EUR', 'USD']

    def _get_rate(self, currency, date_):
        self.ensure_supported(currency)
        response = requests.get(
            'https://api.fixer.io/{date}?base={base}'.format(
                base=_INTERNAL_CURRENCY,
                date=date_.strftime('%Y-%m-%d')
            ))
        response.raise_for_status()

        data = response.json(parse_float=Decimal)
        rates = data['rates']
        returned_date = date(*map(int, data['date'].split('-')))
        requested_rate = rates[currency]

        for currency, rate in rates.items():
            self.cache_rate(currency, returned_date, rate)

        return requested_rate


class Converter(object):
    # TODO: Make configurable

    def __init__(self, base_currency=None, backend=FixerBackend()):
        self.base_currency = base_currency or defaults.INTERNAL_CURRENCY
        self.backend = backend

    def convert(self, value, from_currency, to_currency, date):
        # TODO: Update to handle Money values
        return value * self.rate(from_currency, to_currency, date)

    def rate(self, from_currency, to_currency, date):
        """Get the exchange rate between the specified currencies"""
        return self.backend.get_rate(from_currency, date) \
               * \
               (1 / self.backend.get_rate(to_currency, date))


converter = Converter()


class Money(object):

    def __init__(cls, value, currency, context=None):
        converter.backend.ensure_supported(currency)
        # TBA

