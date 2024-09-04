from decimal import Decimal

from django.db import transaction as db_transaction
from django.test.testcases import TransactionTestCase as DbTransactionTestCase
from moneyed import Money

from hordak.models import Leg, LegView, Transaction, TransactionView
from hordak.tests.utils import DataProvider
from hordak.utilities.currency import Balance
from hordak.utilities.test import mysql_only, postgres_only


class LegViewTestCase(DataProvider, DbTransactionTestCase):
    def setUp(self):
        self.parent = self.account(currencies=["USD"], name="Parent", code="A")
        self.account1 = self.account(
            currencies=["USD"], parent=self.parent, name="One", code="1"
        )
        self.account2 = self.account(
            currencies=["USD"], parent=self.parent, name="Two", code="2"
        )

    def create_transaction(self, amount, account1=None, account2=None):
        with db_transaction.atomic():
            transaction = Transaction.objects.create(
                description="Transaction description", date="2000-01-01"
            )
            leg1 = Leg.objects.create(
                transaction=transaction,
                account=account1 or self.account1,
                credit=amount,
                description="Leg 1 description",
            )
            leg2 = Leg.objects.create(
                transaction=transaction,
                account=account2 or self.account2,
                debit=amount,
                description="Leg 2 description",
            )
        return transaction, leg1, leg2

    def test_simple(self):
        """A single transaction between two accounts"""

        transaction, leg1, leg2 = self.create_transaction(Money(100, "USD"))
        leg_view = LegView.objects.get(account=self.account1)
        self.assertEqual(leg_view.uuid, leg1.uuid)
        self.assertEqual(leg_view.leg, leg1)
        self.assertEqual(leg_view.transaction_id, transaction.pk)
        self.assertEqual(leg_view.account, self.account1)
        self.assertEqual(leg_view.date.isoformat(), "2000-01-01")
        self.assertEqual(leg_view.type, "CR")
        self.assertEqual(leg_view.credit, Money(100, "USD"))
        self.assertEqual(leg_view.debit, None)
        self.assertEqual(leg_view.amount, Money(100, "USD"))
        self.assertEqual(leg_view.legacy_amount, Money(100, "USD"))
        self.assertEqual(leg_view.account_balance, Decimal(100))
        self.assertEqual(leg_view.leg_description, "Leg 1 description")
        self.assertEqual(leg_view.transaction_description, "Transaction description")
        self.assertEqual(leg_view.account_name, "One")
        self.assertEqual(leg_view.account_type, "IN")
        self.assertEqual(leg_view.account_full_code, "A1")

        leg_view = LegView.objects.get(account=self.account2)
        self.assertEqual(leg_view.uuid, leg2.uuid)
        self.assertEqual(leg_view.leg, leg2)
        self.assertEqual(leg_view.transaction_id, transaction.pk)
        self.assertEqual(leg_view.account, self.account2)
        self.assertEqual(leg_view.date.isoformat(), "2000-01-01")
        self.assertEqual(leg_view.type, "DR")
        self.assertEqual(leg_view.credit, None)
        self.assertEqual(leg_view.debit, Money(100, "USD"))
        self.assertEqual(leg_view.amount, Money(100, "USD"))
        self.assertEqual(leg_view.legacy_amount, -Money(100, "USD"))
        self.assertEqual(leg_view.account_balance, Decimal(-100))
        self.assertEqual(leg_view.leg_description, "Leg 2 description")
        self.assertEqual(leg_view.transaction_description, "Transaction description")
        self.assertEqual(leg_view.account_name, "Two")
        self.assertEqual(leg_view.account_type, "IN")
        self.assertEqual(leg_view.account_full_code, "A2")

    def test_account_balance_leaf(self):
        self.create_transaction(Money(100, "USD"))
        self.create_transaction(Money(20, "USD"))
        self.create_transaction(Money(10, "USD"))

        # First transaction is for 100
        leg_view = LegView.objects.filter(account=self.account1).first()
        self.assertEqual(leg_view.account_balance, Decimal(100))

        leg_view = LegView.objects.filter(account=self.account2).first()
        self.assertEqual(leg_view.account_balance, Decimal(-100))

        # Then we have + 20 - 10
        leg_view = LegView.objects.filter(account=self.account1).last()
        self.assertEqual(leg_view.account_balance, Decimal(130))

        leg_view = LegView.objects.filter(account=self.account2).last()
        self.assertEqual(leg_view.account_balance, Decimal(-130))

    def test_account_balance_parent(self):
        self.create_transaction(
            amount=Money(15, "USD"),
            account1=self.parent,
            account2=self.account(currencies=["USD"]),
        )
        leg_view = LegView.objects.filter(account=self.parent).last()
        # Account balance is None because it is a non-leaf account
        self.assertEqual(leg_view.account_balance, None)


class TransactionViewTestCase(DataProvider, DbTransactionTestCase):
    def setUp(self):
        super().setUp()

        self.credit_account = self.account(currencies=["USD"], name="Credit")
        self.debit_account = self.account(currencies=["USD"], name="Debit")

        # Create a transaction that should be ignored
        with db_transaction.atomic():
            self.transaction = Transaction.objects.create()
            Leg.objects.create(
                transaction=self.transaction,
                account=self.credit_account,
                credit=Money(5, "USD"),
            )
            Leg.objects.create(
                transaction=self.transaction,
                account=self.debit_account,
                debit=Money(5, "USD"),
            )

        with db_transaction.atomic():
            self.transaction = Transaction.objects.create(
                description="Transaction description", date="2000-01-01"
            )
            Leg.objects.create(
                transaction=self.transaction,
                account=self.credit_account,
                credit=Money(100, "USD"),
            )
            Leg.objects.create(
                transaction=self.transaction,
                account=self.debit_account,
                debit=Money(100, "USD"),
            )

    def test_join_from_transaction_model(self):
        self.assertEqual(self.transaction.view.description, "Transaction description")

    def test_debit_account_details(self):
        view: TransactionView = TransactionView.objects.latest("pk")
        self.assertEqual(view.debit_account_ids, [self.debit_account.pk])
        self.assertEqual(view.debit_account_names, ["Debit"])

    def test_credit_account_details(self):
        view: TransactionView = TransactionView.objects.latest("pk")
        self.assertEqual(view.credit_account_ids, [self.credit_account.pk])
        self.assertEqual(view.credit_account_names, ["Credit"])

    def test_amount_single_currency(self):
        view: TransactionView = TransactionView.objects.latest("pk")
        self.assertEqual(view.amount, Balance([Money(100, "USD")]))

    @postgres_only("Only postgres supports multi-currency account amounts")
    def test_amount_multi_currency_postgres(self):
        self.credit_account_eur = self.account(currencies=["EUR"], name="Credit EUR")
        self.debit_account_eur = self.account(currencies=["EUR"], name="Debit EUR")

        with db_transaction.atomic():
            Leg.objects.create(
                transaction=self.transaction,
                account=self.credit_account_eur,
                credit=Money(90, "EUR"),
            )
            Leg.objects.create(
                transaction=self.transaction,
                account=self.debit_account_eur,
                debit=Money(90, "EUR"),
            )
        view: TransactionView = TransactionView.objects.latest("pk")
        self.assertEqual(view.amount, Balance([Money(100, "USD"), Money(90, "EUR")]))

    @mysql_only("No MySQL support for multi-currency account amounts")
    def test_amount_multi_currency_mysql(self):
        # Multi-currency transaction amounts only available in postgres
        self.credit_account_eur = self.account(currencies=["EUR"], name="Credit EUR")
        self.debit_account_eur = self.account(currencies=["EUR"], name="Debit EUR")

        with db_transaction.atomic():
            Leg.objects.create(
                transaction=self.transaction,
                account=self.credit_account_eur,
                credit=Money(90, "EUR"),
            )
            Leg.objects.create(
                transaction=self.transaction,
                account=self.debit_account_eur,
                debit=Money(90, "EUR"),
            )
        view: TransactionView = TransactionView.objects.latest("pk")
        self.assertEqual(view.amount, None)

    def test_amount_multiple_legs_to_same_account(self):
        with db_transaction.atomic():
            Leg.objects.create(
                transaction=self.transaction,
                account=self.credit_account,
                credit=Money(100, "USD"),
            )
            Leg.objects.create(
                transaction=self.transaction,
                account=self.debit_account,
                debit=Money(100, "USD"),
            )
        view: TransactionView = TransactionView.objects.latest("pk")
        self.assertEqual(view.amount, Money(200, "USD"))
