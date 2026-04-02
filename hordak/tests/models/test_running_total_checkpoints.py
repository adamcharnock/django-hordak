import logging
from unittest.mock import patch

from django.db import connection
from django.db import transaction as db_transaction
from django.db.models import Max
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
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

    def test_simple_balance_avoids_distinct_amount_currency_scan(self):
        account1 = self.account(type=Account.TYPES.income, currencies=["EUR"])
        account2 = self.account(type=Account.TYPES.income, currencies=["EUR"])
        with db_transaction.atomic():
            txn = Transaction.objects.create()
            Leg.objects.create(
                transaction=txn, account=account1, amount=Money(10, "EUR")
            )
            Leg.objects.create(
                transaction=txn, account=account2, amount=Money(-10, "EUR")
            )
        account1.rebuild_running_totals()
        account1.currencies = ["EUR", "USD"]
        account1.save()
        account2.currencies = ["EUR", "USD"]
        account2.save()
        with db_transaction.atomic():
            txn = Transaction.objects.create()
            Leg.objects.create(
                transaction=txn, account=account1, amount=Money(20, "USD")
            )
            Leg.objects.create(
                transaction=txn, account=account2, amount=Money(-20, "USD")
            )

        with CaptureQueriesContext(connection) as queries:
            balance = account1.simple_balance()

        self.assertEqual(balance, Balance([Money(10, "EUR"), Money(20, "USD")]))
        self.assertFalse(
            any(
                "SELECT DISTINCT" in query["sql"].upper()
                and "AMOUNT_CURRENCY" in query["sql"].upper()
                for query in queries.captured_queries
            )
        )

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

    def test_append_running_totals_uses_leg_cutoff_for_full_sum(self):
        account = self.account()

        with patch.object(
            account, "_running_total_current_leg_id", return_value=42
        ), patch.object(
            account,
            "_running_total_full_signed_balance",
            return_value=Balance([Money(10, "EUR")]),
        ) as full_balance_mock:
            account._append_running_totals_from_full_sum()

        full_balance_mock.assert_called_once_with(as_of_leg_id=42)
        self.assertEqual(
            account.running_totals.get(currency="EUR").includes_leg_id,
            42,
        )


class AdvanceCheckpointTests(DataProvider, TestCase):
    def test_advance_creates_new_checkpoint_from_delta(self):
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
        account1.rebuild_running_totals()
        old_rt = account1.running_totals.get(currency="EUR")

        with db_transaction.atomic():
            txn2 = Transaction.objects.create()
            Leg.objects.create(
                transaction=txn2, account=account1, amount=Money(30, "EUR")
            )
            Leg.objects.create(
                transaction=txn2, account=account2, amount=Money(-30, "EUR")
            )

        account1.advance_checkpoint()
        new_rt = (
            account1.running_totals.filter(currency="EUR")
            .order_by("-includes_leg_id")
            .first()
        )
        self.assertGreater(new_rt.includes_leg_id, old_rt.includes_leg_id)
        self.assertEqual(new_rt.balance, Money(80, "EUR"))
        self.assertEqual(account1.simple_balance(), Balance([Money(80, "EUR")]))

    def test_advance_preserves_history(self):
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
        account1.rebuild_running_totals()
        with db_transaction.atomic():
            txn2 = Transaction.objects.create()
            Leg.objects.create(
                transaction=txn2, account=account1, amount=Money(5, "EUR")
            )
            Leg.objects.create(
                transaction=txn2, account=account2, amount=Money(-5, "EUR")
            )
        account1.advance_checkpoint()
        self.assertEqual(account1.running_totals.filter(currency="EUR").count(), 2)

    def test_advance_noop_when_already_current(self):
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
        account1.rebuild_running_totals()
        count_before = account1.running_totals.count()
        account1.advance_checkpoint()
        self.assertEqual(account1.running_totals.count(), count_before)

    def test_advance_falls_back_to_full_sum_when_no_checkpoint(self):
        account1 = self.account()
        account2 = self.account()
        with db_transaction.atomic():
            txn = Transaction.objects.create()
            Leg.objects.create(
                transaction=txn, account=account1, amount=Money(25, "EUR")
            )
            Leg.objects.create(
                transaction=txn, account=account2, amount=Money(-25, "EUR")
            )
        self.assertEqual(account1.running_totals.count(), 0)
        account1.advance_checkpoint()
        self.assertEqual(account1.running_totals.count(), 1)
        rt = account1.running_totals.get()
        self.assertEqual(rt.balance, Money(25, "EUR"))

    def test_advance_handles_multi_currency(self):
        account1 = self.account(currencies=["EUR", "USD"])
        account2 = self.account(currencies=["EUR", "USD"])
        with db_transaction.atomic():
            txn = Transaction.objects.create()
            Leg.objects.create(
                transaction=txn, account=account1, amount=Money(10, "EUR")
            )
            Leg.objects.create(
                transaction=txn, account=account2, amount=Money(-10, "EUR")
            )
            Leg.objects.create(
                transaction=txn, account=account1, amount=Money(20, "USD")
            )
            Leg.objects.create(
                transaction=txn, account=account2, amount=Money(-20, "USD")
            )
        account1.rebuild_running_totals()
        with db_transaction.atomic():
            txn2 = Transaction.objects.create()
            Leg.objects.create(
                transaction=txn2, account=account1, amount=Money(5, "EUR")
            )
            Leg.objects.create(
                transaction=txn2, account=account2, amount=Money(-5, "EUR")
            )
            Leg.objects.create(
                transaction=txn2, account=account1, amount=Money(7, "USD")
            )
            Leg.objects.create(
                transaction=txn2, account=account2, amount=Money(-7, "USD")
            )
        account1.advance_checkpoint()
        self.assertEqual(
            account1.simple_balance(),
            Balance([Money(15, "EUR"), Money(27, "USD")]),
        )

    def test_advance_handles_new_currency_since_last_checkpoint(self):
        account1 = self.account(currencies=["EUR", "USD"])
        account2 = self.account(currencies=["EUR", "USD"])
        with db_transaction.atomic():
            txn = Transaction.objects.create()
            Leg.objects.create(
                transaction=txn, account=account1, amount=Money(10, "EUR")
            )
            Leg.objects.create(
                transaction=txn, account=account2, amount=Money(-10, "EUR")
            )
        account1.rebuild_running_totals()
        with db_transaction.atomic():
            txn2 = Transaction.objects.create()
            Leg.objects.create(
                transaction=txn2, account=account1, amount=Money(20, "USD")
            )
            Leg.objects.create(
                transaction=txn2, account=account2, amount=Money(-20, "USD")
            )
        account1.advance_checkpoint()
        self.assertEqual(
            account1.simple_balance(),
            Balance([Money(10, "EUR"), Money(20, "USD")]),
        )

    def test_advance_noop_when_no_legs(self):
        account1 = self.account()
        account1.advance_checkpoint()
        self.assertEqual(account1.running_totals.count(), 0)

    def test_advance_matches_full_sum_for_asset_account(self):
        bank = self.account(type=Account.TYPES.asset)
        income = self.account(type=Account.TYPES.income)
        with db_transaction.atomic():
            txn = Transaction.objects.create()
            Leg.objects.create(transaction=txn, account=bank, amount=Money(100, "EUR"))
            Leg.objects.create(
                transaction=txn, account=income, amount=Money(-100, "EUR")
            )
        bank.rebuild_running_totals()
        with db_transaction.atomic():
            txn2 = Transaction.objects.create()
            Leg.objects.create(transaction=txn2, account=bank, amount=Money(20, "EUR"))
            Leg.objects.create(
                transaction=txn2, account=income, amount=Money(-20, "EUR")
            )
        bank.advance_checkpoint()
        self.assertEqual(bank.simple_balance(), bank._simple_balance_full_sum())


class AutoAdvanceCheckpointTests(DataProvider, TestCase):
    def _create_legs(self, account1, account2, count):
        """Create `count` legs on account1 (and mirror on account2)."""
        for _ in range(count):
            txn = Transaction.objects.create()
            Leg.objects.create(
                transaction=txn, account=account1, amount=Money(1, "EUR")
            )
            Leg.objects.create(
                transaction=txn, account=account2, amount=Money(-1, "EUR")
            )

    @override_settings(HORDAK_CHECKPOINT_THRESHOLD=10)
    def test_auto_advance_triggers_at_threshold(self):
        from hordak import defaults

        defaults.CHECKPOINT_THRESHOLD = 10

        account1 = self.account()
        account2 = self.account()
        self._create_legs(account1, account2, 1)
        account1.rebuild_running_totals()
        initial_rt = account1.running_totals.get(currency="EUR")
        initial_includes = initial_rt.includes_leg_id

        # Each round creates 2 globally-sequenced leg IDs (one per account),
        # so account1's gap grows by 2 per round. 4 rounds → gap=8, below 10.
        self._create_legs(account1, account2, 4)
        latest_rt = (
            account1.running_totals.filter(currency="EUR")
            .order_by("-includes_leg_id")
            .first()
        )
        self.assertEqual(latest_rt.includes_leg_id, initial_includes)

        # 5th round → gap=10, meets threshold → auto-advance fires.
        self._create_legs(account1, account2, 1)
        latest_rt = (
            account1.running_totals.filter(currency="EUR")
            .order_by("-includes_leg_id")
            .first()
        )
        self.assertGreater(latest_rt.includes_leg_id, initial_includes)
        self.assertEqual(account1.simple_balance(), account1._simple_balance_full_sum())

    @override_settings(HORDAK_CHECKPOINT_THRESHOLD=0)
    def test_auto_advance_disabled_when_threshold_zero(self):
        from hordak import defaults

        defaults.CHECKPOINT_THRESHOLD = 0

        account1 = self.account()
        account2 = self.account()
        account1.rebuild_running_totals()
        initial_count = account1.running_totals.count()

        self._create_legs(account1, account2, 10)
        self.assertEqual(account1.running_totals.count(), initial_count)

    @override_settings(HORDAK_CHECKPOINT_THRESHOLD=3)
    def test_auto_advance_no_checkpoint_means_no_trigger(self):
        """Auto-advance should not trigger when there is no existing checkpoint."""
        from hordak import defaults

        defaults.CHECKPOINT_THRESHOLD = 3

        account1 = self.account()
        account2 = self.account()
        RunningTotal.objects.filter(account=account1).delete()

        self._create_legs(account1, account2, 5)
        self.assertEqual(account1.running_totals.count(), 0)

    @override_settings(HORDAK_CHECKPOINT_THRESHOLD=5)
    def test_auto_advance_on_bulk_create(self):
        """bulk_create should also trigger auto-advance when threshold exceeded."""
        from hordak import defaults

        defaults.CHECKPOINT_THRESHOLD = 5

        account1 = self.account()
        account2 = self.account()
        self._create_legs(account1, account2, 1)
        account1.rebuild_running_totals()
        initial_rt = account1.running_totals.get(currency="EUR")
        initial_includes = initial_rt.includes_leg_id

        txn = Transaction.objects.create()
        legs = [
            Leg(transaction=txn, account=account1, amount=Money(1, "EUR")),
            Leg(transaction=txn, account=account2, amount=Money(-1, "EUR")),
        ]
        Leg.objects.bulk_create(legs)
        # Gap is only 2, below threshold
        latest_rt = (
            account1.running_totals.filter(currency="EUR")
            .order_by("-includes_leg_id")
            .first()
        )
        self.assertEqual(latest_rt.includes_leg_id, initial_includes)

        # Now bulk_create enough to exceed threshold (need gap >= 5 total)
        legs2 = []
        for _ in range(3):
            txn = Transaction.objects.create()
            legs2.append(Leg(transaction=txn, account=account1, amount=Money(1, "EUR")))
            legs2.append(
                Leg(transaction=txn, account=account2, amount=Money(-1, "EUR"))
            )
        Leg.objects.bulk_create(legs2)
        latest_rt = (
            account1.running_totals.filter(currency="EUR")
            .order_by("-includes_leg_id")
            .first()
        )
        self.assertGreater(latest_rt.includes_leg_id, initial_includes)
        self.assertEqual(account1.simple_balance(), account1._simple_balance_full_sum())


class SignCorrectnessTests(DataProvider, TestCase):
    """Verify checkpoint + delta gives identical results to full sum for every account type."""

    def _make_pair_and_transact(self, type1, type2, amount):
        a1 = self.account(type=type1)
        a2 = self.account(type=type2)
        with db_transaction.atomic():
            txn = Transaction.objects.create()
            Leg.objects.create(transaction=txn, account=a1, amount=Money(amount, "EUR"))
            Leg.objects.create(
                transaction=txn, account=a2, amount=Money(-amount, "EUR")
            )
        a1.rebuild_running_totals()
        a2.rebuild_running_totals()
        with db_transaction.atomic():
            txn2 = Transaction.objects.create()
            Leg.objects.create(
                transaction=txn2, account=a1, amount=Money(amount / 2, "EUR")
            )
            Leg.objects.create(
                transaction=txn2, account=a2, amount=Money(-amount / 2, "EUR")
            )
        return a1, a2

    def test_expense_checkpoint_plus_delta(self):
        expense, income = self._make_pair_and_transact(
            Account.TYPES.expense, Account.TYPES.income, 100
        )
        self.assertEqual(expense.simple_balance(), expense._simple_balance_full_sum())
        self.assertEqual(income.simple_balance(), income._simple_balance_full_sum())

    def test_liability_checkpoint_plus_delta(self):
        liability, asset = self._make_pair_and_transact(
            Account.TYPES.liability, Account.TYPES.asset, 100
        )
        self.assertEqual(
            liability.simple_balance(), liability._simple_balance_full_sum()
        )
        self.assertEqual(asset.simple_balance(), asset._simple_balance_full_sum())

    def test_equity_checkpoint_plus_delta(self):
        equity, asset = self._make_pair_and_transact(
            Account.TYPES.equity, Account.TYPES.asset, 100
        )
        self.assertEqual(equity.simple_balance(), equity._simple_balance_full_sum())
        self.assertEqual(asset.simple_balance(), asset._simple_balance_full_sum())

    def test_advance_checkpoint_expense_account(self):
        expense = self.account(type=Account.TYPES.expense)
        income = self.account(type=Account.TYPES.income)
        with db_transaction.atomic():
            txn = Transaction.objects.create()
            Leg.objects.create(
                transaction=txn, account=expense, amount=Money(100, "EUR")
            )
            Leg.objects.create(
                transaction=txn, account=income, amount=Money(-100, "EUR")
            )
        expense.rebuild_running_totals()
        with db_transaction.atomic():
            txn2 = Transaction.objects.create()
            Leg.objects.create(
                transaction=txn2, account=expense, amount=Money(30, "EUR")
            )
            Leg.objects.create(
                transaction=txn2, account=income, amount=Money(-30, "EUR")
            )
        expense.advance_checkpoint()
        self.assertEqual(expense.simple_balance(), expense._simple_balance_full_sum())

    def test_advance_checkpoint_liability_account(self):
        liability = self.account(type=Account.TYPES.liability)
        asset = self.account(type=Account.TYPES.asset)
        with db_transaction.atomic():
            txn = Transaction.objects.create()
            Leg.objects.create(
                transaction=txn, account=liability, amount=Money(-200, "EUR")
            )
            Leg.objects.create(transaction=txn, account=asset, amount=Money(200, "EUR"))
        liability.rebuild_running_totals()
        with db_transaction.atomic():
            txn2 = Transaction.objects.create()
            Leg.objects.create(
                transaction=txn2, account=liability, amount=Money(-50, "EUR")
            )
            Leg.objects.create(transaction=txn2, account=asset, amount=Money(50, "EUR"))
        liability.advance_checkpoint()
        self.assertEqual(
            liability.simple_balance(), liability._simple_balance_full_sum()
        )


class CheckRunningTotalsTests(DataProvider, TestCase):
    def test_check_reports_effective_balance(self):
        account1 = self.account(type=Account.TYPES.income)
        account2 = self.account(type=Account.TYPES.income)
        with db_transaction.atomic():
            txn = Transaction.objects.create()
            Leg.objects.create(
                transaction=txn, account=account1, amount=Money(10, "EUR")
            )
            Leg.objects.create(
                transaction=txn, account=account2, amount=Money(-10, "EUR")
            )
        account1.rebuild_running_totals()
        with db_transaction.atomic():
            txn = Transaction.objects.create()
            Leg.objects.create(
                transaction=txn, account=account1, amount=Money(5, "EUR")
            )
            Leg.objects.create(
                transaction=txn, account=account2, amount=Money(-5, "EUR")
            )
        account1.running_totals.update(balance=Money(999, "EUR"))

        faulty = account1._check_running_totals()

        self.assertEqual(faulty, [("EUR", Money(1004, "EUR"), Money(15, "EUR"))])

    def test_check_detects_corrupted_checkpoint(self):
        account1 = self.account()
        account2 = self.account()
        with db_transaction.atomic():
            txn = Transaction.objects.create()
            Leg.objects.create(
                transaction=txn, account=account1, amount=Money(100, "EUR")
            )
            Leg.objects.create(
                transaction=txn, account=account2, amount=Money(-100, "EUR")
            )
        account1.rebuild_running_totals()
        rt = account1.running_totals.get(currency="EUR")
        RunningTotal.objects.filter(pk=rt.pk).update(balance=Money(999, "EUR"))

        faulty = account1._check_running_totals()
        self.assertEqual(len(faulty), 1)
        currency, rt_value, correct_value = faulty[0]
        self.assertEqual(currency, "EUR")
        self.assertEqual(rt_value, Money(999, "EUR"))
        self.assertEqual(correct_value, Money(100, "EUR"))

    def test_check_returns_empty_when_correct(self):
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
        account1.rebuild_running_totals()
        self.assertEqual(account1._check_running_totals(), [])

    def test_check_detects_missing_running_total(self):
        account1 = self.account()
        account2 = self.account()
        with db_transaction.atomic():
            txn = Transaction.objects.create()
            Leg.objects.create(
                transaction=txn, account=account1, amount=Money(75, "EUR")
            )
            Leg.objects.create(
                transaction=txn, account=account2, amount=Money(-75, "EUR")
            )
        faulty = account1._check_running_totals()
        self.assertEqual(len(faulty), 1)
        currency, rt_value, correct_value = faulty[0]
        self.assertEqual(currency, "EUR")
        self.assertIsNone(rt_value)
        self.assertEqual(correct_value, Money(75, "EUR"))

    def test_check_logs_warning_on_corruption(self):
        account1 = self.account()
        account2 = self.account()
        with db_transaction.atomic():
            txn = Transaction.objects.create()
            Leg.objects.create(
                transaction=txn, account=account1, amount=Money(100, "EUR")
            )
            Leg.objects.create(
                transaction=txn, account=account2, amount=Money(-100, "EUR")
            )
        account1.rebuild_running_totals()
        rt = account1.running_totals.get(currency="EUR")
        RunningTotal.objects.filter(pk=rt.pk).update(balance=Money(999, "EUR"))

        with self.assertLogs("hordak.models.core", level=logging.WARNING) as cm:
            account1._check_running_totals()
        self.assertTrue(any("Running totals difference" in msg for msg in cm.output))

    def test_check_logs_warning_on_missing_total(self):
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

        with self.assertLogs("hordak.models.core", level=logging.WARNING) as cm:
            account1._check_running_totals()
        self.assertTrue(any("No running total" in msg for msg in cm.output))

    def test_update_running_totals_check_only(self):
        account1 = self.account()
        account2 = self.account()
        with db_transaction.atomic():
            txn = Transaction.objects.create()
            Leg.objects.create(
                transaction=txn, account=account1, amount=Money(100, "EUR")
            )
            Leg.objects.create(
                transaction=txn, account=account2, amount=Money(-100, "EUR")
            )
        account1.rebuild_running_totals()
        rt = account1.running_totals.get(currency="EUR")
        RunningTotal.objects.filter(pk=rt.pk).update(balance=Money(999, "EUR"))

        faulty = account1.update_running_totals(check_only=True)
        self.assertEqual(len(faulty), 1)
        # check_only=True should NOT fix the running total
        rt.refresh_from_db()
        self.assertEqual(rt.balance, Money(999, "EUR"))

    def test_update_running_totals_fixes_corruption(self):
        account1 = self.account()
        account2 = self.account()
        with db_transaction.atomic():
            txn = Transaction.objects.create()
            Leg.objects.create(
                transaction=txn, account=account1, amount=Money(100, "EUR")
            )
            Leg.objects.create(
                transaction=txn, account=account2, amount=Money(-100, "EUR")
            )
        account1.rebuild_running_totals()
        rt = account1.running_totals.get(currency="EUR")
        RunningTotal.objects.filter(pk=rt.pk).update(balance=Money(999, "EUR"))

        account1.update_running_totals(check_only=False)
        new_rt = (
            account1.running_totals.filter(currency="EUR")
            .order_by("-includes_leg_id")
            .first()
        )
        self.assertEqual(new_rt.balance, Money(100, "EUR"))
