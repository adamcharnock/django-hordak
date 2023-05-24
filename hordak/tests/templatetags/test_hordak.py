from decimal import Decimal

from django.test import TestCase
from moneyed import Money

from hordak.templatetags.hordak import currency
from hordak.tests.utils import TestLocaleMixin
from hordak.utilities.currency import Balance


class TestHordakTemplateTags(TestLocaleMixin, TestCase):
    def test_currency_as_balance(self):
        bal = Balance([Money("10.00", "EUR")])
        assert currency(bal) == "€10.00"

    def test_currency_as_val(self):
        bal = Decimal(10000)
        assert currency(bal) == "10,000"
