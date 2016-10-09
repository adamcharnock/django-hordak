from datetime import date
from django.db.utils import DatabaseError, IntegrityError
from django.test.testcases import TestCase, TransactionTestCase as DbTransactionTestCase
from django.core.management import call_command
from django.db import transaction as db_transaction

from hordak.models import Account, Transaction, Leg, StatementImport, StatementLine, DEBIT, CREDIT
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

    def test_balance_simple_as_of(self):
        account1 = Account.objects.create(name='account1', type=Account.TYPES.income, code='1')
        account2 = Account.objects.create(name='account2', type=Account.TYPES.income, code='2')

        with db_transaction.atomic():
            transaction = Transaction.objects.create(date='2016-06-01')
            Leg.objects.create(transaction=transaction, account=account1, amount=100)
            Leg.objects.create(transaction=transaction, account=account2, amount=-100)

            transaction = Transaction.objects.create(date='2016-06-15')
            Leg.objects.create(transaction=transaction, account=account1, amount=50)
            Leg.objects.create(transaction=transaction, account=account2, amount=-50)

        self.assertEqual(account1.simple_balance(as_of='2016-01-01'), 0)    # before any transactions
        self.assertEqual(account1.simple_balance(as_of='2016-06-01'), 100)  # same date as first transaction
        self.assertEqual(account1.simple_balance(as_of='2016-06-10'), 100)  # between two transactions
        self.assertEqual(account1.simple_balance(as_of='2016-06-15'), 150)  # same date as second transaction
        self.assertEqual(account1.simple_balance(as_of='2020-01-01'), 150)  # after transactions

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

    def test_net_balance(self):
        bank = Account.objects.create(name='bank', type=Account.TYPES.asset, code='0')
        account1 = Account.objects.create(name='account1', type=Account.TYPES.income, code='1')
        account2 = Account.objects.create(name='account2', type=Account.TYPES.income, code='2')

        bank.transfer_to(account1, 100)
        bank.transfer_to(account2, 50)

        self.assertEqual(Account.objects.filter(_type=Account.TYPES.income).net_balance(), 150)

    def test_transfer_to(self):
        account1 = Account.objects.create(name='account1', type=Account.TYPES.income, code='1')
        account2 = Account.objects.create(name='account2', type=Account.TYPES.income, code='2')
        transaction = account1.transfer_to(account2, 500)
        self.assertEqual(transaction.legs.count(), 2)
        self.assertEqual(account1.balance(), -500)
        self.assertEqual(account2.balance(), 500)

    def test_transfer_pos_to_pos(self):
        src = Account.objects.create(name='src', type=Account.TYPES.income, code='1')
        dst = Account.objects.create(name='dst', type=Account.TYPES.income, code='2')
        src.transfer_to(dst, 100)
        self.assertEqual(src.balance(), -100)
        self.assertEqual(dst.balance(), 100)
        Account.validate_accounting_equation()

    def test_transfer_pos_to_neg(self):
        src = Account.objects.create(name='src', type=Account.TYPES.income, code='1')
        dst = Account.objects.create(name='dst', type=Account.TYPES.asset, code='2')
        src.transfer_to(dst, 100)
        self.assertEqual(src.balance(), 100)
        self.assertEqual(dst.balance(), 100)
        Account.validate_accounting_equation()

    def test_transfer_neg_to_pos(self):
        src = Account.objects.create(name='src', type=Account.TYPES.asset, code='1')
        dst = Account.objects.create(name='dst', type=Account.TYPES.income, code='2')
        src.transfer_to(dst, 100)
        self.assertEqual(src.balance(), 100)
        self.assertEqual(dst.balance(), 100)
        Account.validate_accounting_equation()

    def test_transfer_neg_to_neg(self):
        src = Account.objects.create(name='src', type=Account.TYPES.asset, code='1')
        dst = Account.objects.create(name='dst', type=Account.TYPES.asset, code='2')
        src.transfer_to(dst, 100)
        self.assertEqual(src.balance(), -100)
        self.assertEqual(dst.balance(), 100)
        Account.validate_accounting_equation()


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

    def test_type_zero(self):
        leg = Leg(amount=0)

        def get_type():
            leg.type

        self.assertRaises(exceptions.ZeroAmountError, get_type)


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


class StatementLineTestCase(DbTransactionTestCase):

    def setUp(self):
        self.bank = Account.objects.create(name='Bank', type=Account.TYPES.asset, code='1')
        self.sales = Account.objects.create(name='Sales', type=Account.TYPES.income, code='2')
        self.expenses = Account.objects.create(name='Expenses', type=Account.TYPES.expense, code='3')

        self.statement_import = StatementImport.objects.create(bank_account=self.bank)

    def test_is_reconciled(self):
        line = StatementLine.objects.create(
            date='2016-01-01',
            statement_import=self.statement_import,
            amount=100,
        )
        self.assertEqual(line.is_reconciled, False)
        line.transaction = Transaction()
        self.assertEqual(line.is_reconciled, True)

    def test_create_transaction_money_in(self):
        """Call StatementLine.create_transaction() for a sale"""
        line = StatementLine.objects.create(
            date='2016-01-01',
            statement_import=self.statement_import,
            amount=100,
        )
        line.refresh_from_db()

        transaction = line.create_transaction(self.sales)
        self.assertEqual(transaction.legs.count(), 2)
        self.assertEqual(transaction.date, date(2016, 1, 1))
        self.assertEqual(self.bank.balance(), 100)
        self.assertEqual(self.sales.balance(), 100)
        line.refresh_from_db()
        self.assertEqual(line.transaction, transaction)
        Account.validate_accounting_equation()

    def test_create_transaction_money_out(self):
        """Call StatementLine.create_transaction() for an expense"""
        line = StatementLine.objects.create(
            date='2016-01-01',
            statement_import=self.statement_import,
            amount=-100,
        )
        line.refresh_from_db()

        transaction = line.create_transaction(self.expenses)
        self.assertEqual(transaction.legs.count(), 2)
        self.assertEqual(transaction.date, date(2016, 1, 1))
        self.assertEqual(self.bank.balance(), -100)
        self.assertEqual(self.expenses.balance(), 100)
        line.refresh_from_db()
        self.assertEqual(line.transaction, transaction)
        Account.validate_accounting_equation()
