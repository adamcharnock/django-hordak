from django.test import TestCase
from hordak.forms.transactions import SimpleTransactionForm
from hordak.models import Account, Transaction
from hordak.tests.utils import DataProvider
from hordak.utilities.currency import Balance
from moneyed import Money


class SimpleTransactionFormTestCase(DataProvider, TestCase):

    def setUp(self):
        self.from_account = self.account(name='From Account', type=Account.TYPES.income)
        self.to_account = self.account(name='To Account', type=Account.TYPES.income)

        self.bank = self.account(name='Bank', type=Account.TYPES.asset)
        self.income = self.account(name='Income', type=Account.TYPES.income)
        self.expense = self.account(name='Expense', type=Account.TYPES.expense)

    def test_valid_data(self):
        form = SimpleTransactionForm(dict(
            from_account=self.from_account.uuid,
            to_account=self.to_account.uuid,
            description='A test simple transaction',
            amount_0='50.00',
            amount_1='EUR',
        ))
        self.assertTrue(form.is_valid())
        form.save()

        # Transaction exists with two legs
        transaction = Transaction.objects.get()
        self.assertEqual(transaction.description, 'A test simple transaction')
        self.assertEqual(transaction.legs.count(), 2)

        # Account balances changed
        self.assertEqual(self.from_account.balance(), Balance(-50, 'EUR'))
        self.assertEqual(self.to_account.balance(), Balance(50, 'EUR'))

        # Check transaction legs have amounts set as expected
        from_leg = transaction.legs.get(account=self.from_account)
        to_leg = transaction.legs.get(account=self.to_account)

        self.assertEqual(from_leg.amount, Money(-50, 'EUR'))
        self.assertEqual(to_leg.amount, Money(50, 'EUR'))

    def test_transfer_from_bank_to_income(self):
        """If we move money out of the bank and into an income account, we expect both values to go up"""

        form = SimpleTransactionForm(dict(
            from_account=self.bank.uuid,
            to_account=self.income.uuid,
            description='A test simple transaction',
            amount_0='50.00',
            amount_1='EUR',
        ))
        self.assertTrue(form.is_valid())
        form.save()
        self.assertEqual(self.bank.balance(), Balance(50, 'EUR'))
        self.assertEqual(self.income.balance(), Balance(50, 'EUR'))

    def test_no_from_account(self):
        form = SimpleTransactionForm(dict(
            from_account='',
            to_account=self.to_account.uuid,
            description='A test simple transaction',
            amount_0='50.00',
            amount_1='EUR',
        ))
        self.assertFalse(form.is_valid())

    def test_no_to_account(self):
        form = SimpleTransactionForm(dict(
            from_account=self.from_account.uuid,
            to_account='',
            description='A test simple transaction',
            amount_0='50.00',
            amount_1='EUR',
        ))
        self.assertFalse(form.is_valid())

    def test_no_description_account(self):
        form = SimpleTransactionForm(dict(
            from_account=self.from_account.uuid,
            to_account=self.to_account.uuid,
            description='',
            amount_0='50.00',
            amount_1='EUR',
            amount='50.00',
        ))
        self.assertTrue(form.is_valid())  # valid

    def test_no_amount(self):
        form = SimpleTransactionForm(dict(
            from_account=self.from_account.uuid,
            to_account=self.to_account.uuid,
            description='A test simple transaction',
            amount_0='',
            amount_1='',
        ))
        self.assertFalse(form.is_valid())


