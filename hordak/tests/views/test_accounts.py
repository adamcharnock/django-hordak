from django.test import TestCase
from django.urls import reverse

from hordak.forms.accounts import AccountForm
from hordak.models import Account
from hordak.tests.utils import DataProvider


class AccountListViewTestCase(DataProvider, TestCase):
    def setUp(self):
        self.view_url = reverse("hordak:accounts_list")
        self.login()

        self.bank_account = self.account(is_bank_account=True, type=Account.TYPES.asset)
        self.income_account = self.account(is_bank_account=False, type=Account.TYPES.income)

    def test_get(self):
        response = self.client.get(self.view_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["accounts"].count(), 2)


class AccountCreateViewTestCase(DataProvider, TestCase):
    def setUp(self):
        self.view_url = reverse("hordak:accounts_create")
        self.login()

    def test_get(self):
        response = self.client.get(self.view_url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)
        self.assertEqual(response.context["form"]["code"].initial, "01")

    def test_post(self):
        response = self.client.post(
            self.view_url,
            data=dict(
                name="Test Account", code="01", type="IN", is_bank_account="", currencies="EUR, GBP"
            ),
        )
        if response.context:
            self.assertFalse(response.context["form"].errors)
        account = Account.objects.get()
        self.assertEqual(account.name, "Test Account")
        self.assertEqual(account.code, "01")
        self.assertEqual(account.type, Account.TYPES.income)
        self.assertEqual(account.is_bank_account, False)
        self.assertEqual(account.currencies, ["EUR", "GBP"])

    def test_bank_account_not_asset_account(self):
        """Bank accounts must be asset accounts"""
        form = AccountForm(
            data=dict(
                name="Test Account", code="01", type="IN", is_bank_account="yes", currencies="GBP"
            )
        )
        self.assertFalse(form.is_valid())
        error = form.errors["__all__"][0].lower()
        self.assertIn("bank account", error)
        self.assertIn("asset", error)

    def test_bank_account_single_currency(self):
        """Bank accounts may only have one currency"""
        form = AccountForm(
            data=dict(
                name="Test Account",
                code="01",
                type="AS",
                is_bank_account="yes",
                currencies="EUR, GBP",
            )
        )
        self.assertFalse(form.is_valid())
        error = form.errors["__all__"][0].lower()
        self.assertIn("bank account", error)
        self.assertIn("currency", error)

    def test_post_no_code(self):
        response = self.client.post(
            self.view_url,
            data=dict(
                name="Test Account", code="", type="IN", is_bank_account="", currencies="EUR, GBP"
            ),
        )
        if response.context:
            self.assertFalse(response.context["form"].errors)
        account = Account.objects.get()
        self.assertEqual(account.code, None)
        self.assertEqual(account.full_code, None)


class AccountUpdateViewTestCase(DataProvider, TestCase):
    def setUp(self):
        self.account1 = self.account(
            code="01", currencies=["USD"], type=Account.TYPES.expense, is_bank_account=False
        )
        self.view_url = reverse("hordak:accounts_update", args=[self.account1.uuid])
        self.login()

    def test_get(self):
        response = self.client.get(self.view_url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)
        self.assertEqual(response.context["form"]["code"].value(), "01")

    def test_post(self):
        response = self.client.post(
            self.view_url,
            data=dict(
                name="My Account",
                code="04",
                type="LI",
                is_bank_account="yes",
                currencies="EUR, GBP",
            ),
        )
        if response.context:
            self.assertFalse(response.context["form"].errors)

        self.account1.refresh_from_db()
        self.assertEqual(self.account1.name, "My Account")
        self.assertEqual(self.account1.code, "04")
        self.assertEqual(self.account1.type, Account.TYPES.expense)  # Not editable, so unchanged
        self.assertEqual(self.account1.is_bank_account, False)  # Not editable, so unchanged
        self.assertEqual(self.account1.currencies, ["USD"])  # Not editable, so unchanged

    def test_post_no_code(self):
        response = self.client.post(
            self.view_url,
            data=dict(
                name="My Account", code="", type="LI", is_bank_account="yes", currencies="EUR, GBP"
            ),
        )
        if response.context:
            self.assertFalse(response.context["form"].errors)

        self.account1.refresh_from_db()
        self.assertEqual(self.account1.code, None)
        self.assertEqual(self.account1.full_code, None)
