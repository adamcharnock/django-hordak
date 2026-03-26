from django.core import mail
from django.core.management import call_command
from django.db import transaction as db_transaction
from django.db.models import Max
from django.test import override_settings
from django.test.testcases import TestCase
from django.test.testcases import TransactionTestCase as DbTransactionTestCase
from django.utils.translation import activate, get_language, to_locale
from moneyed.classes import Money

from hordak.models import Account, Leg, RunningTotal, Transaction
from hordak.tests.utils import DataProvider
from hordak.utilities.currency import Balance


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
    def setUp(self):
        super().setUp()
        self._orig_locale = to_locale(get_language())
        activate("en-US")

    def tearDown(self):
        activate(self._orig_locale)
        super().tearDown()

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
        rt1 = (
            account1.running_totals.filter(currency="EUR")
            .order_by("-includes_leg_id")
            .first()
        )
        rt2 = (
            account2.running_totals.filter(currency="EUR")
            .order_by("-includes_leg_id")
            .first()
        )
        self.assertEqual(rt1.balance, Money(100, "EUR"))
        self.assertEqual(rt2.balance, Money(-100, "EUR"))
        max1 = Leg.objects.filter(account=account1).aggregate(m=Max("id"))["m"]
        max2 = Leg.objects.filter(account=account2).aggregate(m=Max("id"))["m"]
        self.assertEqual(rt1.includes_leg_id, max1)
        self.assertEqual(rt2.includes_leg_id, max2)

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
            account1.running_totals.filter(currency="EUR")
            .order_by("-includes_leg_id")
            .first()
            .balance,
            Money(100, "EUR"),
        )
        self.assertEqual(
            account2.running_totals.filter(currency="EUR")
            .order_by("-includes_leg_id")
            .first()
            .balance,
            Money(-100, "EUR"),
        )
        self.assertEqual(
            account1.running_totals.filter(currency="USD")
            .order_by("-includes_leg_id")
            .first()
            .balance,
            Money(100, "USD"),
        )
        self.assertEqual(
            account2.running_totals.filter(currency="USD")
            .order_by("-includes_leg_id")
            .first()
            .balance,
            Money(-100, "USD"),
        )

    def test_check_mismatch(self):
        """
        The check option should return a non-zero exit code if the running totals
        are incorrect.
        """
        account1 = self.account()
        account2 = self.account()
        account1.update_running_totals()
        account2.update_running_totals()
        with db_transaction.atomic():
            transaction = Transaction.objects.create()
            Leg.objects.create(
                transaction=transaction, account=account1, amount=Money(100, "EUR")
            )
            Leg.objects.create(
                transaction=transaction, account=account2, amount=Money(-100, "EUR")
            )

        running_total = account1.running_totals.order_by("-includes_leg_id").first()
        running_total.balance = Money(200, "EUR")
        running_total.save()

        ret_val = call_command("recalculate_running_totals", *["--check"])
        self.assertIn("Running totals are INCORRECT", ret_val)
        self.assertIn("Account Account 1 has faulty running total for EUR", ret_val)
        self.assertRegex(ret_val, r"100")
        self.assertRegex(ret_val, r"200")

    def test_mail_admins(self):
        """
        The mail-admins option should send an email if the running totals are
        incorrect.
        """
        account1 = self.account()
        account2 = self.account()
        account1.update_running_totals()
        account2.update_running_totals()
        with db_transaction.atomic():
            transaction = Transaction.objects.create()
            Leg.objects.create(
                transaction=transaction, account=account1, amount=Money(100, "EUR")
            )
            Leg.objects.create(
                transaction=transaction, account=account2, amount=Money(-100, "EUR")
            )

        running_total = account1.running_totals.order_by("-includes_leg_id").first()
        running_total.balance = Money(200, "EUR")
        running_total.save()

        ret_val = call_command("recalculate_running_totals", *["--mail-admins"])
        self.assertIn("Running totals are INCORRECT", ret_val)
        self.assertIn("Account Account 1 has faulty running total for EUR", ret_val)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(
            mail.outbox[0].subject, "[Django] Running totals are incorrect"
        )
        self.assertIn(
            "Running totals are incorrect for some accounts", mail.outbox[0].body
        )
        self.assertIn(
            "Account Account 1 has faulty running total for EUR", mail.outbox[0].body
        )

    def test_keep_history_appends_checkpoints(self):
        account1 = self.account()
        account2 = self.account()
        with db_transaction.atomic():
            transaction = Transaction.objects.create()
            Leg.objects.create(
                transaction=transaction, account=account1, amount=Money(10, "EUR")
            )
            Leg.objects.create(
                transaction=transaction, account=account2, amount=Money(-10, "EUR")
            )
        RunningTotal.objects.all().delete()
        call_command("recalculate_running_totals")
        self.assertEqual(account1.running_totals.filter(currency="EUR").count(), 1)
        with db_transaction.atomic():
            transaction = Transaction.objects.create()
            Leg.objects.create(
                transaction=transaction, account=account1, amount=Money(5, "EUR")
            )
            Leg.objects.create(
                transaction=transaction, account=account2, amount=Money(-5, "EUR")
            )
        call_command("recalculate_running_totals", "--keep-history")
        self.assertEqual(account1.running_totals.filter(currency="EUR").count(), 2)
        self.assertEqual(account1.simple_balance(), Balance([Money(15, "EUR")]))
