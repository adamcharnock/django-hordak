from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from hordak.models import Account, StatementImport, StatementLine, Transaction
from hordak.tests.utils import DataProvider
from moneyed import Money

from hordak.utilities.currency import Balance


class TransactionCreateViewTestCase(DataProvider, TestCase):
    def setUp(self):
        self.view_url = reverse("hordak:transactions_create")
        self.login()

        self.bank_account = self.account(is_bank_account=True, type=Account.TYPES.asset)
        self.income_account = self.account(is_bank_account=False, type=Account.TYPES.income)

    def test_get(self):
        response = self.client.get(self.view_url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)

    @patch("hordak.forms.transactions.DEFAULT_CURRENCY", "GBP")
    @patch("hordak.forms.transactions.CURRENCIES", ["EUR", "USD"])
    def test_get_currency_choices(self):
        response = self.client.get(self.view_url)
        self.assertEqual(response.status_code, 200)
        amount_field = response.context["form"]["amount"]
        self.assertEqual(len(amount_field.field.widget.widgets[1].choices), 3)

    def test_submit(self):
        # more checks done in form unit tests
        response = self.client.post(
            self.view_url,
            data=dict(
                from_account=self.bank_account.uuid,
                to_account=self.income_account.uuid,
                amount_0="123.45",
                amount_1="EUR",
                date="2000-06-15",
                description="Test description",
            ),
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/")
        self.assertEqual(self.bank_account.balance(), Balance("123.45", "EUR"))
        self.assertEqual(self.income_account.balance(), Balance("123.45", "EUR"))

        transaction = Transaction.objects.get()
        self.assertEqual(str(transaction.date), "2000-06-15")
        self.assertEqual(transaction.description, "Test description")


class TransactionDeleteViewTestCase(DataProvider, TestCase):
    def setUp(self):
        self.login()

        self.bank_account = self.account(
            is_bank_account=True, type=Account.TYPES.asset, currencies=["GBP"]
        )
        self.income_account = self.account(
            is_bank_account=False, type=Account.TYPES.income, currencies=["GBP"]
        )
        self.transaction = self.bank_account.transfer_to(self.income_account, Money(100, "GBP"))

        self.view_url = reverse("hordak:transactions_delete", args=[self.transaction.uuid])

    def test_get(self):
        response = self.client.get(self.view_url)
        self.assertEqual(response.status_code, 200)

    def test_post(self):
        response = self.client.post(self.view_url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Transaction.objects.count(), 0)


class CurrencyTradeView(DataProvider, TestCase):
    def setUp(self):
        self.view_url = reverse("hordak:currency_trade")
        self.login()

        self.account_gbp = self.account(name="GBP", type=Account.TYPES.asset, currencies=["GBP"])
        self.account_eur = self.account(name="EUR", type=Account.TYPES.asset, currencies=["EUR"])
        self.account_usd = self.account(name="USD", type=Account.TYPES.asset, currencies=["USD"])

        self.trading_gbp_eur = self.account(
            name="GBP, EUR", type=Account.TYPES.trading, currencies=["GBP", "EUR"]
        )
        self.trading_eur_usd = self.account(
            name="EUR, USD", type=Account.TYPES.trading, currencies=["EUR", "USD"]
        )
        self.trading_all = self.account(
            name="GBP, EUR, USD", type=Account.TYPES.trading, currencies=["GBP", "EUR", "USD"]
        )

    def test_get(self):
        response = self.client.get(self.view_url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)

    def test_submit(self):
        # more checks done in form unit tests
        response = self.client.post(
            self.view_url,
            data=dict(
                source_account=self.account_gbp.uuid,
                source_amount_0="100",
                source_amount_1="GBP",
                trading_account=self.trading_gbp_eur.uuid,
                destination_account=self.account_eur.uuid,
                destination_amount_0="110",
                destination_amount_1="EUR",
            ),
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.account_gbp.balance(), Balance("-100", "GBP"))
        self.assertEqual(self.trading_gbp_eur.balance(), Balance("-100", "GBP", "110", "EUR"))
        self.assertEqual(self.account_eur.balance(), Balance("110", "EUR"))


class ReconcileTransactionsViewTestCase(DataProvider, TestCase):
    def setUp(self):
        self.view_url = reverse("hordak:transactions_reconcile")
        self.login()

    def create_statement_import(self, **kwargs):
        self.bank_account = self.account(is_bank_account=True, type=Account.TYPES.asset, **kwargs)
        self.income_account = self.account(
            is_bank_account=False, type=Account.TYPES.income, **kwargs
        )

        statement_import = StatementImport.objects.create(
            bank_account=self.bank_account, source="csv"
        )

        self.line1 = StatementLine.objects.create(
            date="2000-01-01",
            statement_import=statement_import,
            amount=Decimal("100.16"),
            description="Item description 1",
        )

        self.line2 = StatementLine.objects.create(
            date="2000-01-03",
            statement_import=statement_import,
            amount=Decimal("-50.12"),
            description="Item description 2",
        )

        self.line3 = StatementLine.objects.create(
            date="2000-01-06",
            statement_import=statement_import,
            amount=Decimal("40.35"),
            description="Item description 3",
        )

    def test_get(self):
        self.create_statement_import()

        response = self.client.get(self.view_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["statement_lines"].count(), 3)
        self.assertNotIn("transaction_form", response.context)
        self.assertNotIn("leg_formset", response.context)

    def test_get_reconcile(self):
        self.create_statement_import()

        response = self.client.get(self.view_url, data=dict(reconcile=self.line1.uuid))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["statement_lines"].count(), 3)
        self.assertTrue(response.context["transaction_form"])
        self.assertTrue(response.context["leg_formset"])

        transaction_form = response.context["transaction_form"]
        self.assertEqual(transaction_form.initial["description"], "Item description 1")

        leg_formset = response.context["leg_formset"]
        self.assertEqual(leg_formset.forms[0].initial["amount"], Money("100.16", "EUR"))

    def test_post_reconcile_valid_one(self):
        self.create_statement_import()

        response = self.client.post(
            self.view_url,
            data={
                "reconcile": self.line1.uuid,
                "description": "Test transaction",
                "legs-INITIAL_FORMS": "0",
                "legs-TOTAL_FORMS": "2",
                "legs-0-amount_0": "100.16",
                "legs-0-amount_1": "EUR",
                "legs-0-account": self.income_account.uuid,
                "legs-0-id": "",
            },
        )

        if "transaction_form" in response.context:
            self.assertFalse(response.context["transaction_form"].errors)
            self.assertFalse(response.context["leg_formset"].non_form_errors())
            self.assertFalse(response.context["leg_formset"].errors)

        self.line1.refresh_from_db()

        self.assertEqual(Transaction.objects.count(), 1)
        transaction = Transaction.objects.get()

        self.assertEqual(transaction.description, "Test transaction")
        self.assertEqual(str(transaction.date), "2000-01-01")
        self.assertEqual(self.line1.transaction, transaction)

        self.assertEqual(transaction.legs.count(), 2)
        self.assertEqual(transaction.legs.filter(account=self.bank_account).count(), 1)
        self.assertEqual(transaction.legs.filter(account=self.income_account).count(), 1)

        leg_in = transaction.legs.get(account=self.bank_account)
        leg_out = transaction.legs.get(account=self.income_account)

        self.assertEqual(leg_in.amount, Money("-100.16", "EUR"))
        self.assertEqual(leg_in.account, self.bank_account)

        self.assertEqual(leg_out.amount, Money("100.16", "EUR"))
        self.assertEqual(leg_out.account, self.income_account)

        self.assertNotIn("leg_formset", response.context)
        self.assertNotIn("transaction_form", response.context)

    def test_post_reconcile_non_default_currency(self):
        self.create_statement_import(currencies=["GBP"])

        response = self.client.post(
            self.view_url,
            data={
                "reconcile": self.line1.uuid,
                "description": "Test transaction",
                "legs-INITIAL_FORMS": "0",
                "legs-TOTAL_FORMS": "2",
                "legs-0-amount_0": "100.16",
                "legs-0-amount_1": "GBP",
                "legs-0-account": self.income_account.uuid,
                "legs-0-id": "",
            },
        )
        if "transaction_form" in response.context:
            self.assertFalse(response.context["transaction_form"].errors)
            self.assertFalse(response.context["leg_formset"].non_form_errors())
            self.assertFalse(response.context["leg_formset"].errors)

        self.line1.refresh_from_db()

        self.assertEqual(Transaction.objects.count(), 1)
        transaction = Transaction.objects.get()

        self.assertEqual(transaction.legs.filter(account=self.bank_account).count(), 1)
        self.assertEqual(transaction.legs.filter(account=self.income_account).count(), 1)

        leg_in = transaction.legs.get(account=self.bank_account)
        leg_out = transaction.legs.get(account=self.income_account)

        self.assertEqual(leg_in.amount, Money("-100.16", "GBP"))
        self.assertEqual(leg_out.amount, Money("100.16", "GBP"))

    def test_post_reconcile_valid_two(self):
        self.create_statement_import()

        response = self.client.post(
            self.view_url,
            data={
                "reconcile": self.line1.uuid,
                "description": "Test transaction",
                "legs-INITIAL_FORMS": "0",
                "legs-TOTAL_FORMS": "2",
                "legs-0-amount_0": "50.16",
                "legs-0-amount_1": "EUR",
                "legs-0-account": self.income_account.uuid,
                "legs-0-id": "",
                "legs-1-amount_0": "50.00",
                "legs-1-amount_1": "EUR",
                "legs-1-account": self.income_account.uuid,
                "legs-1-id": "",
            },
        )

        if "transaction_form" in response.context:
            self.assertFalse(response.context["transaction_form"].errors)
            self.assertFalse(response.context["leg_formset"].errors)

        transaction = Transaction.objects.get()
        self.assertEqual(transaction.legs.count(), 3)

    def test_post_reconcile_invalid_amounts(self):
        self.create_statement_import()

        response = self.client.post(
            self.view_url,
            data={
                "reconcile": self.line1.uuid,
                "description": "Test transaction",
                "legs-INITIAL_FORMS": "0",
                "legs-TOTAL_FORMS": "2",
                "legs-0-amount_0": "1",
                "legs-0-amount_1": "EUR",
                "legs-0-account": self.income_account.uuid,
                "legs-0-id": "",
            },
        )
        self.assertEqual(Transaction.objects.count(), 0)

        leg_formset = response.context["leg_formset"]
        self.assertEqual(leg_formset.non_form_errors(), ["Amounts must add up to 100.16"])
        self.assertIn("Amounts must add up to 100.16", response.content.decode("utf8"))

    def test_post_reconcile_negative_amount(self):
        self.create_statement_import()

        response = self.client.post(
            self.view_url,
            data={
                "reconcile": self.line1.uuid,
                "description": "Test transaction",
                "legs-INITIAL_FORMS": "0",
                "legs-TOTAL_FORMS": "2",
                "legs-0-amount_0": "-1",
                "legs-0-amount_1": "EUR",
                "legs-0-account": self.income_account.uuid,
                "legs-0-id": "",
            },
        )
        self.assertEqual(Transaction.objects.count(), 0)

        leg_formset = response.context["leg_formset"]
        self.assertEqual(leg_formset.errors[0]["amount"], ["Amount must be greater than zero"])

    def test_post_reconcile_zero_amount(self):
        self.create_statement_import()

        response = self.client.post(
            self.view_url,
            data={
                "reconcile": self.line1.uuid,
                "description": "Test transaction",
                "legs-INITIAL_FORMS": "0",
                "legs-TOTAL_FORMS": "2",
                "legs-0-amount_0": "0",
                "legs-0-amount_1": "EUR",
                "legs-0-account": self.income_account.uuid,
                "legs-0-id": "",
            },
        )
        self.assertEqual(Transaction.objects.count(), 0)

        leg_formset = response.context["leg_formset"]
        self.assertEqual(leg_formset.errors[0]["amount"], ["Amount must be greater than zero"])

    def test_post_reconcile_negative(self):
        """Check that that positive amounts will be correctly used to reconcile negative amounts"""
        self.create_statement_import()

        response = self.client.post(
            self.view_url,
            data={
                "reconcile": self.line2.uuid,
                "description": "Test transaction",
                "legs-INITIAL_FORMS": "0",
                "legs-TOTAL_FORMS": "2",
                "legs-0-amount_0": "50.12",
                "legs-0-amount_1": "EUR",
                "legs-0-account": self.income_account.uuid,
                "legs-0-id": "",
            },
        )

        if "transaction_form" in response.context:
            self.assertFalse(response.context["transaction_form"].errors)
            self.assertFalse(response.context["leg_formset"].errors)

        transaction = Transaction.objects.get()
        self.assertEqual(transaction.legs.count(), 2)


class UnreconcileTransactionsViewTestCase(DataProvider, TestCase):
    def setUp(self):
        self.bank_account = self.account(is_bank_account=True, type=Account.TYPES.asset)
        self.income_account = self.account(is_bank_account=False, type=Account.TYPES.income)

        statement_import = StatementImport.objects.create(
            bank_account=self.bank_account, source="csv"
        )

        self.line1 = StatementLine.objects.create(
            date="2000-01-01",
            statement_import=statement_import,
            amount=Decimal("100.16"),
            description="Item description 1",
        )

        self.transaction = self.line1.create_transaction(self.income_account)

        self.login()
        self.view_url = reverse("hordak:transactions_unreconcile", args=[self.line1.uuid])

    def test_post(self):
        self.assertEqual(StatementLine.objects.get().transaction, self.transaction)
        response = self.client.post(self.view_url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(StatementLine.objects.get().transaction_id, None)
        self.assertEqual(Transaction.objects.count(), 0)
