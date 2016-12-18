from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from hordak.models import Account, StatementImport, StatementLine, Transaction
from hordak.tests.utils import DataProvider
from moneyed import Money


class ReconcileTransactionsViewTestCase(DataProvider, TestCase):

    def setUp(self):
        self.view_url = reverse('transactions_reconcile')

        self.bank_account = self.account(is_bank_account=True, type=Account.TYPES.asset)
        self.income_account = self.account(is_bank_account=False, type=Account.TYPES.income)

        statement_import = StatementImport.objects.create(bank_account=self.bank_account)

        self.line1 = StatementLine.objects.create(
            date='2000-01-01',
            statement_import=statement_import,
            amount=Decimal('100.16'),
            description='Item description 1',
        )

        self.line2 = StatementLine.objects.create(
            date='2000-01-03',
            statement_import=statement_import,
            amount=Decimal('-50.12'),
            description='Item description 2',
        )

        self.line3 = StatementLine.objects.create(
            date='2000-01-06',
            statement_import=statement_import,
            amount=Decimal('40.35'),
            description='Item description 3',
        )

    def test_get(self):
        response = self.client.get(self.view_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['statement_lines'].count(), 3)
        self.assertNotIn('transaction_form', response.context)
        self.assertNotIn('leg_formset', response.context)

    def test_get_reconcile(self):
        response = self.client.get(self.view_url, data=dict(
            reconcile=self.line1.uuid
        ))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['statement_lines'].count(), 3)
        self.assertTrue(response.context['transaction_form'])
        self.assertTrue(response.context['leg_formset'])

        transaction_form = response.context['transaction_form']
        self.assertEqual(transaction_form.initial['description'], 'Item description 1')

        leg_formset = response.context['leg_formset']
        self.assertEqual(leg_formset.forms[0].initial['amount'], Money('100.16', 'EUR'))

    def test_post_reconcile_valid_one(self):
        response = self.client.post(self.view_url, data={
            'reconcile': self.line1.uuid,
            'description': 'Test transaction',

            'legs-INITIAL_FORMS': '0',
            'legs-TOTAL_FORMS': '2',

            'legs-0-amount_0': '100.16',
            'legs-0-amount_1': 'EUR',
            'legs-0-account': self.income_account.uuid,
            'legs-0-id': '',
        })

        if 'transaction_form' in response.context:
            self.assertFalse(response.context['transaction_form'].errors)
            self.assertFalse(response.context['leg_formset'].non_form_errors())
            self.assertFalse(response.context['leg_formset'].errors)

        self.line1.refresh_from_db()

        self.assertEqual(Transaction.objects.count(), 1)
        transaction = Transaction.objects.get()

        self.assertEqual(transaction.description, 'Test transaction')
        self.assertEqual(self.line1.transaction, transaction)

        self.assertEqual(transaction.legs.count(), 2)
        self.assertEqual(transaction.legs.filter(account=self.bank_account).count(), 1)
        self.assertEqual(transaction.legs.filter(account=self.income_account).count(), 1)

        leg_in = transaction.legs.get(account=self.bank_account)
        leg_out = transaction.legs.get(account=self.income_account)

        self.assertEqual(leg_in.amount, Money('-100.16', 'EUR'))
        self.assertEqual(leg_in.account, self.bank_account)

        self.assertEqual(leg_out.amount, Money('100.16', 'EUR'))
        self.assertEqual(leg_out.account, self.income_account)

        self.assertNotIn('leg_formset', response.context)
        self.assertNotIn('transaction_form', response.context)

    def test_post_reconcile_valid_two(self):
        response = self.client.post(self.view_url, data={
            'reconcile': self.line1.uuid,
            'description': 'Test transaction',

            'legs-INITIAL_FORMS': '0',
            'legs-TOTAL_FORMS': '2',

            'legs-0-amount_0': '50.16',
            'legs-0-amount_1': 'EUR',
            'legs-0-account': self.income_account.uuid,
            'legs-0-id': '',

            'legs-1-amount_0': '50.00',
            'legs-1-amount_1': 'EUR',
            'legs-1-account': self.income_account.uuid,
            'legs-1-id': '',
        })

        if 'transaction_form' in response.context:
            self.assertFalse(response.context['transaction_form'].errors)
            self.assertFalse(response.context['leg_formset'].errors)

        transaction = Transaction.objects.get()
        self.assertEqual(transaction.legs.count(), 3)

    def test_post_reconcile_invalid_amounts(self):
        response = self.client.post(self.view_url, data={
            'reconcile': self.line1.uuid,
            'description': 'Test transaction',

            'legs-INITIAL_FORMS': '0',
            'legs-TOTAL_FORMS': '2',

            'legs-0-amount_0': '1',
            'legs-0-amount_1': 'EUR',
            'legs-0-account': self.income_account.uuid,
            'legs-0-id': '',
        })
        self.assertEqual(Transaction.objects.count(), 0)

        leg_formset = response.context['leg_formset']
        self.assertEqual(leg_formset.non_form_errors(), ['Amounts must add up to 100.16'])
        self.assertIn('Amounts must add up to 100.16', response.content.decode('utf8'))

    def test_post_reconcile_negative_amount(self):
        response = self.client.post(self.view_url, data={
            'reconcile': self.line1.uuid,
            'description': 'Test transaction',

            'legs-INITIAL_FORMS': '0',
            'legs-TOTAL_FORMS': '2',

            'legs-0-amount_0': '-1',
            'legs-0-amount_1': 'EUR',
            'legs-0-account': self.income_account.uuid,
            'legs-0-id': '',
        })
        self.assertEqual(Transaction.objects.count(), 0)

        leg_formset = response.context['leg_formset']
        self.assertEqual(leg_formset.errors[0]['amount'], ['Amount must be greater than zero'])

    def test_post_reconcile_zero_amount(self):
        response = self.client.post(self.view_url, data={
            'reconcile': self.line1.uuid,
            'description': 'Test transaction',

            'legs-INITIAL_FORMS': '0',
            'legs-TOTAL_FORMS': '2',

            'legs-0-amount_0': '0',
            'legs-0-amount_1': 'EUR',
            'legs-0-account': self.income_account.uuid,
            'legs-0-id': '',
        })
        self.assertEqual(Transaction.objects.count(), 0)

        leg_formset = response.context['leg_formset']
        self.assertEqual(leg_formset.errors[0]['amount'], ['Amount must be greater than zero'])

    def test_post_reconcile_negative(self):
        """Check that that positive amounts will be correctly used to reconcile negative amounts"""
        response = self.client.post(self.view_url, data={
            'reconcile': self.line2.uuid,
            'description': 'Test transaction',

            'legs-INITIAL_FORMS': '0',
            'legs-TOTAL_FORMS': '2',

            'legs-0-amount_0': '50.12',
            'legs-0-amount_1': 'EUR',
            'legs-0-account': self.income_account.uuid,
            'legs-0-id': '',
        })

        if 'transaction_form' in response.context:
            self.assertFalse(response.context['transaction_form'].errors)
            self.assertFalse(response.context['leg_formset'].errors)

        transaction = Transaction.objects.get()
        self.assertEqual(transaction.legs.count(), 2)
