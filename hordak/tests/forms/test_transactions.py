from django.test import TestCase
from hordak.forms.transactions import SimpleTransactionForm, CurrencyTradeForm
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
            date='2000-06-15',
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
            date='2000-06-15',
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
            date='2000-06-15',
        ))
        self.assertFalse(form.is_valid())

    def test_no_to_account(self):
        form = SimpleTransactionForm(dict(
            from_account=self.from_account.uuid,
            to_account='',
            description='A test simple transaction',
            amount_0='50.00',
            amount_1='EUR',
            date='2000-06-15',
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
            date='2000-06-15',
        ))
        self.assertTrue(form.is_valid())  # valid

    def test_no_amount(self):
        form = SimpleTransactionForm(dict(
            from_account=self.from_account.uuid,
            to_account=self.to_account.uuid,
            description='A test simple transaction',
            amount_0='',
            amount_1='',
            date='2000-06-15',
        ))
        self.assertFalse(form.is_valid())


class CurrencyTradeFormTestCase(DataProvider, TestCase):

    def setUp(self):
        self.account_gbp = self.account(name='GBP', type=Account.TYPES.asset, currencies=['GBP'])
        self.account_eur = self.account(name='EUR', type=Account.TYPES.asset, currencies=['EUR'])
        self.account_usd = self.account(name='USD', type=Account.TYPES.asset, currencies=['USD'])

        self.trading_gbp_eur = self.account(name='GBP, EUR', type=Account.TYPES.trading, currencies=['GBP', 'EUR'])
        self.trading_eur_usd = self.account(name='EUR, USD', type=Account.TYPES.trading, currencies=['EUR', 'USD'])
        self.trading_all = self.account(name='GBP, EUR, USD', type=Account.TYPES.trading, currencies=['GBP', 'EUR', 'USD'])

    def test_valid(self):
        form = CurrencyTradeForm(dict(
            source_account=self.account_gbp.uuid,
            source_amount_0='100',
            source_amount_1='GBP',
            trading_account=self.trading_gbp_eur.uuid,
            destination_account=self.account_eur.uuid,
            destination_amount_0='110',
            destination_amount_1='EUR',
        ))
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.assertEqual(self.account_gbp.balance(), Balance('-100', 'GBP'))
        self.assertEqual(self.trading_gbp_eur.balance(), Balance('-100', 'GBP', '110', 'EUR'))
        self.assertEqual(self.account_eur.balance(), Balance('110', 'EUR'))

    def test_no_source_account(self):
        form = CurrencyTradeForm(dict(
            source_account='',
            source_amount_0='100',
            source_amount_1='GBP',
            trading_account=self.trading_gbp_eur.uuid,
            destination_account=self.account_eur.uuid,
            destination_amount_0='110',
            destination_amount_1='EUR',
        ))
        self.assertFalse(form.is_valid())

    def test_no_source_amount(self):
        form = CurrencyTradeForm(dict(
            source_account=self.account_gbp.uuid,
            source_amount_0='',
            source_amount_1='',
            trading_account=self.trading_gbp_eur.uuid,
            destination_account=self.account_eur.uuid,
            destination_amount_0='110',
            destination_amount_1='EUR',
        ))
        self.assertFalse(form.is_valid())

    def test_no_trading_account(self):
        form = CurrencyTradeForm(dict(
            source_account=self.account_gbp.uuid,
            source_amount_0='100',
            source_amount_1='GBP',
            trading_account='',
            destination_account=self.account_eur.uuid,
            destination_amount_0='110',
            destination_amount_1='EUR',
        ))
        self.assertFalse(form.is_valid())

    def test_trading_account_single_currency(self):
        form = CurrencyTradeForm(dict(
            source_account=self.account_gbp.uuid,
            source_amount_0='100',
            source_amount_1='GBP',
            trading_account=self.account(name='trading', type=Account.TYPES.trading, currencies=['GBP']).uuid,
            destination_account=self.account_eur.uuid,
            destination_amount_0='110',
            destination_amount_1='EUR',
        ))
        self.assertFalse(form.is_valid())

    def test_trading_account_no_source_currency(self):
        form = CurrencyTradeForm(dict(
            source_account=self.account_gbp.uuid,
            source_amount_0='100',
            source_amount_1='GBP',
            trading_account=self.account(name='trading', type=Account.TYPES.trading, currencies=['EUR', 'USD']).uuid,
            destination_account=self.account_eur.uuid,
            destination_amount_0='110',
            destination_amount_1='EUR',
        ))
        self.assertFalse(form.is_valid())

    def test_trading_account_no_destination_currency(self):
        form = CurrencyTradeForm(dict(
            source_account=self.account_gbp.uuid,
            source_amount_0='100',
            source_amount_1='GBP',
            trading_account=self.account(name='trading', type=Account.TYPES.trading, currencies=['GBP', 'USD']).uuid,
            destination_account=self.account_eur.uuid,
            destination_amount_0='110',
            destination_amount_1='EUR',
        ))
        self.assertFalse(form.is_valid())

    def test_no_destination_account(self):
        form = CurrencyTradeForm(dict(
            source_account=self.account_gbp.uuid,
            source_amount_0='100',
            source_amount_1='GBP',
            trading_account=self.trading_gbp_eur.uuid,
            destination_account='',
            destination_amount_0='110',
            destination_amount_1='EUR',
        ))
        self.assertFalse(form.is_valid())

    def test_no_destination_amount(self):
        form = CurrencyTradeForm(dict(
            source_account=self.account_gbp.uuid,
            source_amount_0='100',
            source_amount_1='GBP',
            trading_account=self.trading_gbp_eur.uuid,
            destination_account=self.account_eur.uuid,
            destination_amount_0='',
            destination_amount_1='',
        ))
        self.assertFalse(form.is_valid())
