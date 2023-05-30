from django.test import TestCase

from hordak.forms.accounts import AccountForm
from hordak.models import Account


class SimpleTransactionFormTestCase(TestCase):
    def test_valid_data(self):
        form = AccountForm(
            {
                "name": "Foo account",
                "currencies": ["USD", "EUR"],
            }
        )
        self.assertTrue(form.is_valid())
        form.save()

        account = Account.objects.get()
        self.assertEqual(account.name, "Foo account")
        self.assertEqual(account.currencies, ["USD", "EUR"])
        self.assertEqual(account.code, None)

    def test_valid_data_code(self):
        form = AccountForm(
            {
                "name": "Foo account",
                "currencies": ["USD", "EUR"],
                "code": "foo",
            }
        )
        self.assertTrue(form.is_valid())
        form.save()

        account = Account.objects.get()
        self.assertEqual(account.name, "Foo account")
        self.assertEqual(account.currencies, ["USD", "EUR"])
        self.assertEqual(account.code, "foo")

    def test_currency_validation_error(self):
        """Non-existent currency doesn't validate"""
        form = AccountForm(
            {
                "name": "Foo account",
                "currencies": ["FOO"],
            }
        )
        self.assertEqual(
            form.errors,
            {
                "currencies": [
                    "Select a valid choice. " "FOO is not one of the available choices."
                ]
            },
        )

    def test_currencies_old_format(self):
        """Non-existent currency doesn't validate"""
        form = AccountForm(
            {
                "name": "Foo account",
                "currencies": "USD, EUR",
            }
        )
        self.assertIn(
            'Currencies needs to be valid JSON (i.e. ["USD", "EUR"]'
            ' or ["USD"]) - USD, EUR is not valid JSON.',
            form.errors["currencies"],
        )
