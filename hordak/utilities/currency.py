# -*- coding: utf-8 -*-
"""

Overview
--------

Hordak features multi currency support. Each account in Hordak can support one or more currencies.
Hordak does provide currency conversion functionality, but should be as part of the display logic
only. It is also a good idea to make it clear to users that you are showing converted values.

The preference for Hordak internals is to always store & process values in the intended currency. This
is because currency conversion is an inherently lossy process. Exchange rates vary over time, and rounding
errors mean that currency conversions are not reversible without data loss (e.g. ¥176.51 -> $1.54 -> ¥176.20).

Classes
-------

``Money`` **instances**:

    The ``Money`` class is provided by `moneyd`_ and combines both an amount and a currency into a single value.
    Hordak uses these these as the core unit of monetary value.

``Balance`` **instances (see below for more details)**:

    An account can hold multiple currencies, and a `Balance`_ instance is how we represent this.

    A `Balance`_ may contain one or more ``Money`` objects. There will be precisely one ``Money`` object
    for each currency which the account holds.

    Balance objects may be added, subtracted etc. This will produce a new `Balance`_ object containing a
    union of all the currencies involved in the calculation, even where the result was zero.

    Accounts with ``is_bank_account=True`` may only support a single currency.

Caching
-------

Currency conversion makes use of Django's cache. It is therefore recommended that you
`setup your Django cache`_ to something other than the default in-memory store.

.. _moneyd: https://github.com/limist/py-moneyed
.. _setup your Django cache: https://docs.djangoproject.com/en/1.10/topics/cache/

"""
from __future__ import division
import logging
from decimal import Decimal

import babel.numbers
import requests
import datetime

import six
import copy
from django.core.cache import cache
from django.db import transaction as db_transaction
from django.utils.translation import get_language
from django.utils.translation import to_locale
from moneyed import Money
from moneyed.localization import format_money

from hordak import defaults
from hordak.exceptions import (
    LossyCalculationError,
    BalanceComparisonError,
    TradingAccountRequiredError,
    InvalidFeeCurrency,
    CannotSimplifyError,
)

logger = logging.getLogger(__name__)


def _cache_key(currency, date):
    return "{}-{}-{}".format(defaults.INTERNAL_CURRENCY, currency, date)


def _cache_timeout(date_):
    if date_ == datetime.date.today():
        # Cache today's rates for 24 hours only, as we will
        # want to get average dates again once trading is over
        return 3600 * 24
    else:
        # None = cache forever
        return None


def currency_exchange(
    source,
    source_amount,
    destination,
    destination_amount,
    trading_account,
    fee_destination=None,
    fee_amount=None,
    date=None,
    description=None,
):
    """ Exchange funds from one currency to another

    Use this method to represent a real world currency transfer. Note this
    process doesn't care about exchange rates, only about the value
    of currency going in and out of the transaction.

    You can also record any exchange fees by syphoning off funds to ``fee_account`` of amount ``fee_amount``. Note
    that the free currency must be the same as the source currency.

    Examples:

        For example, imagine our Canadian bank has obligingly transferred 120 CAD into our US bank account.
        We sent CAD 120, and received USD 100. We were also changed 1.50 CAD in fees.

        We can represent this exchange in Hordak as follows::

            from hordak.utilities.currency import currency_exchange

            currency_exchange(
                # Source account and amount
                source=cad_cash,
                source_amount=Money(120, 'CAD'),
                # Destination account and amount
                destination=usd_cash,
                destination_amount=Money(100, 'USD'),
                # Trading account the exchange will be done through
                trading_account=trading,
                # We also incur some fees
                fee_destination=banking_fees,
                fee_amount=Money(1.50, 'CAD')
            )

        We should now find that:

         1. ``cad_cash.balance()`` has decreased by ``CAD 120``
         2. ``usd_cash.balance()`` has increased by ``USD 100``
         3. ``banking_fees.balance()`` is ``CAD 1.50``
         4. ``trading_account.balance()`` is ``USD 100, CAD -120``

        You can perform ``trading_account.normalise()`` to discover your unrealised gains/losses
        on currency traded through that account.

    Args:
        source (Account): The account the funds will be taken from
        source_amount (Money): A ``Money`` instance containing the inbound amount and currency.
        destination (Account): The account the funds will be placed into
        destination_amount (Money): A ``Money`` instance containing the outbound amount and currency
        trading_account (Account): The trading account to be used. The normalised balance of this account will indicate
            gains/losses you have made as part of your activity via this account. Note that the normalised balance
            fluctuates with the current exchange rate.
        fee_destination (Account): Your exchange may incur fees. Specifying this will move incurred fees
            into this account (optional).
        fee_amount (Money): The amount and currency of any incurred fees (optional).
        description (str): Description for the transaction. Will default to describing funds in/out & fees (optional).
        date (datetime.date): The date on which the transaction took place. Defaults to today (optional).

    Returns:
        (Transaction): The transaction created

    See Also:
        You can see the above example in practice in ``CurrencyExchangeTestCase.test_fees`` in `test_currency.py`_.

    .. _test_currency.py: https://github.com/adamcharnock/django-hordak/blob/master/hordak/tests/utilities/test_currency.py
    """
    from hordak.models import Account, Transaction, Leg

    if trading_account.type != Account.TYPES.trading:
        raise TradingAccountRequiredError(
            "Account {} must be a trading account".format(trading_account)
        )

    if (fee_destination or fee_amount) and not (fee_destination and fee_amount):
        raise RuntimeError(
            "You must specify either neither or both fee_destination and fee_amount."
        )

    if fee_amount is None:
        # If fees are not specified then set fee_amount to be zero
        fee_amount = Money(0, source_amount.currency)
    else:
        # If we do have fees then make sure the fee currency matches the source currency
        if fee_amount.currency != source_amount.currency:
            raise InvalidFeeCurrency(
                "Fee amount currency ({}) must match source amount currency ({})".format(
                    fee_amount.currency, source_amount.currency
                )
            )

    # Checks over and done now. Let's create the transaction
    with db_transaction.atomic():
        transaction = Transaction.objects.create(
            date=date or datetime.date.today(),
            description=description
            or "Exchange of {} to {}, incurring {} fees".format(
                source_amount, destination_amount, "no" if fee_amount is None else fee_amount
            ),
        )

        # Source currency into trading account
        Leg.objects.create(transaction=transaction, account=source, amount=source_amount)
        Leg.objects.create(
            transaction=transaction, account=trading_account, amount=-(source_amount - fee_amount)
        )

        # Any fees
        if fee_amount and fee_destination:
            Leg.objects.create(
                transaction=transaction,
                account=fee_destination,
                amount=-fee_amount,
                description="Fees",
            )

        # Destination currency out of trading account
        Leg.objects.create(
            transaction=transaction, account=trading_account, amount=destination_amount
        )
        Leg.objects.create(transaction=transaction, account=destination, amount=-destination_amount)

    return transaction


class BaseBackend(object):
    """ Top-level exchange rate backend

    This should be extended to hook into your preferred exchange rate service.
    The primary method which needs defining is :meth:`_get_rate()`.
    """

    supported_currencies = []

    def __init__(self):
        if not self.is_supported(defaults.INTERNAL_CURRENCY):
            raise ValueError(
                "Currency specified by INTERNAL_CURRENCY "
                "is not supported by this backend: ".format(defaults.INTERNAL_CURRENCY)
            )

    def cache_rate(self, currency, date, rate):
        """
        Cache a rate for future use
        """
        if not self.is_supported(defaults.INTERNAL_CURRENCY):
            logger.info('Tried to cache unsupported currency "{}". Ignoring.'.format(currency))
        else:
            cache.set(_cache_key(currency, date), str(rate), _cache_timeout(date))

    def get_rate(self, currency, date):
        """Get the exchange rate for ``currency`` against ``_INTERNAL_CURRENCY``

        If implementing your own backend, you should probably override :meth:`_get_rate()`
        rather than this.
        """
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

        You should implement this in any custom backend. For each rate
        you should call :meth:`cache_rate()`.

        Normally you will only need to call :meth:`cache_rate()` once. However, some
        services provide multiple exchange rates in a single response,
        in which it will likely be expedient to cache them all.

        .. important::

            Not calling :meth:`cache_rate()` will result in your backend service being called for
            every currency conversion. This could be very slow and may result in your
            software being rate limited (or, if you pay for your exchange rates, you may
            get a big bill).
        """
        raise NotImplementedError()

    def ensure_supported(self, currency):
        if not self.is_supported(currency):
            raise ValueError("Currency not supported by backend: {}".format(currency))

    def is_supported(self, currency):
        return str(currency) in self.supported_currencies


class FixerBackend(BaseBackend):
    """Use fixer.io for currency conversions"""

    supported_currencies = [
        "AUD",
        "BGN",
        "BRL",
        "CAD",
        "CHF",
        "CNY",
        "CZK",
        "DKK",
        "GBP",
        "HKD",
        "HRK",
        "HUF",
        "IDR",
        "ILS",
        "INR",
        "JPY",
        "KRW",
        "MXN",
        "MYR",
        "NOK",
        "NZD",
        "PHP",
        "PLN",
        "RON",
        "RUB",
        "SEK",
        "SGD",
        "THB",
        "TRY",
        "ZAR",
        "EUR",
        "USD",
    ]

    def _get_rate(self, currency, date_):
        self.ensure_supported(currency)
        response = requests.get(
            "https://api.fixer.io/{date}?base={base}".format(
                base=defaults.INTERNAL_CURRENCY, date=date_.strftime("%Y-%m-%d")
            )
        )
        response.raise_for_status()

        data = response.json(parse_float=Decimal)
        rates = data["rates"]
        returned_date = datetime.date(*map(int, data["date"].split("-")))
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
            return copy.copy(money)
        return Money(
            amount=money.amount
            * self.rate(money.currency, to_currency, date or datetime.date.today()),
            currency=to_currency,
        )

    def rate(self, from_currency, to_currency, date):
        """Get the exchange rate between the specified currencies"""
        return (1 / self.backend.get_rate(from_currency, date)) * self.backend.get_rate(
            to_currency, date
        )


converter = Converter()


class Balance(object):
    """An account balance

    Accounts may have multiple currencies. This class represents these multi-currency
    balances and provides math functionality. Balances can be added, subtracted, multiplied,
    divided, absolute'ed, and have their sign changed.

    Examples:

        Example use::

            Balance([Money(100, 'USD'), Money(200, 'EUR')])

            # Or in short form
            Balance(100, 'USD', 200, 'EUR')

    .. important::

        Balances can also be compared, but note that this requires a currency conversion step.
        Therefore it is possible that balances will compare differently as exchange rates
        change over time.

    """

    def __init__(self, _money_obs=None, *args):
        all_args = [_money_obs] + list(args)
        if len(all_args) % 2 == 0:
            _money_obs = []
            for i in range(0, len(all_args) - 1, 2):
                _money_obs.append(Money(all_args[i], all_args[i + 1]))

        self._money_obs = tuple(_money_obs or [])
        self._by_currency = {m.currency.code: m for m in self._money_obs}
        if len(self._by_currency) != len(self._money_obs):
            raise ValueError(
                "Duplicate currency provided. All Money instances must have a unique currency."
            )

    def __str__(self):
        def fmt(money):
            return babel.numbers.format_currency(money.amount, currency=money.currency.code)

        return ", ".join(map(fmt, self._money_obs)) or "No values"

    def __repr__(self):
        return "Balance: {}".format(self.__str__())

    def __getitem__(self, currency):
        if hasattr(currency, "code"):
            currency = currency.code
        elif not isinstance(currency, six.string_types) or len(currency) != 3:
            raise ValueError("Currencies must be a string of length three, not {}".format(currency))

        try:
            return self._by_currency[currency]
        except KeyError:
            return Money(0, currency)

    def __add__(self, other):
        if not isinstance(other, Balance):
            raise TypeError(
                "Can only add/subtract Balance instances, not Balance and {}.".format(type(other))
            )
        by_currency = copy.deepcopy(self._by_currency)
        for other_currency, other_money in other._by_currency.items():
            by_currency[other_currency] = other_money + self[other_currency]
        return self.__class__(by_currency.values())

    def __sub__(self, other):
        return self.__add__(-other)

    def __neg__(self):
        return self.__class__([-m for m in self._money_obs])

    def __pos__(self):
        return self.__class__([+m for m in self._money_obs])

    def __mul__(self, other):
        if isinstance(other, Balance):
            raise TypeError("Cannot multiply two Balance instances.")
        elif isinstance(other, float):
            raise LossyCalculationError(
                "Cannot multiply a Balance by a float. Use a Decimal or an int."
            )
        return self.__class__([m * other for m in self._money_obs])

    def __truediv__(self, other):
        if isinstance(other, Balance):
            raise TypeError("Cannot multiply two Balance instances.")
        elif isinstance(other, float):
            raise LossyCalculationError(
                "Cannot divide a Balance by a float. Use a Decimal or an int."
            )
        return self.__class__([m / other for m in self._money_obs])

    def __abs__(self):
        return self.__class__([abs(m) for m in self._money_obs])

    def __bool__(self):
        return any([bool(m) for m in self._money_obs])

    if six.PY2:
        __nonzero__ = __bool__

    def __eq__(self, other):
        if other == 0:
            # Support comparing to integer/Decimal zero as it is useful
            return not self.__bool__()
        elif not isinstance(other, Balance):
            raise TypeError(
                "Can only compare Balance objects to other "
                "Balance objects, not to type {}".format(type(other))
            )
        return not self - other

    def __ne__(self, other):
        return not self.__eq__(other)

    def __lt__(self, other):
        if isinstance(other, Money):
            other = self.__class__([other])
        # We can compare against non-balance 0-values, but otherwise we have to
        # compare against a Balance (otherwise we won't know what currency we are
        # dealing with)
        if isinstance(other, (float, int, Decimal)) and other == 0:
            other = self.__class__()
        if not isinstance(other, Balance):
            raise BalanceComparisonError(other)

        # If we can confidently simplify the values to
        # -1, 0, and 1, and the values are different, then
        # just compare those.
        try:
            self_simplified = self._simplify()
            other_simplified = other._simplify()
            if self_simplified != other_simplified:
                return self_simplified < other_simplified
        except CannotSimplifyError:
            pass

        if len(self._money_obs) == 1 and self.currencies() == other.currencies():
            # Shortcut if we have a single value with the same currency
            return self._money_obs[0] < other._money_obs[0]
        else:
            money = self.normalise(defaults.INTERNAL_CURRENCY)._money_obs[0]
            other_money = other.normalise(defaults.INTERNAL_CURRENCY)._money_obs[0]
            return money < other_money

    def __gt__(self, other):
        return not self < other and not self == other

    def __le__(self, other):
        return self < other or self == other

    def __ge__(self, other):
        return self > other or self == other

    def monies(self):
        """Get a list of the underlying ``Money`` instances

        Returns:
            ([Money]): A list of zero or money money instances. Currencies will be unique.
        """
        return [copy.copy(m) for m in self._money_obs]

    def currencies(self):
        """Get all currencies with non-zero values"""
        return [m.currency.code for m in self.monies() if m.amount]

    def normalise(self, to_currency):
        """Normalise this balance into a single currency

        Args:
            to_currency (str): Destination currency

        Returns:
            (Balance): A new balance object containing a single Money value in the specified currency
        """
        out = Money(currency=to_currency)
        for money in self._money_obs:
            out += converter.convert(money, to_currency)
        return Balance([out])

    def _is_positive(self):
        return all([m.amount > 0 for m in self.monies()]) and self.monies()

    def _is_negative(self):
        return all([m.amount < 0 for m in self.monies()]) and self.monies()

    def _is_zero(self):
        return not self.monies() or all([m.amount == 0 for m in self.monies()])

    def _simplify(self):
        if self._is_positive():
            return 1
        elif self._is_negative():
            return -1
        elif self._is_zero():
            return 0
        else:
            raise CannotSimplifyError()
