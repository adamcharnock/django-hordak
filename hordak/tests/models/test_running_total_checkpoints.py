from django.db import transaction as db_transaction
from django.db.models import Max
from django.test import TestCase
from moneyed.classes import Money

from hordak.models import Account, Leg, RunningTotal, Transaction
from hordak.tests.utils import DataProvider
from hordak.utilities.currency import Balance


class RunningTotalCheckpointTests(DataProvider, TestCase):
    def test_checkpoint_plus_delta_matches_full_sum(self):
        account1 = self.account()
        account2 = self.account()
        with db_transaction.atomic():
            txn = Transaction.objects.create()
            Leg.objects.create(
                transaction=txn, account=account1, amount=Money(50, "EUR")
            )
            Leg.objects.create(
                transaction=txn, account=account2, amount=Money(-50, "EUR")
            )
        account1.update_running_totals()
        with db_transaction.atomic():
            txn2 = Transaction.objects.create()
            Leg.objects.create(
                transaction=txn2, account=account1, amount=Money(25, "EUR")
            )
            Leg.objects.create(
                transaction=txn2, account=account2, amount=Money(-25, "EUR")
            )
        self.assertEqual(account1.simple_balance(), Balance([Money(75, "EUR")]))
        self.assertEqual(account1.simple_balance(), account1._simple_balance_full_sum())

    def test_no_running_total_row_change_on_leg_insert(self):
        account1 = self.account()
        account2 = self.account()
        with db_transaction.atomic():
            txn = Transaction.objects.create()
            Leg.objects.create(
                transaction=txn, account=account1, amount=Money(10, "EUR")
            )
            Leg.objects.create(
                transaction=txn, account=account2, amount=Money(-10, "EUR")
            )
        account1.update_running_totals()
        before = list(
            account1.running_totals.values_list("id", "includes_leg_id", "balance")
        )
        n_before = account1.running_totals.count()
        with db_transaction.atomic():
            txn2 = Transaction.objects.create()
            Leg.objects.create(
                transaction=txn2, account=account1, amount=Money(5, "EUR")
            )
            Leg.objects.create(
                transaction=txn2, account=account2, amount=Money(-5, "EUR")
            )
        self.assertEqual(account1.running_totals.count(), n_before)
        after = list(
            account1.running_totals.values_list("id", "includes_leg_id", "balance")
        )
        self.assertEqual(before, after)

    def test_recompute_on_leg_update(self):
        account1 = self.account()
        account2 = self.account()
        with db_transaction.atomic():
            txn = Transaction.objects.create()
            leg = Leg.objects.create(
                transaction=txn, account=account1, amount=Money(40, "EUR")
            )
            Leg.objects.create(
                transaction=txn, account=account2, amount=Money(-40, "EUR")
            )
        account1.update_running_totals()
        with db_transaction.atomic():
            leg.amount = Money(70, "EUR")
            leg.save()
            other = Leg.objects.get(account=account2, transaction=leg.transaction)
            other.amount = Money(-70, "EUR")
            other.save()
        account1.refresh_from_db()
        rt = (
            account1.running_totals.filter(currency="EUR")
            .order_by("-includes_leg_id")
            .first()
        )
        self.assertEqual(rt.balance, Money(70, "EUR"))
        max_id = Leg.objects.filter(account=account1).aggregate(m=Max("id"))["m"]
        self.assertEqual(rt.includes_leg_id, max_id)

    def test_recompute_on_leg_delete(self):
        account1 = self.account()
        account2 = self.account()
        with db_transaction.atomic():
            txn = Transaction.objects.create()
            Leg.objects.create(
                transaction=txn, account=account1, amount=Money(30, "EUR")
            )
            Leg.objects.create(
                transaction=txn, account=account2, amount=Money(-30, "EUR")
            )
        account1.update_running_totals()
        Transaction.objects.filter(legs__account=account1).delete()
        rt = (
            account1.running_totals.filter(currency="EUR")
            .order_by("-includes_leg_id")
            .first()
        )
        self.assertEqual(rt.balance.amount, 0)

    def test_latest_checkpoint_used_when_multiple_exist(self):
        account1 = self.account()
        account2 = self.account()
        with db_transaction.atomic():
            txn = Transaction.objects.create()
            Leg.objects.create(
                transaction=txn, account=account1, amount=Money(10, "EUR")
            )
            Leg.objects.create(
                transaction=txn, account=account2, amount=Money(-10, "EUR")
            )
        account1.update_running_totals()
        with db_transaction.atomic():
            txn2 = Transaction.objects.create()
            Leg.objects.create(
                transaction=txn2, account=account1, amount=Money(5, "EUR")
            )
            Leg.objects.create(
                transaction=txn2, account=account2, amount=Money(-5, "EUR")
            )
        account1.update_running_totals(keep_history=True)
        stale = (
            account1.running_totals.filter(currency="EUR")
            .order_by("includes_leg_id")
            .first()
        )
        RunningTotal.objects.filter(pk=stale.pk).update(balance=Money(999, "EUR"))
        self.assertEqual(account1.simple_balance(), Balance([Money(15, "EUR")]))

    def test_no_checkpoint_falls_back_to_full_sum(self):
        account1 = self.account()
        account2 = self.account()
        with db_transaction.atomic():
            txn = Transaction.objects.create()
            Leg.objects.create(
                transaction=txn, account=account1, amount=Money(33, "EUR")
            )
            Leg.objects.create(
                transaction=txn, account=account2, amount=Money(-33, "EUR")
            )
        expected = account1.simple_balance()
        RunningTotal.objects.filter(account=account1).delete()
        self.assertEqual(account1.simple_balance(), expected)

    def test_bulk_create_balance_correct(self):
        account1 = self.account(type=Account.TYPES.income, currencies=["EUR"])
        account2 = self.account(type=Account.TYPES.income, currencies=["EUR"])
        txn = Transaction.objects.create()
        legs = [
            Leg(transaction=txn, account=account1, amount=Money(3, "EUR")),
            Leg(transaction=txn, account=account2, amount=Money(-3, "EUR")),
        ]
        Leg.objects.bulk_create(legs)
        account1.update_running_totals()
        self.assertEqual(account1.simple_balance(), Balance([Money(3, "EUR")]))

    def test_sign_asset_checkpoint_and_delta(self):
        bank = self.account(type=Account.TYPES.asset)
        income = self.account(type=Account.TYPES.income)
        with db_transaction.atomic():
            txn = Transaction.objects.create()
            Leg.objects.create(transaction=txn, account=bank, amount=Money(100, "EUR"))
            Leg.objects.create(
                transaction=txn, account=income, amount=Money(-100, "EUR")
            )
        bank.update_running_totals()
        with db_transaction.atomic():
            txn2 = Transaction.objects.create()
            Leg.objects.create(transaction=txn2, account=bank, amount=Money(20, "EUR"))
            Leg.objects.create(
                transaction=txn2, account=income, amount=Money(-20, "EUR")
            )
        self.assertEqual(bank.simple_balance(), bank._simple_balance_full_sum())

    def test_raw_balance_correct_with_checkpoint(self):
        bank = self.account(type=Account.TYPES.asset)
        income = self.account(type=Account.TYPES.income)
        with db_transaction.atomic():
            txn = Transaction.objects.create()
            Leg.objects.create(transaction=txn, account=bank, amount=Money(100, "EUR"))
            Leg.objects.create(
                transaction=txn, account=income, amount=Money(-100, "EUR")
            )
        bank.update_running_totals()
        with db_transaction.atomic():
            txn2 = Transaction.objects.create()
            Leg.objects.create(transaction=txn2, account=bank, amount=Money(20, "EUR"))
            Leg.objects.create(
                transaction=txn2, account=income, amount=Money(-20, "EUR")
            )
        self.assertEqual(
            bank.simple_balance(raw=True),
            bank._simple_balance_full_sum(raw=True),
        )
