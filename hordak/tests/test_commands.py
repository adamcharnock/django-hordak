from django.core import mail
from django.core.management import call_command
from django.db import transaction as db_transaction
from django.test import override_settings
from django.test.testcases import TestCase
from django.test.testcases import TransactionTestCase as DbTransactionTestCase
from moneyed.classes import Money

from hordak.models import Account, Leg, RunningTotal, Transaction
from hordak.tests.utils import DataProvider


class CreateChartOfAccountsTestCase(TestCase):
    def test_simple(self):
        call_command("create_chart_of_accounts", *["--currency", "USD"])
        self.assertGreater(Account.objects.count(), 10)
        account = Account.objects.all()[0]
        self.assertEqual(account.currencies, ["USD"])

    def test_multi_currency(self):
        call_command("create_chart_of_accounts", *["--currency", "USD", "EUR"])
        self.assertGreater(Account.objects.count(), 10)
        account = Account.objects.all()[0]
        self.assertEqual(account.currencies, ["USD", "EUR"])


@override_settings(ADMINS=[("Admin", "foo@bar.cz")])
class RecalculateRunningTotalsTestCase(DataProvider, DbTransactionTestCase):
    def test_simple(self):
        account1 = self.account()
        account2 = self.account()
        with db_transaction.atomic():
            transaction = Transaction.objects.create()
            Leg.objects.create(
                transaction=transaction, account=account1, amount=Money(100, "EUR")
            )
            Leg.objects.create(
                transaction=transaction, account=account2, amount=Money(-100, "EUR")
            )

        RunningTotal.objects.all().delete()

        call_command("recalculate_running_totals")
        account1.refresh_from_db()
        account2.refresh_from_db()
        self.assertEqual(
            account1.running_totals.get(currency="EUR").balance, Money(100, "EUR")
        )
        self.assertEqual(
            account2.running_totals.get(currency="EUR").balance, Money(-100, "EUR")
        )

    def test_multi_currency(self):
        account1 = self.account(currencies=["EUR", "USD"])
        account2 = self.account(currencies=["EUR", "USD"])
        with db_transaction.atomic():
            transaction = Transaction.objects.create()
            Leg.objects.create(
                transaction=transaction, account=account1, amount=Money(100, "EUR")
            )
            Leg.objects.create(
                transaction=transaction, account=account2, amount=Money(-100, "EUR")
            )
            Leg.objects.create(
                transaction=transaction, account=account1, amount=Money(100, "USD")
            )
            Leg.objects.create(
                transaction=transaction, account=account2, amount=Money(-100, "USD")
            )

        RunningTotal.objects.all().delete()

        call_command("recalculate_running_totals")
        account1.refresh_from_db()
        account2.refresh_from_db()
        self.assertEqual(
            account1.running_totals.get(currency="EUR").balance, Money(100, "EUR")
        )
        self.assertEqual(
            account2.running_totals.get(currency="EUR").balance, Money(-100, "EUR")
        )
        self.assertEqual(
            account1.running_totals.get(currency="USD").balance, Money(100, "USD")
        )
        self.assertEqual(
            account2.running_totals.get(currency="USD").balance, Money(-100, "USD")
        )

    def test_check_mismatch(self):
        """
        The check option should return a non-zero exit code if the running totals
        are incorrect.
        """
        account1 = self.account()
        account2 = self.account()
        with db_transaction.atomic():
            transaction = Transaction.objects.create()
            Leg.objects.create(
                transaction=transaction, account=account1, amount=Money(100, "EUR")
            )
            Leg.objects.create(
                transaction=transaction, account=account2, amount=Money(-100, "EUR")
            )

        running_total = account1.running_totals.get()
        running_total.balance = Money(200, "EUR")
        running_total.save()

        ret_val = call_command("recalculate_running_totals", *["--check"])
        self.assertEqual(ret_val, "Running totals are incorrect")

    def test_mail_admins(self):
        """
        The mail-admins option should send an email if the running totals are
        incorrect.
        """
        account1 = self.account()
        account2 = self.account()
        with db_transaction.atomic():
            transaction = Transaction.objects.create()
            Leg.objects.create(
                transaction=transaction, account=account1, amount=Money(100, "EUR")
            )
            Leg.objects.create(
                transaction=transaction, account=account2, amount=Money(-100, "EUR")
            )

        running_total = account1.running_totals.get()
        running_total.balance = Money(200, "EUR")
        running_total.save()

        ret_val = call_command("recalculate_running_totals", *["--mail-admins"])
        self.assertEqual(ret_val, "Running totals are incorrect")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(
            mail.outbox[0].subject, "[Django] Running totals are incorrect"
        )
