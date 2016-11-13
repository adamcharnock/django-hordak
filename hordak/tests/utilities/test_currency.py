import os
import six
from datetime import date
from unittest import skipUnless

from moneyed import Money

if six.PY2:
    from mock import patch
else:
    from unittest.mock import patch

import requests_mock

from decimal import Decimal
from django.test import TestCase
from django.test import override_settings
from django.core.cache import cache

from hordak.utilities.currency import _cache_key, _cache_timeout, BaseBackend, FixerBackend, Converter, ExMoney, \
    MoneyCollection

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

    def test_convert_money_date(self):
        money = ExMoney('100', 'GBP', date=date(2000, 5, 15))
        self.assertEqual(
            self.converter.convert(money, 'USD'),
            ExMoney('150', 'USD')
        )

    def test_convert_custom_date(self):
        money = ExMoney('100', 'GBP', date=date(2000, 5, 15))
        self.assertEqual(
            self.converter.convert(money, 'USD', date=date(2015, 5, 15)),
            ExMoney('200', 'USD')
        )

    @skipUnless(os.environ.get('TEST_MAKE_REQUESTS'), 'Making requests disabled')
    def test_against_live_api(self):
        live_converter = Converter(backend=FixerBackend())
        money = ExMoney('100', 'GBP', date=date(2000, 5, 15))
        converted = live_converter.convert(money, 'USD')
        self.assertEqual(round(converted.amount, 2), Decimal('151.32'))
        self.assertEqual(str(converted.currency), 'USD')


@patch('hordak.utilities.currency.converter', Converter(backend=TestBackend()))
class ExMoneyTestCase(CacheTestCase):

    def test_sum(self):
        usd_100 = ExMoney('100', 'USD')
        eur_100 = ExMoney('100', 'EUR')
        gbp_100 = ExMoney('100', 'GBP')

        self.assertEqual(usd_100 + usd_100, ExMoney('200', 'USD'))
        self.assertEqual(usd_100 + eur_100, ExMoney('2100', 'USD'))
        self.assertEqual(eur_100 + usd_100, ExMoney('105', 'EUR'))
        self.assertEqual(eur_100 + gbp_100 + usd_100, ExMoney('115', 'EUR'))

        self.assertEqual((usd_100 + eur_100).converted, True)
        self.assertEqual((eur_100 + usd_100).converted, True)

        self.assertEqual((usd_100 + usd_100).converted, False)
        self.assertEqual((gbp_100 + gbp_100).converted, False)
        self.assertEqual((eur_100 + eur_100).converted, False)


@patch('hordak.utilities.currency.converter', Converter(backend=TestBackend()))
class MoneyCollectionTestCase(CacheTestCase):

    def test_sum_simple(self):
        collection = MoneyCollection('USD')
        collection.add(ExMoney('100', 'EUR', date=date(2000, 5, 15)))
        sum = collection.sum()
        self.assertEqual(sum.amount, Decimal('300'))
        self.assertEqual(str(sum.currency), 'USD')
        self.assertEqual(sum.converted, True)

    def test_sum_to_same(self):
        collection = MoneyCollection('USD')
        collection.add(ExMoney('100', 'USD', date=date(2000, 5, 15)))
        sum = collection.sum()
        self.assertEqual(sum.amount, Decimal('100'))
        self.assertEqual(sum.converted, False)

    def test_sum_many(self):
        collection = MoneyCollection('USD')
        collection.add(ExMoney('100', 'EUR', date=date(2000, 5, 15)))  # 300 USD
        collection.add(ExMoney('100', 'USD', date=date(2000, 5, 15)))  # 100 USD
        collection.add(ExMoney('100', 'GBP', date=date(2000, 5, 15)))  # 150 USD
        sum = collection.sum()
        self.assertEqual(sum.amount, Decimal('550'))
        self.assertEqual(str(sum.currency), 'USD')
        self.assertEqual(sum.converted, True)

    def test_sum_different_dates(self):
        collection = MoneyCollection('USD')
        collection.add(ExMoney('100', 'EUR', date=date(2000, 5, 15)))  # 300 USD
        collection.add(ExMoney('100', 'GBP', date=date(2015, 5, 15)))  # 200 USD
        sum = collection.sum()
        self.assertEqual(sum.amount, Decimal('500'))
        self.assertEqual(str(sum.currency), 'USD')
        self.assertEqual(sum.converted, True)

    def test_sum_explicit_date(self):
        collection = MoneyCollection('USD')
        collection.add(ExMoney('100', 'EUR', date=date(2000, 5, 15)))  # 300 USD
        collection.add(ExMoney('100', 'GBP', date=date(2015, 5, 15)))  # 200 USD
        sum = collection.sum(date=date(2015, 5, 15))
        self.assertEqual(sum.amount, Decimal('2200'))
        self.assertEqual(str(sum.currency), 'USD')
        self.assertEqual(sum.converted, True)
