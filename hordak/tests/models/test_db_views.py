from decimal import Decimal

from django.db import transaction as db_transaction
from django.test.testcases import TransactionTestCase as DbTransactionTestCase
from moneyed import Money

from hordak.models import Leg, LegView, Transaction
from hordak.tests.utils import DataProvider


class LegViewTestCase(DataProvider, DbTransactionTestCase):
    def test_simple(self):
        """A single transaction between two accounts"""
        account1 = self.account(currencies=["USD"])
        account2 = self.account(currencies=["USD"])

        with db_transaction.atomic():
            transaction = Transaction.objects.create(
                description="Transaction description", date="2000-01-01"
            )
            leg1 = Leg.objects.create(
                transaction=transaction,
                account=account1,
                amount=Money(100, "USD"),
                description="Leg 1 description",
            )
            leg2 = Leg.objects.create(
                transaction=transaction,
                account=account2,
                amount=Money(-100, "USD"),
                description="Leg 2 description",
            )

        leg_view = LegView.objects.get(account=account1)
        self.assertEqual(leg_view.uuid, leg1.uuid)
        self.assertEqual(leg_view.transaction_id, transaction.pk)
        self.assertEqual(leg_view.account, account1)
        self.assertEqual(leg_view.date.isoformat(), "2000-01-01")
        self.assertEqual(leg_view.type, "CR")
        self.assertEqual(leg_view.credit, Decimal(100))
        self.assertEqual(leg_view.debit, None)
        self.assertEqual(leg_view.account_balance, Decimal(100))
        self.assertEqual(leg_view.leg_description, "Leg 1 description")
        self.assertEqual(leg_view.transaction_description, "Transaction description")

        leg_view = LegView.objects.get(account=account2)
        self.assertEqual(leg_view.uuid, leg2.uuid)
        self.assertEqual(leg_view.transaction_id, transaction.pk)
        self.assertEqual(leg_view.account, account2)
        self.assertEqual(leg_view.date.isoformat(), "2000-01-01")
        self.assertEqual(leg_view.type, "DR")
        self.assertEqual(leg_view.credit, None)
        self.assertEqual(leg_view.debit, Decimal(100))
        self.assertEqual(leg_view.account_balance, Decimal(-100))
        self.assertEqual(leg_view.leg_description, "Leg 2 description")
        self.assertEqual(leg_view.transaction_description, "Transaction description")

    def test_account_balance(self):
        account1 = self.account(currencies=["USD"])
        account2 = self.account(currencies=["USD"])

        with db_transaction.atomic():
            transaction1 = Transaction.objects.create()
            Leg.objects.create(
                transaction=transaction1, account=account1, amount=Money(100, "USD")
            )
            Leg.objects.create(
                transaction=transaction1, account=account2, amount=Money(-100, "USD")
            )

            transaction2 = Transaction.objects.create()
            Leg.objects.create(
                transaction=transaction2, account=account1, amount=Money(20, "USD")
            )
            Leg.objects.create(
                transaction=transaction2, account=account2, amount=Money(-20, "USD")
            )

            transaction3 = Transaction.objects.create()
            Leg.objects.create(
                transaction=transaction3, account=account1, amount=Money(-10, "USD")
            )
            Leg.objects.create(
                transaction=transaction3, account=account2, amount=Money(10, "USD")
            )

        # First transaction is for 100
        leg_view = LegView.objects.filter(account=account1).first()
        self.assertEqual(leg_view.account_balance, Decimal(100))

        leg_view = LegView.objects.filter(account=account2).first()
        self.assertEqual(leg_view.account_balance, Decimal(-100))

        # Then we have + 20 - 10
        leg_view = LegView.objects.filter(account=account1).last()
        self.assertEqual(leg_view.account_balance, Decimal(110))

        leg_view = LegView.objects.filter(account=account2).last()
        self.assertEqual(leg_view.account_balance, Decimal(-110))
