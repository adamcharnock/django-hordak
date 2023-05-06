from decimal import Decimal

from django.test import TestCase
from django.utils.translation import activate, get_language, to_locale
from moneyed import Money

from hordak.templatetags.hordak import currency
from hordak.utilities.currency import Balance


class TestHordakTemplateTags(TestCase):
    def setUp(self):
        self.orig_locale = to_locale(get_language())
        activate("en-US")

    def tearDown(self):
        activate(self.orig_locale)

    def test_currency_as_balance(self):
        bal = Balance([Money("10.00", "EUR")])
        assert currency(bal) == "€10.00"

    def test_currency_as_val(self):
        bal = Decimal(10000)
        assert currency(bal) == "10,000"
