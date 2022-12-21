from django.contrib.auth import get_user_model
from django.db import transaction as db_transaction
from django.test.testcases import TestCase
from django.urls import reverse
from moneyed.classes import Money

from hordak.admin import update_running_totals
from hordak.models import Account, Leg, RunningTotal, Transaction
from hordak.tests.utils import DataProvider


class TestAdmin(DataProvider, TestCase):
    def setUp(self):
        self.user_account = self.account(name="User account", type="")
        self.user_subaccount = self.account(
            name="User account", parent=self.user_account
        )
        self.bank_account = self.account(
            name="Bank account", is_bank_account=True, type=Account.TYPES.asset
        )
        self.income_account = self.account(
            is_bank_account=False, type=Account.TYPES.income
        )
        transaction = Transaction.objects.create()
        Leg.objects.create(
            amount=-10, account=self.bank_account, transaction=transaction
        )
        Leg.objects.create(
            amount=10, account=self.income_account, transaction=transaction
        )

    def test_account_list(self):
        """Test that accounts are listed on admin page"""
        superuser = get_user_model().objects.create_superuser(username="superuser")
        self.client.force_login(superuser)
        url = reverse("admin:hordak_account_changelist")
        res = self.client.get(url)
        self.assertContains(
            res,
            f'<a href="/admin/hordak/account/{self.bank_account.id}/change/">Bank account</a>',
            html=True,
        )
        self.assertContains(res, '<td class="field-balance_sum">10.00</td>', html=True)
        self.assertContains(res, '<td class="field-balance_sum">-</td>', html=True)
        self.assertContains(res, '<td class="field-type_">-</td>', html=True)
        self.assertContains(res, '<td class="field-type_">Income</td>', html=True)
        self.assertContains(res, '<td class="field-type_">Asset</td>', html=True)

    def test_account_edit(self):
        """Test account edit page"""
        superuser = get_user_model().objects.create_superuser(username="superuser")
        self.client.force_login(superuser)
        url = reverse("admin:hordak_account_change", args=(self.bank_account.id,))
        res = self.client.get(url)
        self.assertContains(
            res,
            '<input type="text" name="name" value="Bank account" '
            'class="vTextField" maxlength="50" required id="id_name">',
            html=True,
        )

    def test_transaction_list(self):
        """Test that transactions are listed on admin page"""
        superuser = get_user_model().objects.create_superuser(username="superuser")
        self.client.force_login(superuser)
        url = reverse("admin:hordak_transaction_changelist")
        res = self.client.get(url)
        self.assertContains(
            res, '<td class="field-debited_accounts">Account 4</td>', html=True
        )

    def test_update_running_totals(self):
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

        update_running_totals(None, None, Account.objects.all())
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
