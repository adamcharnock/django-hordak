from django.contrib.auth import get_user_model
from django.test.testcases import TestCase
from django.urls import reverse

from hordak.models import AccountType, Leg, Transaction
from hordak.tests.utils import DataProvider


class AdminTestCase(DataProvider, TestCase):
    def setUp(self):
        self.user_account = self.account(name="User account", type="")
        self.user_subaccount = self.account(
            name="User account", parent=self.user_account
        )
        self.bank_account = self.account(
            name="Bank account", is_bank_account=True, type=AccountType.asset
        )
        self.income_account = self.account(
            is_bank_account=False, type=AccountType.income
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
        self.assertContains(
            res, '<td class="field-balance_sum">10.000000</td>', html=True
        )
        self.assertContains(res, '<td class="field-balance_sum">-</td>', html=True)
        self.assertContains(res, '<td class="field-type_">-</td>', html=True)
        self.assertContains(res, '<td class="field-type_">Income</td>', html=True)
        self.assertContains(res, '<td class="field-type_">Asset</td>', html=True)

    def test_search_query(self):
        """Test that search query works"""
        superuser = get_user_model().objects.create_superuser(username="superuser")
        self.client.force_login(superuser)
        url = reverse("admin:hordak_account_changelist")
        res = self.client.get(url + "?q=Bank")
        self.assertContains(
            res,
            f'<a href="/admin/hordak/account/{self.bank_account.id}/change/'
            '?_changelist_filters=q%3DBank">Bank account</a>',
            html=True,
        )
        self.assertContains(res, '<p class="paginator">1 account</p>', html=True)

    def test_filter_query(self):
        """Test that filter query works"""
        superuser = get_user_model().objects.create_superuser(username="superuser")
        self.client.force_login(superuser)
        url = reverse("admin:hordak_account_changelist")
        res = self.client.get(url + "?type__exact=AS")
        self.assertContains(
            res,
            f'<a href="/admin/hordak/account/{self.bank_account.id}/change/'
            '?_changelist_filters=type__exact%3DAS">Bank account</a>',
            html=True,
        )
        self.assertContains(res, '<p class="paginator">1 account</p>', html=True)

    def test_filter_query_liability(self):
        """Test that filter query works"""
        superuser = get_user_model().objects.create_superuser(username="superuser")
        self.client.force_login(superuser)
        url = reverse("admin:hordak_account_changelist")
        res = self.client.get(url + "?type__exact=LI")
        self.assertContains(res, '<p class="paginator">0 accounts</p>', html=True)

    def test_account_edit(self):
        """Test account edit page"""
        superuser = get_user_model().objects.create_superuser(username="superuser")
        self.client.force_login(superuser)
        url = reverse("admin:hordak_account_change", args=(self.bank_account.id,))
        res = self.client.get(url)
        self.assertContains(
            res,
            '<input type="text" name="name" value="Bank account" '
            'class="vTextField" maxlength="255" required id="id_name">',
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

    def test_transaction_list_queries(self):
        for _ in range(0, 50):
            transaction = Transaction.objects.create()
            Leg.objects.create(
                amount=-10, account=self.bank_account, transaction=transaction
            )
            Leg.objects.create(
                amount=10, account=self.income_account, transaction=transaction
            )

        superuser = get_user_model().objects.create_superuser(username="superuser")
        self.client.force_login(superuser)
        url = reverse("admin:hordak_transaction_changelist")
        with self.assertNumQueries(8):
            res = self.client.get(url)
        self.assertEqual(res.status_code, 200)

    def test_leg_list(self):
        """Test the leg listing loads"""
        superuser = get_user_model().objects.create_superuser(username="superuser")
        self.client.force_login(superuser)
        url = reverse("admin:hordak_leg_changelist")
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)

    def test_legview_list(self):
        """Test the leg view listing loads"""
        superuser = get_user_model().objects.create_superuser(username="superuser")
        self.client.force_login(superuser)
        url = reverse("admin:hordak_legview_changelist")
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
