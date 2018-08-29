from __future__ import division
import six
from datetime import date
from moneyed import Money

from hordak.exceptions import LossyCalculationError
from hordak.models import Account
from hordak.tests.utils import DataProvider, BalanceUtils

if six.PY2:
    from mock import patch
else:
    from unittest.mock import patch

import requests_mock

from decimal import Decimal
from django.test import TestCase
from django.test import override_settings
from django.core.cache import cache

from hordak.utilities.currency import (
    _cache_key,
    _cache_timeout,
    BaseBackend,
    FixerBackend,
    Converter,
    Balance,
    currency_exchange,
)

DUMMY_CACHE = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}


class TestBackend(BaseBackend):
    supported_currencies = ["EUR", "GBP", "USD"]

    def _get_rate(self, currency, date_):
        if date_ < date(2010, 1, 1):
            rates = dict(GBP=Decimal(2), USD=Decimal(3))
        else:
            rates = dict(GBP=Decimal(10), USD=Decimal(20))
        rate = rates[str(currency)]
        self.cache_rate(currency, date_, rate)
        return rate


@override_settings(CACHES=DUMMY_CACHE)
class CacheTestCase(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()


class FunctionsTestCase(CacheTestCase):
    def test_cache_key(self):
        self.assertEqual(_cache_key("GBP", date(2000, 5, 15)), "EUR-GBP-2000-05-15")

    def test_cache_timeout(self):
        one_day = 86400
        self.assertEqual(_cache_timeout(date.today()), one_day)
        self.assertEqual(_cache_timeout(date(2000, 5, 15)), None)


class BaseBackendTestCase(CacheTestCase):
    @patch("hordak.defaults.INTERNAL_CURRENCY", "XXX")
    def test_bad_currency(self):
        with self.assertRaises(ValueError):
            TestBackend()

    def test_cache_rate(self):
        backend = TestBackend()
        backend.cache_rate("GBP", date(2000, 5, 15), Decimal("0.1234"))
        self.assertEqual(cache.get("EUR-GBP-2000-05-15"), "0.1234")

    def test_get_rate(self):
        backend = TestBackend()
        self.assertEqual(backend.get_rate("GBP", date(2000, 5, 15)), Decimal(2))
        self.assertEqual(cache.get("EUR-GBP-2000-05-15"), "2")
        self.assertEqual(backend.get_rate("USD", date(2015, 5, 15)), Decimal(20))
        self.assertEqual(cache.get("EUR-USD-2015-05-15"), "20")

    def test_get_rate_cached(self):
        backend = TestBackend()
        cache.set("EUR-GBP-2000-05-15", "0.123")
        self.assertEqual(backend.get_rate("GBP", date(2000, 5, 15)), Decimal("0.123"))

    def test_ensure_supported(self):
        with self.assertRaises(ValueError):
            TestBackend().ensure_supported("XXX")


class FixerBackendTestCase(CacheTestCase):
    def test_get_rate(self):
        with requests_mock.mock() as m:
            m.get(
                "https://api.fixer.io/2000-05-15?base=EUR",
                json={"base": "EUR", "date": "2000-05-15", "rates": {"GBP": 5.1234, "USD": 6.1234}},
            )
            rate = FixerBackend().get_rate("GBP", date(2000, 5, 15))
        self.assertEqual(rate, Decimal("5.1234"))
        self.assertEqual(cache.get("EUR-GBP-2000-05-15"), "5.1234")
        self.assertEqual(cache.get("EUR-USD-2000-05-15"), "6.1234")

    def test_get_rate_use_returned_date(self):
        """Make sure we cache against the date provided by fixer, not the date we asked for

        This is important when requesting dates for in the future. We would not want to
        cache rates against incorrect dates.
        """
        with requests_mock.mock() as m:
            m.get(
                "https://api.fixer.io/2100-05-15?base=EUR",
                json={"base": "EUR", "date": "2000-05-15", "rates": {"GBP": 5.1234, "USD": 6.1234}},
            )
            FixerBackend().get_rate("GBP", date(2100, 5, 15))
        self.assertEqual(cache.get("EUR-GBP-2000-05-15"), "5.1234")
        self.assertEqual(cache.get("EUR-USD-2000-05-15"), "6.1234")


class ConverterTestCase(CacheTestCase):
    def setUp(self):
        super(ConverterTestCase, self).setUp()
        self.converter = Converter(backend=TestBackend())

    def test_rate_gbp_usd(self):
        self.assertEqual(self.converter.rate("GBP", "USD", date(2000, 5, 15)), Decimal("1.5"))

    def test_rate_usd_gbp(self):
        self.assertEqual(
            self.converter.rate("USD", "GBP", date(2000, 5, 15)),
            Decimal("0.6666666666666666666666666666"),
        )


@override_settings(CACHES=DUMMY_CACHE)
@patch("hordak.utilities.currency.converter", Converter(backend=TestBackend()))
class BalanceTestCase(CacheTestCase):
    def setUp(self):
        self.balance_1 = Balance([Money(100, "USD"), Money(100, "EUR")])
        self.balance_2 = Balance([Money(80, "USD"), Money(150, "GBP")])
        self.balance_neg = Balance([Money(-10, "USD"), Money(-20, "GBP")])

    def test_unique_currency(self):
        with self.assertRaises(ValueError):
            Balance([Money(0, "USD"), Money(0, "USD")])

    def test_init_args(self):
        b = Balance(100, "USD", 200, "EUR", 300, "GBP")
        return
        self.assertEqual(b["USD"].amount, 100)
        self.assertEqual(b["EUR"].amount, 200)
        self.assertEqual(b["GBP"].amount, 300)

    def test_add(self):
        b = self.balance_1 + self.balance_2
        self.assertEqual(b["USD"].amount, 180)
        self.assertEqual(b["EUR"].amount, 100)
        self.assertEqual(b["GBP"].amount, 150)

    def test_sub(self):
        b = self.balance_1 - self.balance_2
        self.assertEqual(b["USD"].amount, 20)
        self.assertEqual(b["EUR"].amount, 100)
        self.assertEqual(b["GBP"].amount, -150)

    def test_sub_rev(self):
        b = self.balance_2 - self.balance_1
        self.assertEqual(b["USD"].amount, -20)
        self.assertEqual(b["EUR"].amount, -100)
        self.assertEqual(b["GBP"].amount, 150)

    def test_neg(self):
        b = -self.balance_1
        self.assertEqual(b["USD"].amount, -100)
        self.assertEqual(b["EUR"].amount, -100)
        self.assertEqual(b["GBP"].amount, 0)

    def test_pos(self):
        b = +self.balance_1
        self.assertEqual(b["USD"].amount, 100)
        self.assertEqual(b["EUR"].amount, 100)
        self.assertEqual(b["GBP"].amount, 0)

    def test_mul(self):
        b = self.balance_1 * 2
        self.assertEqual(b["USD"].amount, 200)
        self.assertEqual(b["EUR"].amount, 200)
        self.assertEqual(b["GBP"].amount, 0)

    def test_mul_error(self):
        with self.assertRaises(LossyCalculationError):
            self.balance_1 / 1.123

    def test_div(self):
        b = self.balance_1 / 2
        self.assertEqual(b["USD"].amount, 50)
        self.assertEqual(b["EUR"].amount, 50)
        self.assertEqual(b["GBP"].amount, 0)

    def test_div_error(self):
        with self.assertRaises(LossyCalculationError):
            self.balance_1 / 1.123

    def test_abs(self):
        b = abs(self.balance_neg)
        self.assertEqual(b["USD"].amount, 10)
        self.assertEqual(b["EUR"].amount, 0)
        self.assertEqual(b["GBP"].amount, 20)

    def test_bool(self):
        self.assertEqual(bool(Balance()), False)
        self.assertEqual(bool(Balance([Money(0, "USD")])), False)
        self.assertEqual(bool(self.balance_1), True)

    def test_eq(self):
        self.assertEqual(Balance() == Balance(), True)
        self.assertEqual(Balance() == 0, True)
        self.assertEqual(Balance([Money(0, "USD")]) == Balance(), True)

        self.assertEqual(self.balance_1 == +self.balance_1, True)
        self.assertEqual(self.balance_1 == self.balance_2, False)
        self.assertEqual(Balance([Money(100, "USD")]) == Balance([Money(100, "USD")]), True)
        self.assertEqual(
            Balance([Money(100, "USD"), Money(0, "EUR")]) == Balance([Money(100, "USD")]), True
        )

        self.assertEqual(
            Balance([Money(100, "USD"), Money(10, "EUR")]) == Balance([Money(100, "USD")]), False
        )

    def test_eq_zero(self):
        self.assertEqual(Balance() == 0, True)
        self.assertEqual(Balance([Money(0, "USD")]) == 0, True)
        self.assertEqual(self.balance_1 == 0, False)

    def test_neq(self):
        self.assertEqual(Balance() != Balance(), False)
        self.assertEqual(Balance([Money(0, "USD")]) != Balance(), False)

        self.assertEqual(self.balance_1 != +self.balance_1, False)
        self.assertEqual(self.balance_1 != self.balance_2, True)
        self.assertEqual(Balance([Money(100, "USD")]) != Balance([Money(100, "USD")]), False)
        self.assertEqual(
            Balance([Money(100, "USD"), Money(0, "EUR")]) != Balance([Money(100, "USD")]), False
        )

        self.assertEqual(
            Balance([Money(100, "USD"), Money(10, "EUR")]) != Balance([Money(100, "USD")]), True
        )

    def test_lt(self):
        self.assertEqual(Balance() < Balance(), False)
        self.assertEqual(self.balance_1 < self.balance_1, False)
        self.assertEqual(Balance() < Balance([Money(1, "USD")]), True)
        self.assertEqual(Balance([Money(1, "USD")]) < Balance(), False)
        self.assertEqual(Balance([Money(-1, "USD")]) < Balance([Money(1, "USD")]), True)
        self.assertEqual(Balance([Money(1, "USD")]) < Balance([Money(-1, "USD")]), False)
        self.assertEqual(Balance([Money(1, "USD")]) < Balance([Money(10, "EUR")]), True)
        self.assertEqual(Balance([Money(-1, "USD")]) < 0, True)

    def test_lt_shortcut(self):
        self.assertEqual(Balance(1, "USD") < Balance(2, "USD"), True)
        self.assertEqual(Balance(2, "USD") < Balance(1, "USD"), False)

    def test_gt(self):
        self.assertEqual(Balance() > Balance(), False)
        self.assertEqual(self.balance_1 > self.balance_1, False)
        self.assertEqual(Balance() > Balance([Money(1, "USD")]), False)
        self.assertEqual(Balance([Money(1, "USD")]) > Balance(), True)
        self.assertEqual(Balance([Money(-1, "USD")]) > Balance([Money(1, "USD")]), False)
        self.assertEqual(Balance([Money(1, "USD")]) > Balance([Money(-1, "USD")]), True)
        self.assertEqual(Balance([Money(1, "USD")]) > Balance([Money(10, "EUR")]), False)
        self.assertEqual(Balance([Money(1, "USD")]) > 0, True)

    def test_lte(self):
        self.assertEqual(Balance() <= Balance(), True)
        self.assertEqual(self.balance_1 <= self.balance_1, True)
        self.assertEqual(Balance() <= Balance([Money(1, "USD")]), True)
        self.assertEqual(Balance([Money(1, "USD")]) <= Balance(), False)
        self.assertEqual(Balance([Money(1, "USD")]) <= Balance([Money(1, "EUR")]), True)

    def test_gte(self):
        self.assertEqual(Balance() >= Balance(), True)
        self.assertEqual(self.balance_1 >= self.balance_1, True)
        self.assertEqual(Balance() >= Balance([Money(1, "USD")]), False)
        self.assertEqual(Balance([Money(1, "USD")]) >= Balance(), True)
        self.assertEqual(Balance([Money(1, "USD")]) >= Balance([Money(1, "EUR")]), False)

    def test_normalise(self):
        self.assertEqual(self.balance_1.normalise("EUR"), Balance([Money(105, "EUR")]))

    def test_currencies(self):
        self.assertEqual(self.balance_1.currencies(), ["USD", "EUR"])
        self.assertEqual(self.balance_2.currencies(), ["USD", "GBP"])


class CurrencyExchangeTestCase(DataProvider, BalanceUtils, TestCase):
    def test_peter_selinger_tutorial_table_4_4(self):
        """Test the example given by Peter Selinger in his muticurrency accounting tutorial. Table 4.4"""
        cad_cash = self.account(type=Account.TYPES.asset, currencies=["CAD"])
        usd_cash = self.account(type=Account.TYPES.asset, currencies=["USD"])
        initial_capital = self.account(type=Account.TYPES.equity, currencies=["CAD"])
        food = self.account(type=Account.TYPES.expense, currencies=["CAD"])
        trading = self.account(type=Account.TYPES.trading, currencies=["CAD", "USD"])

        # Put CAD 200 into cad_cash
        initial_capital.transfer_to(cad_cash, Money(200, "CAD"))
        self.assertEqual(initial_capital.balance(), Balance(200, "CAD"))
        self.assertEqual(cad_cash.balance(), Balance(200, "CAD"))

        # Exchange CAD 120 to USD 100 (1 USD = 1.20 CAD)
        currency_exchange(cad_cash, Money(120, "CAD"), usd_cash, Money(100, "USD"), trading)
        self.assertEqual(cad_cash.balance(), Balance(80, "CAD"))
        self.assertEqual(usd_cash.balance(), Balance(100, "USD"))
        self.assertEqual(trading.balance(), Balance(100, "USD", -120, "CAD"))

        # Buy food (1 USD = 1.30 CAD)
        currency_exchange(usd_cash, Money(40, "USD"), food, Money(52, "CAD"), trading)
        self.assertEqual(usd_cash.balance(), Balance(60, "USD"))
        self.assertEqual(food.balance(), Balance(52, "CAD"))
        self.assertEqual(trading.balance(), Balance(60, "USD", -68, "CAD"))

        # Exchange all USD back to CAD (1 USD = 1.25 CAD)
        currency_exchange(usd_cash, Money(60, "USD"), cad_cash, Money(75, "CAD"), trading)
        self.assertEqual(cad_cash.balance(), Balance(155, "CAD"))
        self.assertEqual(usd_cash.balance(), Balance(0, "USD"))
        self.assertEqual(trading.balance(), Balance(0, "USD", 7, "CAD"))

        # Buy food in CAD
        cad_cash.transfer_to(food, Money(20, "CAD"))
        self.assertEqual(cad_cash.balance(), Balance(135, "CAD"))
        self.assertEqual(food.balance(), Balance(72, "CAD"))

    def test_fees(self):
        cad_cash = self.account(type=Account.TYPES.asset, currencies=["CAD"])
        usd_cash = self.account(type=Account.TYPES.asset, currencies=["USD"])
        initial_capital = self.account(type=Account.TYPES.equity, currencies=["CAD"])
        trading = self.account(type=Account.TYPES.trading, currencies=["CAD", "USD"])
        banking_fees = self.account(type=Account.TYPES.expense, currencies=["CAD"])

        initial_capital.transfer_to(cad_cash, Money(200, "CAD"))
        currency_exchange(
            source=cad_cash,
            source_amount=Money(120, "CAD"),
            destination=usd_cash,
            destination_amount=Money(100, "USD"),
            trading_account=trading,
            fee_destination=banking_fees,
            fee_amount=Money(1.50, "CAD"),
        )
        self.assertEqual(cad_cash.balance(), Balance(80, "CAD"))
        self.assertEqual(usd_cash.balance(), Balance(100, "USD"))
        self.assertEqual(banking_fees.balance(), Balance(1.50, "CAD"))
