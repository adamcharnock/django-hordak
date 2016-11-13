""" Monetary values and currency conversion

"""
import logging
from decimal import Decimal

import requests
import datetime
from django.core.cache import cache
from moneyed import Money

from hordak import defaults


logger = logging.getLogger(__name__)


def _cache_key(currency, date):
    return '{}-{}-{}'.format(defaults.INTERNAL_CURRENCY, currency, date)


def _cache_timeout(date_):
    if date_ == datetime.date.today():
        # Cache today's rates for 24 hours only, as we will
        # want to get average dates again once trading is over
        return 3600 * 24
    else:
        # None = cache forever
        return None


class BaseBackend(object):
    supported_currencies = []

    def __init__(self):
        if not self.is_supported(defaults.INTERNAL_CURRENCY):
            raise ValueError('Currency specified by INTERNAL_CURRENCY '
                             'is not supported by this backend: '.format(defaults.INTERNAL_CURRENCY))

    def cache_rate(self, currency, date, rate):
        """
        Use the cache rates returned by your backend
        """
        if not self.is_supported(defaults.INTERNAL_CURRENCY):
            logger.info('Tried to cache unsupported currency "{}". Ignoring.'.format(currency))
        else:
            cache.set(_cache_key(currency, date), str(rate), _cache_timeout(date))

    def get_rate(self, currency, date):
        """Get the exchange rate for ``currency`` against ``_INTERNAL_CURRENCY``"""
        if str(currency) == defaults.INTERNAL_CURRENCY:
            return Decimal(1)

        cached = cache.get(_cache_key(currency, date))
        if cached:
            return Decimal(cached)
        else:
            # Expect self._get_rate() to implement caching
            return Decimal(self._get_rate(currency, date))

    def _get_rate(self, currency, date):
        """Get the exchange rate for ``currency`` against ``INTERNAL_CURRENCY``

        You should implement this in any custom backend. For each currency
        provided you should call ``self.cache_rate()``.
        """
        raise NotImplementedError()

    def ensure_supported(self, currency):
        if not self.is_supported(currency):
            raise ValueError('Currency not supported by backend: {}'.format(currency))

    def is_supported(self, currency):
        return str(currency) in self.supported_currencies


class FixerBackend(BaseBackend):
    """Use fixer.io for currency conversions"""
    supported_currencies = ['AUD', 'BGN', 'BRL', 'CAD', 'CHF', 'CNY', 'CZK', 'DKK', 'GBP', 'HKD', 'HRK', 'HUF', 'IDR',
                            'ILS', 'INR', 'JPY', 'KRW', 'MXN', 'MYR', 'NOK', 'NZD', 'PHP', 'PLN', 'RON', 'RUB', 'SEK',
                            'SGD', 'THB', 'TRY', 'ZAR', 'EUR', 'USD']

    def _get_rate(self, currency, date_):
        self.ensure_supported(currency)
        response = requests.get(
            'https://api.fixer.io/{date}?base={base}'.format(
                base=defaults.INTERNAL_CURRENCY,
                date=date_.strftime('%Y-%m-%d')
            ))
        response.raise_for_status()

        data = response.json(parse_float=Decimal)
        rates = data['rates']
        returned_date = datetime.date(*map(int, data['date'].split('-')))
        requested_rate = rates[str(currency)]

        for currency, rate in rates.items():
            self.cache_rate(currency, returned_date, rate)

        return requested_rate


class Converter(object):
    # TODO: Make configurable

    def __init__(self, base_currency=defaults.INTERNAL_CURRENCY, backend=FixerBackend()):
        self.base_currency = base_currency
        self.backend = backend

    def convert(self, money, to_currency, date=None):
        """Convert the given ``money`` to ``to_currency`` using exchange rate on ``date``

        If ``date`` is omitted then the date given by ``money.date`` will be used.
        """
        if str(money.currency) == str(to_currency):
            return money.copy()
        date = money.date if date is None else date
        return ExMoney(
            amount=money.amount * self.rate(money.currency, to_currency, date),
            currency=to_currency,
            date=date,
            converted=True
        )

    def rate(self, from_currency, to_currency, date):
        """Get the exchange rate between the specified currencies"""
        return (1 / self.backend.get_rate(from_currency, date)) \
               * \
               self.backend.get_rate(to_currency, date)


converter = Converter()


class ExMoney(Money):
    """Exchange-rate enabled money

    Will automatically convert as required. Note that the
    ``converted`` property will be set to ``true`` on objects
    which have been through a currency conversion.
    """

    def __init__(self, amount=Decimal('0.0'), currency=defaults.INTERNAL_CURRENCY,
                 date=None, converted=False, auto_convert=True):
        super(ExMoney, self).__init__(amount, currency)
        self.date = date or datetime.date.today()
        self.converted = converted
        self.auto_convert = auto_convert

    @classmethod
    def from_naive_money(cls, money, date):
        if isinstance(money, ExMoney):
            return money
        else:
            return cls(money.amount, money.currency, date=date)

    def copy(self):
        return self.__class__(
            amount=self.amount,
            currency=self.currency,
            date=self.date,
            converted=self.converted,
            auto_convert=self.auto_convert,
        )

    def convert(self, currency, date=None):
        return converter.convert(self, currency, date)

    def _ensure_auto_convert(self):
        if not self.auto_convert:
            raise ValueError(
                'Automatic currency conversion disabled, '
                'cannot convert values with different currencies.')

    def __add__(self, other):
        """Add two money values together, performing conversion as necessary

        Conversion will always be done at the current rate. To
        perform conversion at historical rates use ``MoneyCollection``.
        """
        if isinstance(other, ExMoney):
            if other.currency != self.currency:
                self._ensure_auto_convert()
                other = other.convert(self.currency)
                converted = True
            else:
                converted = self.converted or other.converted
        else:
            converted = self.converted

        added = super(ExMoney, self).__add__(other)
        added.date = self.date
        added.converted = converted
        return added


class MoneyCollection(object):

    def __init__(self, currency=None):
        self._collection = []
        self.currency = currency or defaults.INTERNAL_CURRENCY

    def add(self, money):
        """Add a money value to the collection"""
        self._collection.append(money)

    def sum(self, date=None):
        """Get sum of all values

        Args:
            date (datetime.date): Use the exchange rate at this date (defaults to
                                  the date of each transaction)

        Returns:
            ExMoney: ExMoney instance with ``converted`` set to True
        """
        sum = None
        for money in self._collection:
            converted = converter.convert(money, self.currency, date)
            if sum is None:
                sum = converted
            else:
                sum += converted
        return sum

    @property
    def amount(self):
        return self.sum(date=datetime.date.today())
