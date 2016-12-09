import os
import six
from datetime import date
from unittest import skipUnless

from moneyed import Money

from hordak.exceptions import LossyCalculationError

if six.PY2:
    from mock import patch
else:
    from unittest.mock import patch

import requests_mock

from decimal import Decimal
from django.test import TestCase
from django.test import override_settings
from django.core.cache import cache

from hordak.utilities.currency import _cache_key, _cache_timeout, BaseBackend, FixerBackend, Converter, Balance

DUMMY_CACHE = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}


class TestBackend(BaseBackend):
    supported_currencies = ['EUR', 'GBP', 'USD']

    def _get_rate(self, currency, date_):
        if date_ < date(2010, 1, 1):
            rates = dict(
                GBP=Decimal(2),
                USD=Decimal(3),
            )
        else:
            rates = dict(
                GBP=Decimal(10),
                USD=Decimal(20),
            )
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
        self.assertEqual(_cache_key('GBP', date(2000, 5, 15)), 'EUR-GBP-2000-05-15')

    def test_cache_timeout(self):
        one_day = 86400
        self.assertEqual(_cache_timeout(date.today()), one_day)
        self.assertEqual(_cache_timeout(date(2000, 5, 15)), None)


class BaseBackendTestCase(CacheTestCase):

    @patch('hordak.defaults.INTERNAL_CURRENCY', 'XXX')
    def test_bad_currency(self):
        with self.assertRaises(ValueError):
            TestBackend()

    def test_cache_rate(self):
        backend = TestBackend()
        backend.cache_rate('GBP', date(2000, 5, 15), Decimal('0.1234'))
        self.assertEqual(cache.get('EUR-GBP-2000-05-15'), '0.1234')

    def test_get_rate(self):
        backend = TestBackend()
        self.assertEqual(
            backend.get_rate('GBP', date(2000, 5, 15)),
            Decimal(2)
        )
        self.assertEqual(cache.get('EUR-GBP-2000-05-15'), '2')
        self.assertEqual(
            backend.get_rate('USD', date(2015, 5, 15)),
            Decimal(20)
        )
        self.assertEqual(cache.get('EUR-USD-2015-05-15'), '20')

    def test_get_rate_cached(self):
        backend = TestBackend()
        cache.set('EUR-GBP-2000-05-15', '0.123')
        self.assertEqual(
            backend.get_rate('GBP', date(2000, 5, 15)),
            Decimal('0.123')
        )

    def test_ensure_supported(self):
        with self.assertRaises(ValueError):
            TestBackend().ensure_supported('XXX')


class FixerBackendTestCase(CacheTestCase):

    def test_get_rate(self):
        with requests_mock.mock() as m:
            m.get('https://api.fixer.io/2000-05-15?base=EUR', json={
                'base': 'EUR',
                'date': '2000-05-15',
                'rates': {
                    'GBP': 5.1234,
                    'USD': 6.1234,
                }
            })
            rate = FixerBackend().get_rate('GBP', date(2000, 5, 15))
        self.assertEqual(rate, Decimal('5.1234'))
        self.assertEqual(cache.get('EUR-GBP-2000-05-15'), '5.1234')
        self.assertEqual(cache.get('EUR-USD-2000-05-15'), '6.1234')

    def test_get_rate_use_returned_date(self):
        """Make sure we cache against the date provided by fixer, not the date we asked for

        This is important when requesting dates for in the future. We would not want to
        cache rates against incorrect dates.
        """
        with requests_mock.mock() as m:
            m.get('https://api.fixer.io/2100-05-15?base=EUR', json={
                'base': 'EUR',
                'date': '2000-05-15',
                'rates': {
                    'GBP': 5.1234,
                    'USD': 6.1234,
                }
            })
            FixerBackend().get_rate('GBP', date(2100, 5, 15))
        self.assertEqual(cache.get('EUR-GBP-2000-05-15'), '5.1234')
        self.assertEqual(cache.get('EUR-USD-2000-05-15'), '6.1234')


class ConverterTestCase(CacheTestCase):

    def setUp(self):
        super(ConverterTestCase, self).setUp()
        self.converter = Converter(backend=TestBackend())

    def test_rate_gbp_usd(self):
        self.assertEqual(
            self.converter.rate('GBP', 'USD', date(2000, 5, 15)),
            Decimal('1.5')
        )

    def test_rate_usd_gbp(self):
        self.assertEqual(
            self.converter.rate('USD', 'GBP', date(2000, 5, 15)),
            Decimal('0.6666666666666666666666666666')
        )


@override_settings(CACHES=DUMMY_CACHE)
@patch('hordak.utilities.currency.converter', Converter(backend=TestBackend()))
class BalanceTestCase(CacheTestCase):

    def setUp(self):
        self.balance_1 = Balance([Money(100, 'USD'), Money(100, 'EUR')])
        self.balance_2 = Balance([Money(80, 'USD'), Money(150, 'GBP')])
        self.balance_neg = Balance([Money(-10, 'USD'), Money(-20, 'GBP')])

    def test_unique_currency(self):
        with self.assertRaises(ValueError):
            Balance([Money(0, 'USD'), Money(0, 'USD')])

    def test_init_args(self):
        b = Balance(100, 'USD', 200, 'EUR', 300, 'GBP')
        return
        self.assertEqual(b['USD'].amount, 100)
        self.assertEqual(b['EUR'].amount, 200)
        self.assertEqual(b['GBP'].amount, 300)

    def test_add(self):
        b = self.balance_1 + self.balance_2
        self.assertEqual(b['USD'].amount, 180)
        self.assertEqual(b['EUR'].amount, 100)
        self.assertEqual(b['GBP'].amount, 150)

    def test_sub(self):
        b = self.balance_1 - self.balance_2
        self.assertEqual(b['USD'].amount, 20)
        self.assertEqual(b['EUR'].amount, 100)
        self.assertEqual(b['GBP'].amount, -150)

    def test_sub_rev(self):
        b = self.balance_2 - self.balance_1
        self.assertEqual(b['USD'].amount, -20)
        self.assertEqual(b['EUR'].amount, -100)
        self.assertEqual(b['GBP'].amount, 150)

    def test_neg(self):
        b = -self.balance_1
        self.assertEqual(b['USD'].amount, -100)
        self.assertEqual(b['EUR'].amount, -100)
        self.assertEqual(b['GBP'].amount, 0)

    def test_pos(self):
        b = +self.balance_1
        self.assertEqual(b['USD'].amount, 100)
        self.assertEqual(b['EUR'].amount, 100)
        self.assertEqual(b['GBP'].amount, 0)

    def test_mul(self):
        b = self.balance_1 * 2
        self.assertEqual(b['USD'].amount, 200)
        self.assertEqual(b['EUR'].amount, 200)
        self.assertEqual(b['GBP'].amount, 0)

    def test_mul_error(self):
        with self.assertRaises(LossyCalculationError):
            self.balance_1 / 1.123

    def test_div(self):
        b = self.balance_1 / 2
        self.assertEqual(b['USD'].amount, 50)
        self.assertEqual(b['EUR'].amount, 50)
        self.assertEqual(b['GBP'].amount, 0)

    def test_div_error(self):
        with self.assertRaises(LossyCalculationError):
            self.balance_1 / 1.123

    def test_abs(self):
        b = abs(self.balance_neg)
        self.assertEqual(b['USD'].amount, 10)
        self.assertEqual(b['EUR'].amount, 0)
        self.assertEqual(b['GBP'].amount, 20)

    def test_bool(self):
        self.assertEqual(bool(Balance()), False)
        self.assertEqual(bool(Balance([Money(0, 'USD')])), False)
        self.assertEqual(bool(self.balance_1), True)

    def test_eq(self):
        self.assertEqual(Balance() == Balance(), True)
        self.assertEqual(Balance([Money(0, 'USD')]) == Balance(), True)

        self.assertEqual(self.balance_1 == +self.balance_1, True)
        self.assertEqual(self.balance_1 == self.balance_2, False)
        self.assertEqual(Balance([Money(100, 'USD')]) == Balance([Money(100, 'USD')]), True)
        self.assertEqual(Balance([Money(100, 'USD'), Money(0, 'EUR')]) == Balance([Money(100, 'USD')]), True)

        self.assertEqual(Balance([Money(100, 'USD'), Money(10, 'EUR')]) == Balance([Money(100, 'USD')]), False)

    def test_eq_zero(self):
        self.assertEqual(Balance() == 0, True)
        self.assertEqual(Balance([Money(0, 'USD')]) == 0, True)
        self.assertEqual(self.balance_1 == 0, False)

    def test_neq(self):
        self.assertEqual(Balance() != Balance(), False)
        self.assertEqual(Balance([Money(0, 'USD')]) != Balance(), False)

        self.assertEqual(self.balance_1 != +self.balance_1, False)
        self.assertEqual(self.balance_1 != self.balance_2, True)
        self.assertEqual(Balance([Money(100, 'USD')]) != Balance([Money(100, 'USD')]), False)
        self.assertEqual(Balance([Money(100, 'USD'), Money(0, 'EUR')]) != Balance([Money(100, 'USD')]), False)

        self.assertEqual(Balance([Money(100, 'USD'), Money(10, 'EUR')]) != Balance([Money(100, 'USD')]), True)

    def test_lt(self):
        self.assertEqual(
            Balance() < Balance(),
            False
        )
        self.assertEqual(
            self.balance_1 < self.balance_1,
            False
        )
        self.assertEqual(
            Balance() < Balance([Money(1, 'USD')]),
            True
        )
        self.assertEqual(
            Balance([Money(1, 'USD')]) < Balance(),
            False
        )
        self.assertEqual(
            Balance([Money(1, 'USD')]) < Balance([Money(1, 'EUR')]),
            True
        )

    def test_gt(self):
        self.assertEqual(
            Balance() > Balance(),
            False
        )
        self.assertEqual(
            self.balance_1 > self.balance_1,
            False
        )
        self.assertEqual(
            Balance() > Balance([Money(1, 'USD')]),
            False
        )
        self.assertEqual(
            Balance([Money(1, 'USD')]) > Balance(),
            True
        )
        self.assertEqual(
            Balance([Money(1, 'USD')]) > Balance([Money(1, 'EUR')]),
            False
        )

    def test_lte(self):
        self.assertEqual(
            Balance() <= Balance(),
            True
        )
        self.assertEqual(
            self.balance_1 <= self.balance_1,
            True
        )
        self.assertEqual(
            Balance() <= Balance([Money(1, 'USD')]),
            True
        )
        self.assertEqual(
            Balance([Money(1, 'USD')]) <= Balance(),
            False
        )
        self.assertEqual(
            Balance([Money(1, 'USD')]) <= Balance([Money(1, 'EUR')]),
            True
        )

    def test_gte(self):
        self.assertEqual(
            Balance() >= Balance(),
            True
        )
        self.assertEqual(
            self.balance_1 >= self.balance_1,
            True
        )
        self.assertEqual(
            Balance() >= Balance([Money(1, 'USD')]),
            False
        )
        self.assertEqual(
            Balance([Money(1, 'USD')]) >= Balance(),
            True
        )
        self.assertEqual(
            Balance([Money(1, 'USD')]) >= Balance([Money(1, 'EUR')]),
            False
        )

    def test_normalise(self):
        self.assertEqual(self.balance_1.normalise('EUR'), Balance([Money(105, 'EUR')]))
