import importlib
from io import StringIO
from unittest.mock import patch

from django.core import mail
from django.core.management import call_command
from django.db import connection
from django.db import transaction as db_transaction
from django.test import override_settings
from django.test.testcases import TransactionTestCase as DbTransactionTestCase
from django.test.utils import CaptureQueriesContext
from moneyed import Money

from hordak.models import Account, AccountType, Leg, RunningTotal, Transaction
from hordak.receivers import (
    maintain_running_totals_on_leg_delete,
    maintain_running_totals_on_leg_save,
)
from hordak.tests.utils import DataProvider
from hordak.utilities.currency import Balance


class RunningTotalCheckpointTests(DataProvider, DbTransactionTestCase):
    def test_app_ready_imports_receivers(self):
        from hordak.apps import HordakConfig

        config = HordakConfig("hordak", importlib.import_module("hordak"))

        with patch("hordak.apps.importlib.import_module") as import_module_mock:
            config.ready()

        import_module_mock.assert_called_once_with("hordak.receivers")

    def _post(self, credit_account, debit_account, amount, currency="EUR", date=None):
        with db_transaction.atomic():
            transaction_kwargs = {} if date is None else {"date": date}
            transaction = Transaction.objects.create(**transaction_kwargs)
            Leg.objects.create(
                transaction=transaction,
                account=credit_account,
                credit=Money(amount, currency),
            )
            Leg.objects.create(
                transaction=transaction,
                account=debit_account,
                debit=Money(amount, currency),
            )

    def test_get_simple_balance_returns_zero_for_unsaved_account(self):
        account = Account(type=AccountType.income, currencies=["EUR"])

        self.assertEqual(account.get_simple_balance(), Balance([Money(0, "EUR")]))

    def test_get_simple_balance_falls_back_for_as_of_queries(self):
        account = self.account(type=AccountType.income)
        offset = self.account(type=AccountType.income)

        self._post(account, offset, 50, date="2024-01-01")
        account.rebuild_running_totals()
        self._post(account, offset, 25, date="2024-02-01")

        self.assertEqual(
            account.get_simple_balance(as_of="2024-01-15"),
            Balance([Money(50, "EUR")]),
        )

    def test_get_simple_balance_falls_back_without_checkpoint(self):
        account = self.account(type=AccountType.income)
        offset = self.account(type=AccountType.income)

        self._post(account, offset, 33)

        self.assertEqual(account.running_totals.count(), 0)
        self.assertEqual(account.get_simple_balance(), Balance([Money(33, "EUR")]))

    def test_get_simple_balance_rejects_raw_kwarg(self):
        account = self.account(type=AccountType.income)

        with self.assertRaises(DeprecationWarning):
            account.get_simple_balance(raw=True)

    def test_get_simple_balance_uses_checkpoint_and_delta(self):
        account = self.account(type=AccountType.income)
        offset = self.account(type=AccountType.income)

        self._post(account, offset, 50)
        account.rebuild_running_totals()
        self._post(account, offset, 25)

        self.assertEqual(account.get_simple_balance(), Balance([Money(75, "EUR")]))

    def test_latest_checkpoint_wins_over_stale_history(self):
        account = self.account(type=AccountType.income)
        offset = self.account(type=AccountType.income)

        self._post(account, offset, 10)
        account.rebuild_running_totals()
        self._post(account, offset, 5)
        account.rebuild_running_totals(keep_history=True)

        stale = account.running_totals.order_by("includes_leg_id").first()
        RunningTotal.objects.filter(pk=stale.pk).update(balance=Money(999, "EUR"))

        self.assertEqual(account.get_simple_balance(), Balance([Money(15, "EUR")]))

    def test_get_simple_balance_includes_uncheckpointed_currency(self):
        account = self.account(type=AccountType.income, currencies=["EUR", "USD"])
        offset = self.account(type=AccountType.income, currencies=["EUR", "USD"])

        self._post(account, offset, 10, currency="EUR")
        account.rebuild_running_totals()
        self._post(account, offset, 20, currency="USD")

        self.assertEqual(
            account.get_simple_balance(),
            Balance([Money(10, "EUR"), Money(20, "USD")]),
        )

    def test_get_simple_balance_includes_currency_without_checkpoint_row(self):
        account = self.account(type=AccountType.income, currencies=["EUR"])
        offset = self.account(type=AccountType.income, currencies=["EUR"])

        self._post(account, offset, 10, currency="EUR")
        account.rebuild_running_totals()
        account.currencies = ["EUR", "USD"]
        account.save()
        offset.currencies = ["EUR", "USD"]
        offset.save()
        self._post(account, offset, 20, currency="USD")

        self.assertEqual(
            account.get_simple_balance(),
            Balance([Money(10, "EUR"), Money(20, "USD")]),
        )

    def test_get_simple_balance_avoids_distinct_leg_currency_scan(self):
        account = self.account(type=AccountType.income, currencies=["EUR"])
        offset = self.account(type=AccountType.income, currencies=["EUR"])

        self._post(account, offset, 10, currency="EUR")
        account.rebuild_running_totals()
        account.currencies = ["EUR", "USD"]
        account.save()
        offset.currencies = ["EUR", "USD"]
        offset.save()
        self._post(account, offset, 20, currency="USD")

        with CaptureQueriesContext(connection) as queries:
            balance = account.get_simple_balance()

        self.assertEqual(balance, Balance([Money(10, "EUR"), Money(20, "USD")]))
        self.assertFalse(
            any(
                "SELECT DISTINCT" in query["sql"].upper()
                and '"HORDak_leg"'.upper() in query["sql"].upper()
                for query in queries.captured_queries
            )
        )

    def test_rebuild_running_totals_replaces_existing_history_by_default(self):
        account = self.account(type=AccountType.income)
        offset = self.account(type=AccountType.income)

        self._post(account, offset, 10)
        account.rebuild_running_totals()
        self._post(account, offset, 5)
        account.rebuild_running_totals()

        running_total = account.running_totals.get(currency="EUR")
        self.assertEqual(str(running_total), f"{account}: €15.00")
        self.assertEqual(running_total.balance, Money(15, "EUR"))

    def test_rebuild_running_totals_can_keep_history(self):
        account = self.account(type=AccountType.income)
        offset = self.account(type=AccountType.income)

        self._post(account, offset, 10)
        account.rebuild_running_totals()
        self._post(account, offset, 5)
        account.rebuild_running_totals(keep_history=True)

        self.assertEqual(account.running_totals.filter(currency="EUR").count(), 2)

    def test_append_running_totals_uses_leg_cutoff_for_full_sum(self):
        account = self.account(type=AccountType.income)

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

    def test_check_running_totals_reports_effective_balance(self):
        account = self.account(type=AccountType.income)
        offset = self.account(type=AccountType.income)

        self._post(account, offset, 10)
        account.rebuild_running_totals()
        self._post(account, offset, 5)
        account.running_totals.update(balance=Money(999, "EUR"))

        self.assertEqual(
            account.check_running_totals(),
            [("EUR", Money(1004, "EUR"), Money(15, "EUR"))],
        )

    def test_update_running_totals_check_only_preserves_rows(self):
        account = self.account(type=AccountType.income)
        offset = self.account(type=AccountType.income)

        self._post(account, offset, 10)
        account.rebuild_running_totals()
        account.running_totals.update(balance=Money(999, "EUR"))

        faulty_values = account.update_running_totals(check_only=True)

        self.assertEqual(
            faulty_values,
            [("EUR", Money(999, "EUR"), Money(10, "EUR"))],
        )
        self.assertEqual(
            account.running_totals.get(currency="EUR").balance, Money(999, "EUR")
        )

    def test_update_running_totals_rebuilds_when_not_check_only(self):
        account = self.account(type=AccountType.income)
        offset = self.account(type=AccountType.income)

        self._post(account, offset, 10)
        account.rebuild_running_totals()
        account.running_totals.update(balance=Money(999, "EUR"))

        faulty_values = account.update_running_totals()

        self.assertEqual(
            faulty_values,
            [("EUR", Money(999, "EUR"), Money(10, "EUR"))],
        )
        self.assertEqual(
            account.running_totals.get(currency="EUR").balance, Money(10, "EUR")
        )

    def test_advance_checkpoint_noops_without_legs(self):
        account = self.account(type=AccountType.income)

        account.advance_checkpoint()

        self.assertEqual(account.running_totals.count(), 0)

    def test_advance_checkpoint_creates_first_checkpoint(self):
        account = self.account(type=AccountType.income)
        offset = self.account(type=AccountType.income)

        self._post(account, offset, 25)

        account.advance_checkpoint()

        running_total = account.running_totals.get(currency="EUR")
        self.assertEqual(running_total.balance, Money(25, "EUR"))

    def test_advance_checkpoint_noops_when_already_current(self):
        account = self.account(type=AccountType.income)
        offset = self.account(type=AccountType.income)

        self._post(account, offset, 10)
        account.rebuild_running_totals()
        count_before = account.running_totals.count()

        account.advance_checkpoint()

        self.assertEqual(account.running_totals.count(), count_before)

    def test_advance_checkpoint_appends_delta(self):
        account = self.account(type=AccountType.income)
        offset = self.account(type=AccountType.income)

        self._post(account, offset, 10)
        account.rebuild_running_totals()
        self._post(account, offset, 5)

        account.advance_checkpoint()

        latest = account.running_totals.order_by("-includes_leg_id").first()
        self.assertEqual(account.running_totals.count(), 2)
        self.assertEqual(latest.balance, Money(15, "EUR"))

    def test_advance_checkpoint_adds_new_currency(self):
        account = self.account(type=AccountType.income, currencies=["EUR"])
        offset = self.account(type=AccountType.income, currencies=["EUR"])

        self._post(account, offset, 10, currency="EUR")
        account.rebuild_running_totals()
        account.currencies = ["EUR", "USD"]
        account.save()
        offset.currencies = ["EUR", "USD"]
        offset.save()
        self._post(account, offset, 20, currency="USD")

        account.advance_checkpoint()

        self.assertEqual(
            account.get_simple_balance(),
            Balance([Money(10, "EUR"), Money(20, "USD")]),
        )
        self.assertEqual(account.running_totals.filter(currency="USD").count(), 1)

    def test_leg_update_invalidates_running_totals(self):
        account = self.account(type=AccountType.income)
        offset = self.account(type=AccountType.income)

        with db_transaction.atomic():
            transaction = Transaction.objects.create()
            credit_leg = Leg.objects.create(
                transaction=transaction,
                account=account,
                credit=Money(40, "EUR"),
            )
            debit_leg = Leg.objects.create(
                transaction=transaction,
                account=offset,
                debit=Money(40, "EUR"),
            )
        account.rebuild_running_totals()

        with db_transaction.atomic():
            credit_leg.credit = Money(70, "EUR")
            credit_leg.save()
            debit_leg.debit = Money(70, "EUR")
            debit_leg.save()

        self.assertEqual(account.running_totals.count(), 0)
        self.assertEqual(account.get_simple_balance(), Balance([Money(70, "EUR")]))

    def test_leg_account_move_invalidates_old_and_new_accounts(self):
        source = self.account(type=AccountType.income)
        destination = self.account(type=AccountType.income)
        offset = self.account(type=AccountType.income)

        with db_transaction.atomic():
            transaction = Transaction.objects.create()
            moved_leg = Leg.objects.create(
                transaction=transaction,
                account=source,
                credit=Money(40, "EUR"),
            )
            Leg.objects.create(
                transaction=transaction,
                account=offset,
                debit=Money(40, "EUR"),
            )
        source.rebuild_running_totals()
        destination.rebuild_running_totals()

        moved_leg.account = destination
        moved_leg.save()

        self.assertEqual(source.running_totals.count(), 0)
        self.assertEqual(destination.running_totals.count(), 0)
        self.assertEqual(source.get_simple_balance(), Balance([Money(0, "EUR")]))
        self.assertEqual(destination.get_simple_balance(), Balance([Money(40, "EUR")]))

    def test_leg_delete_invalidates_running_totals(self):
        account = self.account(type=AccountType.income)
        offset = self.account(type=AccountType.income)

        with db_transaction.atomic():
            transaction = Transaction.objects.create()
            Leg.objects.create(
                transaction=transaction,
                account=account,
                credit=Money(30, "EUR"),
            )
            Leg.objects.create(
                transaction=transaction,
                account=offset,
                debit=Money(30, "EUR"),
            )
        account.rebuild_running_totals()

        transaction.delete()

        self.assertEqual(account.running_totals.count(), 0)
        self.assertEqual(account.get_simple_balance(), Balance([Money(0, "EUR")]))

    def test_checkpoint_balance_respects_asset_sign(self):
        asset = self.account(type=AccountType.asset)
        income = self.account(type=AccountType.income)

        self._post(income, asset, 100)
        asset.rebuild_running_totals()
        self._post(income, asset, 20)

        self.assertEqual(asset.get_simple_balance(), Balance([Money(120, "EUR")]))

    @override_settings(HORDAK_CHECKPOINT_THRESHOLD=0)
    def test_leg_insert_does_not_auto_advance_when_disabled(self):
        account = self.account(type=AccountType.income)
        offset = self.account(type=AccountType.income)

        self._post(account, offset, 1)
        account.rebuild_running_totals()
        self._post(account, offset, 1)

        self.assertEqual(account.running_totals.count(), 1)
        self.assertEqual(account.get_simple_balance(), Balance([Money(2, "EUR")]))

    @override_settings(HORDAK_CHECKPOINT_THRESHOLD=4)
    def test_leg_insert_auto_advances_once_threshold_is_reached(self):
        account = self.account(type=AccountType.income)
        offset = self.account(type=AccountType.income)

        self._post(account, offset, 1)
        account.rebuild_running_totals()
        self._post(account, offset, 1)
        self.assertEqual(account.running_totals.count(), 1)

        self._post(account, offset, 1)

        self.assertEqual(account.running_totals.count(), 2)
        self.assertEqual(account.get_simple_balance(), Balance([Money(3, "EUR")]))

    @override_settings(HORDAK_CHECKPOINT_THRESHOLD=4)
    def test_leg_insert_uses_matching_currency_checkpoint_for_threshold(self):
        account = self.account(type=AccountType.income, currencies=["EUR", "USD"])
        offset = self.account(type=AccountType.income, currencies=["EUR", "USD"])

        self._post(account, offset, 1, currency="EUR")
        account.rebuild_running_totals()
        eur_checkpoint = account.running_totals.get(currency="EUR")

        self._post(account, offset, 1, currency="USD")
        RunningTotal.objects.create(
            account=account,
            currency="USD",
            balance=Money(1, "USD"),
            includes_leg_id=account.legs.order_by("-id")
            .values_list("id", flat=True)
            .first(),
        )
        RunningTotal.objects.filter(pk=eur_checkpoint.pk).update(includes_leg_id=1)

        self._post(account, offset, 1, currency="EUR")

        self.assertEqual(account.running_totals.filter(currency="EUR").count(), 2)
        latest_eur = (
            account.running_totals.filter(currency="EUR")
            .order_by("-includes_leg_id")
            .first()
        )
        self.assertEqual(
            latest_eur.includes_leg_id,
            account.legs.order_by("-id").values_list("id", flat=True).first(),
        )

    def test_advance_checkpoint_skips_currency_that_is_already_current(self):
        account = self.account(type=AccountType.income, currencies=["EUR", "USD"])
        offset = self.account(type=AccountType.income, currencies=["EUR", "USD"])

        self._post(account, offset, 1, currency="EUR")
        self._post(account, offset, 1, currency="USD")
        account.rebuild_running_totals()
        usd_checkpoint = account.running_totals.get(currency="USD")
        RunningTotal.objects.filter(currency="EUR", account=account).update(
            includes_leg_id=1
        )

        self._post(account, offset, 1, currency="EUR")
        RunningTotal.objects.filter(pk=usd_checkpoint.pk).update(
            includes_leg_id=account.legs.order_by("-id")
            .values_list("id", flat=True)
            .first()
        )

        account.advance_checkpoint()

        latest_usd = (
            account.running_totals.filter(currency="USD")
            .order_by("-includes_leg_id")
            .first()
        )
        self.assertEqual(
            latest_usd.includes_leg_id,
            account.legs.order_by("-id").values_list("id", flat=True).first(),
        )

    def test_receiver_save_skips_missing_previous_account(self):
        account = self.account(type=AccountType.income)
        offset = self.account(type=AccountType.income)
        with db_transaction.atomic():
            transaction = Transaction.objects.create()
            leg = Leg.objects.create(
                transaction=transaction,
                account=account,
                credit=Money(10, "EUR"),
            )
            Leg.objects.create(
                transaction=transaction,
                account=offset,
                debit=Money(10, "EUR"),
            )

        account.rebuild_running_totals()
        leg._running_total_previous_account_id = 999999
        maintain_running_totals_on_leg_save(
            sender=Leg,
            instance=leg,
            created=False,
        )

        self.assertEqual(account.running_totals.count(), 0)

    def test_receiver_delete_skips_missing_account(self):
        class DeletedLeg:
            account_id = 999999

        maintain_running_totals_on_leg_delete(sender=Leg, instance=DeletedLeg())

    @override_settings(HORDAK_CHECKPOINT_THRESHOLD=2)
    def test_leg_insert_does_not_auto_advance_without_checkpoint(self):
        account = self.account(type=AccountType.income)
        offset = self.account(type=AccountType.income)

        self._post(account, offset, 1)

        self.assertEqual(account.running_totals.count(), 0)

    def test_recalculate_running_totals_command_builds_checkpoints(self):
        account = self.account(type=AccountType.income)
        offset = self.account(type=AccountType.income)
        self._post(account, offset, 12)

        call_command("recalculate_running_totals", stdout=StringIO())

        self.assertEqual(
            account.running_totals.get(currency="EUR").balance, Money(12, "EUR")
        )

    def test_recalculate_running_totals_command_check_reports_missing_checkpoint(self):
        account = self.account(type=AccountType.income)
        offset = self.account(type=AccountType.income)
        self._post(account, offset, 12)
        stdout = StringIO()

        call_command("recalculate_running_totals", "--check", stdout=stdout)

        self.assertIn("Running totals are INCORRECT", stdout.getvalue())
        self.assertIn(
            f"Account {account.name} has no checkpoint for EUR", stdout.getvalue()
        )
        self.assertEqual(account.running_totals.count(), 0)

    def test_recalculate_running_totals_command_check_reports_faulty_checkpoint(self):
        account = self.account(type=AccountType.income)
        offset = self.account(type=AccountType.income)
        self._post(account, offset, 12)
        account.rebuild_running_totals()
        account.running_totals.update(balance=Money(999, "EUR"))
        stdout = StringIO()

        call_command("recalculate_running_totals", "--check", stdout=stdout)

        self.assertIn(
            f"Account {account.name} has faulty running total for EUR",
            stdout.getvalue(),
        )
        self.assertIn("effective", stdout.getvalue())
        self.assertIn("should be", stdout.getvalue())

    @override_settings(ADMINS=[("Admin", "admin@example.com")])
    def test_recalculate_running_totals_command_check_can_mail_admins(self):
        account = self.account(type=AccountType.income)
        offset = self.account(type=AccountType.income)
        self._post(account, offset, 12)

        call_command("recalculate_running_totals", "--check", "--mail-admins")

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Running totals are incorrect", mail.outbox[0].subject)
        self.assertIn(account.name, mail.outbox[0].body)

    def test_recalculate_running_totals_command_check_reports_correct_state(self):
        account = self.account(type=AccountType.income)
        offset = self.account(type=AccountType.income)
        self._post(account, offset, 12)
        call_command("recalculate_running_totals", stdout=StringIO())
        stdout = StringIO()

        call_command("recalculate_running_totals", "--check", stdout=stdout)

        self.assertEqual(stdout.getvalue().strip(), "Running totals are correct")

    def test_recalculate_running_totals_command_rebuild_does_not_report_incorrect(self):
        account = self.account(type=AccountType.income)
        offset = self.account(type=AccountType.income)
        self._post(account, offset, 12)
        stdout = StringIO()

        call_command("recalculate_running_totals", stdout=stdout)

        self.assertNotIn("INCORRECT", stdout.getvalue())
        self.assertIn(
            "Rebuilt running total checkpoints for 2 accounts.", stdout.getvalue()
        )

    def test_recalculate_running_totals_command_can_keep_history(self):
        account = self.account(type=AccountType.income)
        offset = self.account(type=AccountType.income)
        self._post(account, offset, 10)
        call_command("recalculate_running_totals", stdout=StringIO())
        self._post(account, offset, 5)

        call_command("recalculate_running_totals", "--keep-history", stdout=StringIO())

        self.assertEqual(account.running_totals.filter(currency="EUR").count(), 2)
