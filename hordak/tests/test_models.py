from django.db.utils import DatabaseError, IntegrityError
from django.test.testcases import TestCase, TransactionTestCase as DbTransactionTestCase
from django.core.management import call_command
from django.db import transaction as db_transaction

from hordak.models import Account, Transaction, Leg, DEBIT, CREDIT
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


    def test_str_root(self):
        # Account code should not be rendered as we should not
        # associate transaction legs with non-leaf accounts
        account1 = Account.objects.create(name='Account 1', type=Account.TYPES.asset, code='5')
        account2 = Account.objects.create(parent=account1, name='Account 2', code='1')
        self.assertEqual(str(account1), 'Account 1')

    def test_str_child(self):
        account1 = Account.objects.create(name='Account 1', type=Account.TYPES.asset, code='5')
        account2 = Account.objects.create(parent=account1, name='Account 2', code='1')
        self.assertEqual(str(account2), 'Account 2 [51]')

    def test_str_root_no_data_unsaved(self):
        account1 = Account()
        account2 = Account(parent=account1)
        self.assertEqual(str(account1), 'Unnamed Account [-]')

    def test_str_child_no_data_unsaved(self):
        account1 = Account()
        account2 = Account(parent=account1)
        self.assertEqual(str(account2), 'Unnamed Account [-]')

    def test_type_root(self):
        """Check we can set the type on a root account"""
        account1 = Account.objects.create(name='Account 1', type=Account.TYPES.asset, code='5')
        self.assertEqual(account1.type, Account.TYPES.asset)

    def test_type_leaf(self):
        """Check we can set the type on a root account"""
        account1 = Account.objects.create(name='Account 1', type=Account.TYPES.asset, code='1')
        account2 = Account.objects.create(parent=account1, name='Account 2', code='1')
        self.assertEqual(account2.type, Account.TYPES.asset)

    def test_type_leaf_create(self):
        """Check we CANNOT set the type upon creating a leaf account

        Only root accounts have a type
        """
        account1 = Account.objects.create(name='Account 1', type=Account.TYPES.asset, code='5')
        self.assertRaises(
            exceptions.AccountTypeOnChildNode,
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
            exceptions.AccountTypeOnChildNode,
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

    def test_balance_simple(self):
        account1 = Account.objects.create(name='account1', type=Account.TYPES.income, code='1')
        account2 = Account.objects.create(name='account2', type=Account.TYPES.income, code='2')

        with db_transaction.atomic():
            transaction = Transaction.objects.create()
            Leg.objects.create(transaction=transaction, account=account1, amount=100)
            Leg.objects.create(transaction=transaction, account=account2, amount=-100)

        self.assertEqual(account1.simple_balance(), 100)
        self.assertEqual(account2.simple_balance(), -100)

    def test_balance(self):
        account1 = Account.objects.create(name='account1', type=Account.TYPES.income, code='1')
        account1_child = Account.objects.create(name='account1', code='1', parent=account1)
        account2 = Account.objects.create(name='account2', type=Account.TYPES.income, code='2')

        with db_transaction.atomic():
            transaction = Transaction.objects.create()
            Leg.objects.create(transaction=transaction, account=account1, amount=50)
            Leg.objects.create(transaction=transaction, account=account1_child, amount=50)
            Leg.objects.create(transaction=transaction, account=account2, amount=-100)

        self.assertEqual(account1.balance(), 100)


class LegTestCase(DbTransactionTestCase):

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

    def test_type(self):
        account1 = Account.objects.create(name='account1', type=Account.TYPES.income, code='1')
        account2 = Account.objects.create(name='account2', type=Account.TYPES.income, code='2')

        with db_transaction.atomic():
            transaction = Transaction.objects.create()
            leg1 = Leg.objects.create(transaction=transaction, account=account1, amount=100)
            leg2 = Leg.objects.create(transaction=transaction, account=account2, amount=-100)

        self.assertEqual(leg1.type, CREDIT)
        self.assertEqual(leg1.is_credit(), True)
        self.assertEqual(leg1.is_debit(), False)

        self.assertEqual(leg2.type, DEBIT)
        self.assertEqual(leg2.is_debit(), True)
        self.assertEqual(leg2.is_credit(), False)

    def test_model_zero_check(self):
        """Check the model ensures non-zero leg amounts"""
        account1 = Account.objects.create(name='account1', type=Account.TYPES.income, code='1')
        account2 = Account.objects.create(name='account2', type=Account.TYPES.income, code='2')

        with db_transaction.atomic():
            transaction = Transaction.objects.create()
            leg1 = Leg.objects.create(transaction=transaction, account=account1, amount=100)
            leg2 = Leg.objects.create(transaction=transaction, account=account2, amount=-100)

        leg3 = Leg(transaction=transaction, account=account2, amount=0)
        self.assertRaises(exceptions.ZeroAmountError, leg3.save)

    def test_db_zero_check(self):
        """Check the DB ensures non-zero leg amounts"""
        account1 = Account.objects.create(name='account1', type=Account.TYPES.income, code='1')
        account2 = Account.objects.create(name='account2', type=Account.TYPES.income, code='2')

        with db_transaction.atomic():
            transaction = Transaction.objects.create()
            leg1 = Leg.objects.create(transaction=transaction, account=account1, amount=100)
            leg2 = Leg.objects.create(transaction=transaction, account=account2, amount=-100)

        def set_zero_leg():
            # Use update() to bypass the check in Leg.save()
            Leg.objects.filter(pk=leg1.pk).update(amount=0)

        self.assertRaises(IntegrityError, set_zero_leg)


class TransactionTestCase(DbTransactionTestCase):

    def setUp(self):
        self.account1 = Account.objects.create(name='account1', type=Account.TYPES.income, code='1')
        self.account2 = Account.objects.create(name='account2', type=Account.TYPES.income, code='2')

    def test_balance(self):
        with db_transaction.atomic():
            transaction = Transaction.objects.create()
            Leg.objects.create(transaction=transaction, account=self.account1, amount=100)
            Leg.objects.create(transaction=transaction, account=self.account2, amount=-100)

        self.assertEqual(transaction.balance(), 0)

    def test_balance_no_legs(self):
        transaction = Transaction.objects.create()
        self.assertEqual(transaction.balance(), 0)
