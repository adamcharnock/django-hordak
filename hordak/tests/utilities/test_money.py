from decimal import Decimal

from django.test import TestCase
from mock import patch

import hordak.utilities.money
from hordak.utilities.money import ratio_split


# Note: these tests assume that sorting is stable across all Python versions.


@patch.object(hordak.utilities.money, "DECIMAL_PLACES", 2)
class RatioSplitTestCase(TestCase):
    def test_extra_penny(self):
        values = ratio_split(Decimal("10"), [Decimal("3"), Decimal("3"), Decimal("3")])
        self.assertEqual(values, [Decimal("3.34"), Decimal("3.33"), Decimal("3.33")])

    def test_less_penny(self):
        values = ratio_split(Decimal("8"), [Decimal("3"), Decimal("3"), Decimal("3")])
        self.assertEqual(values, [Decimal("2.66"), Decimal("2.67"), Decimal("2.67")])

    def test_pennies(self):
        values = ratio_split(
            Decimal("-11.06"), [Decimal("1"), Decimal("1"), Decimal("1"), Decimal("1")]
        )
        self.assertEqual(
            values,
            [Decimal("-2.77"), Decimal("-2.77"), Decimal("-2.76"), Decimal("-2.76")],
        )

    def test_pennies_zeros(self):
        values = ratio_split(
            Decimal("11.05"), [Decimal("1"), Decimal("1"), Decimal("0")]
        )
        self.assertEqual(values, [Decimal("5.53"), Decimal("5.52"), Decimal("0.00")])

        values = ratio_split(
            Decimal("11.05"), [Decimal("0"), Decimal("1"), Decimal("1")]
        )
        self.assertEqual(values, [Decimal("0.00"), Decimal("5.53"), Decimal("5.52")])

    def test_all_equal(self):
        values = ratio_split(Decimal("30"), [Decimal("3"), Decimal("3"), Decimal("3")])
        self.assertEqual(values, [Decimal("10"), Decimal("10"), Decimal("10")])
