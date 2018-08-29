from decimal import Decimal

from django.test import TestCase
from hordak.utilities.money import ratio_split


class RatioSplitTestCase(TestCase):
    def test_extra_penny(self):
        values = ratio_split(Decimal("10"), [Decimal("3"), Decimal("3"), Decimal("3")])
        self.assertEqual(values, [Decimal("3.33"), Decimal("3.33"), Decimal("3.34")])

    def test_less_penny(self):
        values = ratio_split(Decimal("8"), [Decimal("3"), Decimal("3"), Decimal("3")])
        self.assertEqual(values, [Decimal("2.67"), Decimal("2.67"), Decimal("2.66")])

    def test_all_equal(self):
        values = ratio_split(Decimal("30"), [Decimal("3"), Decimal("3"), Decimal("3")])
        self.assertEqual(values, [Decimal("10"), Decimal("10"), Decimal("10")])
