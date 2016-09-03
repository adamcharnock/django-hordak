from django.db.utils import DatabaseError
from django.test.testcases import TestCase, TransactionTestCase
from django.core.management import call_command
from django.db import transaction as db_transaction

from hordak.models import Account, Transaction, Leg
from hordak import exceptions


class AccountTestCase(TestCase):

    def test_full_code(self):
        """
        Check that the full code for a account is correctly
        determined by combining its own code with those of its
        ancestors
        """
        account1 = Account.objects.create(name='Account 1', type=Account.TYPES.asset, code='5')
        account2 = Account.objects.create(parent=account1, name='Account 1', code='0')
        account3 = Account.objects.create(parent=account2, name='Account 1', code='9')

        self.assertEqual(account1.full_code, '5')
        self.assertEqual(account2.full_code, '50')
        self.assertEqual(account3.full_code, '509')

    def test_type_root(self):
        """Check we can set the type on a root account"""
        account1 = Account.objects.create(name='Account 1', type=Account.TYPES.asset, code='5')
        self.assertEqual(account1.type, Account.TYPES.asset)

    def test_type_leaf_create(self):
        """Check we CANNOT set the type upon creating a leaf account

        Only root accounts have a type
        """
        account1 = Account.objects.create(name='Account 1', type=Account.TYPES.asset, code='5')
        self.assertRaises(
            exceptions.AccountTypeOnLeafNode,
            Account.objects.create,
            parent=account1, type=Account.TYPES.asset, name='Account 1', code='0')


    def test_type_leaf_set(self):
        """Check we CANNOT set the type after we have created a leaf account

        Only root accounts have a type
        """
        account1 = Account.objects.create(name='Account 1', type=Account.TYPES.asset, code='5')
        account2 = Account.objects.create(parent=account1, name='Account 1', code='0')

        def set_it(account):
            account.type = Account.TYPES.asset

        self.assertRaises(
            exceptions.AccountTypeOnLeafNode,
            set_it,
            account2)

    def test_sign(self):
        asset = Account.objects.create(name='asset', type=Account.TYPES.asset, code='1')
        liability = Account.objects.create(name='liability', type=Account.TYPES.liability, code='2')
        income = Account.objects.create(name='income', type=Account.TYPES.income, code='3')
        expense = Account.objects.create(name='expense', type=Account.TYPES.expense, code='4')
        equity = Account.objects.create(name='equity', type=Account.TYPES.equity, code='5')

        self.assertEqual(asset.sign, -1)
        self.assertEqual(expense.sign, -1)

        self.assertEqual(liability.sign, 1)
        self.assertEqual(income.sign, 1)
        self.assertEqual(equity.sign, 1)

        self.assertEqual(len(Account.TYPES), 5, msg='Did not test all account types. Update this test.')


class LegTestCase(TransactionTestCase):

    def test_manager(self):
        account1 = Account.objects.create(name='account1', type=Account.TYPES.income, code='1')
        account2 = Account.objects.create(name='account2', type=Account.TYPES.income, code='2')

        with db_transaction.atomic():
            transaction = Transaction.objects.create()
            Leg.objects.create(transaction=transaction, account=account1, amount=100)
            Leg.objects.create(transaction=transaction, account=account2, amount=-100)

        self.assertEqual(Leg.objects.sum_amount(), 0)
        self.assertEqual(account1.legs.sum_amount(), 100)
        self.assertEqual(account2.legs.sum_amount(), -100)

    def test_postgres_trigger(self):
        """"
        Check the database enforces leg amounts summing to zero

        This is enforced by a postgres trigger applied in migration 0005.
        Note that this requires the test case extend TransactionTestCase,
        as the trigger is only run when changes are committed to the DB
        (which the normal TestCase will not do)
        """
        account = Account.objects.create(name='account1', type=Account.TYPES.income, code='1')
        transaction = Transaction.objects.create()
        self.assertRaises(DatabaseError, Leg.objects.create, transaction=transaction, account=account, amount=100)
