from datetime import date
from django.db.utils import DatabaseError, IntegrityError
from django.test.testcases import (
    TestCase,
    TransactionTestCase as DbTransactionTestCase,
    TransactionTestCase,
)
from django.db import transaction as db_transaction
from moneyed.classes import Money

from hordak.models import Account, Transaction, Leg, StatementImport, StatementLine, DEBIT, CREDIT
from hordak import exceptions
from hordak.tests.utils import DataProvider
from hordak.utilities.currency import Balance


class AccountTestCase(DataProvider, TransactionTestCase):
    def test_str_root(self):
        # Account code should not be rendered as we should not
        # associate transaction legs with non-leaf accounts
        account1 = self.account(name="Account 1", code="5")
        account2 = self.account(parent=account1, code="1")
        self.assertEqual(str(account1), "Account 1")

    def test_str_root_no_code(self):
        # Account code should not be rendered as we should not
        # associate transaction legs with non-leaf accounts
        account1 = self.account(name="Account 1")
        account2 = self.account(parent=account1)
        self.assertEqual(str(account1), "Account 1")

    def test_str_child(self):
        account1 = self.account(code="5")
        account2 = self.account(parent=account1, name="Account 2", code="1")
        account2.refresh_from_db()
        self.assertEqual(str(account2).replace("\xa0", ""), "51 Account 2 [€0.00]")

    def test_str_root_no_data_unsaved(self):
        account1 = Account()
        account2 = Account(parent=account1)
        self.assertEqual(str(account1), "Unnamed Account")

    def test_str_child_no_data_unsaved(self):
        account1 = Account()
        account2 = Account(parent=account1)
        self.assertEqual(str(account2), "Unnamed Account")

    def test_type_root(self):
        """Check we can set the type on a root account"""
        account1 = self.account(type=Account.TYPES.asset)
        self.assertEqual(account1.type, Account.TYPES.asset)

    def test_type_leaf(self):
        """Check the type gets set on the leaf account (via db trigger)"""
        account1 = self.account(type=Account.TYPES.asset)
        account2 = self.account(parent=account1)
        account2.refresh_from_db()
        self.assertEqual(account2.type, Account.TYPES.asset)

    def test_type_leaf_create(self):
        """Check set the type upon creation has no effect on child accounts

        Account types are determined by the root node
        """
        account1 = self.account(type=Account.TYPES.asset)
        account2 = Account.objects.create(
            parent=account1, type=Account.TYPES.income, code="1", currencies=["EUR"]
        )
        self.assertEqual(account2.type, Account.TYPES.asset)

    def test_type_leaf_set(self):
        """Check setting account type leaf account has not effect

        Account types are determined by the root node
        """
        account1 = self.account(type=Account.TYPES.asset)
        account2 = self.account(parent=account1)
        account2.type = Account.TYPES.income
        account2.save()
        self.assertEqual(account2.type, Account.TYPES.asset)

    def test_sign(self):
        asset = self.account(type=Account.TYPES.asset)
        liability = self.account(type=Account.TYPES.liability)
        income = self.account(type=Account.TYPES.income)
        expense = self.account(type=Account.TYPES.expense)
        equity = self.account(type=Account.TYPES.equity)
        trading = self.account(type=Account.TYPES.trading)

        self.assertEqual(asset.sign, -1)
        self.assertEqual(expense.sign, -1)

        self.assertEqual(liability.sign, 1)
        self.assertEqual(income.sign, 1)
        self.assertEqual(equity.sign, 1)
        self.assertEqual(trading.sign, 1)

        self.assertEqual(
            len(Account.TYPES), 6, msg="Did not test all account types. Update this test."
        )

    def test_balance_simple(self):
        account1 = self.account()
        account2 = self.account()

        with db_transaction.atomic():
            transaction = Transaction.objects.create()
            Leg.objects.create(transaction=transaction, account=account1, amount=Money(100, "EUR"))
            Leg.objects.create(transaction=transaction, account=account2, amount=Money(-100, "EUR"))

        self.assertEqual(account1.simple_balance(), Balance(100, "EUR"))
        self.assertEqual(account2.simple_balance(), Balance(-100, "EUR"))

    def test_balance_3legs(self):
        account1 = self.account()
        account2 = self.account()
        account3 = self.account()

        with db_transaction.atomic():
            transaction = Transaction.objects.create()
            Leg.objects.create(transaction=transaction, account=account1, amount=Money(100, "EUR"))
            Leg.objects.create(transaction=transaction, account=account2, amount=Money(-40, "EUR"))
            Leg.objects.create(transaction=transaction, account=account3, amount=Money(-60, "EUR"))

        self.assertEqual(account1.simple_balance(), Balance(100, "EUR"))
        self.assertEqual(account2.simple_balance(), Balance(-40, "EUR"))
        self.assertEqual(account3.simple_balance(), Balance(-60, "EUR"))

    def test_balance_simple_as_of(self):
        account1 = self.account()
        account2 = self.account()

        with db_transaction.atomic():
            transaction = Transaction.objects.create(date="2016-06-01")
            Leg.objects.create(transaction=transaction, account=account1, amount=Money(100, "EUR"))
            Leg.objects.create(transaction=transaction, account=account2, amount=Money(-100, "EUR"))

            transaction = Transaction.objects.create(date="2016-06-15")
            Leg.objects.create(transaction=transaction, account=account1, amount=Money(50, "EUR"))
            Leg.objects.create(transaction=transaction, account=account2, amount=Money(-50, "EUR"))

        self.assertEqual(
            account1.simple_balance(as_of="2016-01-01"), Balance(0, "EUR")
        )  # before any transactions
        self.assertEqual(
            account1.simple_balance(as_of="2016-06-01"), Balance(100, "EUR")
        )  # same date as first transaction
        self.assertEqual(
            account1.simple_balance(as_of="2016-06-10"), Balance(100, "EUR")
        )  # between two transactions
        self.assertEqual(
            account1.simple_balance(as_of="2016-06-15"), Balance(150, "EUR")
        )  # same date as second transaction
        self.assertEqual(
            account1.simple_balance(as_of="2020-01-01"), Balance(150, "EUR")
        )  # after transactions

    def test_balance_simple_zero(self):
        account1 = self.account()
        account2 = self.account()

        self.assertEqual(account1.simple_balance(), Balance(0, "EUR"))
        self.assertEqual(account2.simple_balance(), Balance(0, "EUR"))

    def test_balance_kwargs(self):
        account1 = self.account()
        account2 = self.account()

        with db_transaction.atomic():
            transaction = Transaction.objects.create(date="2016-06-01")
            Leg.objects.create(
                transaction=transaction, account=account1, amount=100, amount_currency="EUR"
            )
            Leg.objects.create(
                transaction=transaction, account=account2, amount=-100, amount_currency="EUR"
            )

            transaction = Transaction.objects.create(date="2016-06-15")
            Leg.objects.create(
                transaction=transaction, account=account1, amount=50, amount_currency="EUR"
            )
            Leg.objects.create(
                transaction=transaction, account=account2, amount=-50, amount_currency="EUR"
            )

        self.assertEqual(account1.balance(transaction__date__gte="2016-06-15"), Balance(50, "EUR"))

    def test_balance(self):
        account1 = self.account(type=Account.TYPES.income)
        account1_child = self.account(type=Account.TYPES.income, parent=account1)
        account2 = self.account(type=Account.TYPES.income)

        with db_transaction.atomic():
            transaction = Transaction.objects.create()
            Leg.objects.create(
                transaction=transaction, account=account1, amount=50, amount_currency="EUR"
            )
            Leg.objects.create(
                transaction=transaction, account=account1_child, amount=50, amount_currency="EUR"
            )
            Leg.objects.create(
                transaction=transaction, account=account2, amount=-100, amount_currency="EUR"
            )

        self.assertEqual(account1.balance(), Balance(100, "EUR"))

    def test_net_balance(self):
        bank = self.account(type=Account.TYPES.asset)
        account1 = self.account(type=Account.TYPES.income)
        account2 = self.account(type=Account.TYPES.income)

        bank.transfer_to(account1, Money(100, "EUR"))
        bank.transfer_to(account2, Money(50, "EUR"))

        self.assertEqual(
            Account.objects.filter(type=Account.TYPES.income).net_balance(), Balance(150, "EUR")
        )

    def test_zero_balance_single(self):
        account = self.account(currencies=["GBP"])._zero_balance()
        self.assertEqual(account, Balance("0", "GBP"))

    def test_zero_balance_two(self):
        account = self.account(currencies=["GBP", "EUR"])._zero_balance()
        self.assertEqual(account, Balance("0", "GBP", "0", "EUR"))

    def test_zero_balance_zero(self):
        account = self.account(currencies=[])._zero_balance()
        self.assertEqual(account, Balance())

    def test_transfer_to(self):
        account1 = self.account(type=Account.TYPES.income)
        account2 = self.account(type=Account.TYPES.income)
        transaction = account1.transfer_to(account2, Money(500, "EUR"))
        self.assertEqual(transaction.legs.count(), 2)
        self.assertEqual(account1.balance(), Balance(-500, "EUR"))
        self.assertEqual(account2.balance(), Balance(500, "EUR"))

    def test_transfer_pos_to_pos(self):
        src = self.account(type=Account.TYPES.income)
        dst = self.account(type=Account.TYPES.income)
        src.transfer_to(dst, Money(100, "EUR"))
        self.assertEqual(src.balance(), Balance(-100, "EUR"))
        self.assertEqual(dst.balance(), Balance(100, "EUR"))
        Account.validate_accounting_equation()

    def test_transfer_pos_to_neg(self):
        src = self.account(type=Account.TYPES.income)
        dst = self.account(type=Account.TYPES.asset)
        src.transfer_to(dst, Money(100, "EUR"))
        self.assertEqual(src.balance(), Balance(100, "EUR"))
        self.assertEqual(dst.balance(), Balance(100, "EUR"))
        Account.validate_accounting_equation()

    def test_transfer_neg_to_pos(self):
        src = self.account(type=Account.TYPES.asset)
        dst = self.account(type=Account.TYPES.income)
        src.transfer_to(dst, Money(100, "EUR"))
        self.assertEqual(src.balance(), Balance(100, "EUR"))
        self.assertEqual(dst.balance(), Balance(100, "EUR"))
        Account.validate_accounting_equation()

    def test_transfer_neg_to_neg(self):
        src = self.account(type=Account.TYPES.asset)
        dst = self.account(type=Account.TYPES.asset)
        src.transfer_to(dst, Money(100, "EUR"))
        self.assertEqual(src.balance(), Balance(-100, "EUR"))
        self.assertEqual(dst.balance(), Balance(100, "EUR"))
        Account.validate_accounting_equation()

    def test_transfer_liability_to_expense(self):
        # When doing this it is probably safe to assume we want to the
        # liability account to contribute to an expense, therefore both should decrease
        src = self.account(type=Account.TYPES.liability)
        dst = self.account(type=Account.TYPES.expense)
        src.transfer_to(dst, Money(100, "EUR"))
        self.assertEqual(src.balance(), Balance(-100, "EUR"))
        self.assertEqual(dst.balance(), Balance(-100, "EUR"))
        Account.validate_accounting_equation()

    def test_transfer_expense_to_liability(self):
        # This should perform the reverse action to that in the above test_transfer_liability_to_expense()
        src = self.account(type=Account.TYPES.expense)
        dst = self.account(type=Account.TYPES.liability)
        src.transfer_to(dst, Money(100, "EUR"))
        self.assertEqual(src.balance(), Balance(100, "EUR"))
        self.assertEqual(dst.balance(), Balance(100, "EUR"))
        Account.validate_accounting_equation()

    def test_currency_exchange(self):
        src = self.account(type=Account.TYPES.asset, currencies=["GBP"])
        trading = self.account(type=Account.TYPES.trading, currencies=["GBP", "EUR"])
        dst = self.account(type=Account.TYPES.asset, currencies=["EUR"])
        src.transfer_to(trading, Money("100", "GBP"))
        trading.transfer_to(dst, Money("110", "EUR"))
        self.assertEqual(src.balance(), Balance("-100", "GBP"))
        self.assertEqual(trading.balance(), Balance("-100", "GBP", "110", "EUR"))
        self.assertEqual(dst.balance(), Balance("110", "EUR"))

    def test_full_code(self):
        """
        Check that the full code for a account is correctly set by the db trigger
        """
        account1 = self.account(code="5")
        account2 = self.account(parent=account1, code="0")
        account3 = self.account(parent=account2, code="9")

        self.assertEqual(account1.full_code, "5")
        self.assertEqual(account2.full_code, "50")
        self.assertEqual(account3.full_code, "509")

    def test_full_code_error_on_non_unique(self):
        account1 = self.account(code="5")
        account2 = self.account(parent=account1, code="0")

        with self.assertRaises(DatabaseError):
            self.account(parent=account1, code="0")

    def test_full_code_changes_on_update(self):
        account1 = self.account(code="5")
        account2 = self.account(parent=account1, code="0")
        account3 = self.account(parent=account2, code="9")
        account1.code = "A"
        account1.save()

        # Account 2 & 3 will need refreshing, but
        # account 1 was directly modified so logic
        # in the Account.save() method should have refreshed
        # it for us
        account2.refresh_from_db()
        account3.refresh_from_db()

        self.assertEqual(account1.full_code, "A")
        self.assertEqual(account2.full_code, "A0")
        self.assertEqual(account3.full_code, "A09")

    def test_full_code_changes_on_update_with_null_code(self):
        account1 = self.account(code="5")
        account2 = self.account(parent=account1, code="0")
        account3 = self.account(parent=account2, code="9")
        account1.code = None
        account1.save()

        account1.refresh_from_db()
        account2.refresh_from_db()
        account3.refresh_from_db()

        self.assertEqual(account1.full_code, None)
        self.assertEqual(account2.full_code, None)
        self.assertEqual(account3.full_code, None)

    def test_full_code_changes_on_update_with_empty_string_code(self):
        account1 = self.account(code="5")
        account2 = self.account(parent=account1, code="0")
        account3 = self.account(parent=account2, code="9")
        account1.code = ""
        account1.save()

        account1.refresh_from_db()
        account2.refresh_from_db()
        account3.refresh_from_db()

        self.assertEqual(account1.full_code, None)
        self.assertEqual(account2.full_code, None)
        self.assertEqual(account3.full_code, None)

    def test_child_asset_account_can_be_bank_account(self):
        """Regression test for: #Postgres check bank_accounts_are_asset_accounts
        does not work on child bank accounts

        See Also:
            https://github.com/adamcharnock/django-hordak/issues/4
        """
        account1 = self.account(type=Account.TYPES.asset)
        account2 = self.account(parent=account1, is_bank_account=True)
        account2.refresh_from_db()
        self.assertEqual(account2.type, Account.TYPES.asset)
        self.assertEqual(account2.is_bank_account, True)


class LegTestCase(DataProvider, DbTransactionTestCase):
    def test_manager(self):
        account1 = self.account(currencies=["USD"])
        account2 = self.account(currencies=["USD"])

        with db_transaction.atomic():
            transaction = Transaction.objects.create()
            Leg.objects.create(
                transaction=transaction, account=account1, amount=Money(100.12, "USD")
            )
            Leg.objects.create(
                transaction=transaction, account=account2, amount=Money(-80.06, "USD")
            )
            Leg.objects.create(
                transaction=transaction, account=account2, amount=Money(-20.06, "USD")
            )

        self.assertEqual(Leg.objects.sum_to_balance(), Balance())
        self.assertEqual(account1.legs.sum_to_balance(), Balance([Money("100.12", "USD")]))
        self.assertEqual(account2.legs.sum_to_balance(), Balance([Money("-100.12", "USD")]))

    def test_postgres_trigger_sum_zero(self):
        """"
        Check the database enforces leg amounts summing to zero

        This is enforced by a postgres trigger applied in migration 0005.
        Note that this requires the test case extend TransactionTestCase,
        as the trigger is only run when changes are committed to the DB
        (which the normal TestCase will not do)
        """
        account = self.account()
        transaction = Transaction.objects.create()

        with self.assertRaises(DatabaseError):
            Leg.objects.create(transaction=transaction, account=account, amount=100)

        with self.assertRaises(DatabaseError), db_transaction.atomic():
            # Also ensure we distinguish between currencies
            Leg.objects.create(transaction=transaction, account=account, amount=Money(100, "EUR"))
            Leg.objects.create(transaction=transaction, account=account, amount=Money(-100, "GBP"))

    def test_postgres_trigger_currency(self):
        """Check the database enforces that leg currencies must be supported by the leg's account"""
        account = self.account(currencies=("USD", "GBP"))
        transaction = Transaction.objects.create()

        with self.assertRaises(DatabaseError):
            Leg.objects.create(transaction=transaction, account=account, amount=Money(100, "EUR"))
            Leg.objects.create(transaction=transaction, account=account, amount=Money(-100, "EUR"))

    def test_postgres_trigger_bank_accounts_are_asset_accounts(self):
        """Check the database enforces that only asset accounts can be bank accounts"""
        self.account(is_bank_account=True, type=Account.TYPES.asset)
        with self.assertRaises(DatabaseError):
            self.account(is_bank_account=True, type=Account.TYPES.income)

    def test_type(self):
        account1 = self.account()
        account2 = self.account()

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

        with self.assertRaises(exceptions.ZeroAmountError):
            leg.type

    def test_model_zero_check(self):
        """Check the model ensures non-zero leg amounts"""
        account1 = self.account()
        account2 = self.account()

        with db_transaction.atomic():
            transaction = Transaction.objects.create()
            leg1 = Leg.objects.create(transaction=transaction, account=account1, amount=100)
            leg2 = Leg.objects.create(transaction=transaction, account=account2, amount=-100)

        leg3 = Leg(transaction=transaction, account=account2, amount=Money(0, "EUR"))
        self.assertRaises(exceptions.ZeroAmountError, leg3.save)

    def test_db_zero_check(self):
        """Check the DB ensures non-zero leg amounts"""
        account1 = self.account()
        account2 = self.account()

        with db_transaction.atomic():
            transaction = Transaction.objects.create()
            leg1 = Leg.objects.create(transaction=transaction, account=account1, amount=100)
            leg2 = Leg.objects.create(transaction=transaction, account=account2, amount=-100)

        with self.assertRaises(IntegrityError):
            # Use update() to bypass the check in Leg.save()
            Leg.objects.filter(pk=leg1.pk).update(amount=Money(0, "EUR"))

    def test_debits(self):
        src = self.account(type=Account.TYPES.asset)
        dst = self.account(type=Account.TYPES.asset)
        src.transfer_to(dst, Money(100, "EUR"))

        debit = Leg.objects.debits().get()
        credit = Leg.objects.credits().get()
        self.assertEqual(debit.account, src)
        self.assertEqual(credit.account, dst)

    def test_account_balance_after(self):
        src = self.account()
        dst = self.account()
        src.transfer_to(dst, Money(100, "EUR"))
        src.transfer_to(dst, Money(100, "EUR"))
        src.transfer_to(dst, Money(50, "EUR"))
        dst.transfer_to(src, Money(70, "EUR"))

        legs = Leg.objects.filter(account=dst).order_by("pk").all()
        self.assertEqual(legs[0].account_balance_after(), Balance("100", "EUR"))
        self.assertEqual(legs[1].account_balance_after(), Balance("200", "EUR"))
        self.assertEqual(legs[2].account_balance_after(), Balance("250", "EUR"))
        self.assertEqual(legs[3].account_balance_after(), Balance("180", "EUR"))

    def test_account_balance_after_out_of_order_ids(self):
        src = self.account()
        dst = self.account()
        # Take test_account_balance_after() as a reference test,
        # here we reverse the order of creation (to make the IDs go
        # backwards), and set the dates to force the order we want
        dst.transfer_to(src, Money(70, "EUR"), date="2000-01-15")
        src.transfer_to(dst, Money(50, "EUR"), date="2000-01-10")
        src.transfer_to(dst, Money(100, "EUR"), date="2000-01-05")
        src.transfer_to(dst, Money(100, "EUR"), date="2000-01-01")

        legs = Leg.objects.filter(account=dst).order_by("transaction__date").all()
        self.assertEqual(legs[0].account_balance_after(), Balance("100", "EUR"))
        self.assertEqual(legs[1].account_balance_after(), Balance("200", "EUR"))
        self.assertEqual(legs[2].account_balance_after(), Balance("250", "EUR"))
        self.assertEqual(legs[3].account_balance_after(), Balance("180", "EUR"))

    def test_account_balance_after_out_of_order_ids_on_same_day(self):
        src = self.account()
        dst = self.account()
        # A more complex version of the above test_account_balance_after_out_of_order_ids()
        # Here we require a mix of ordering by pk and by date because some
        # transactions are dated on the same day, yet we still have to infer a deterministic order
        # from somewhere, so we use the pk
        src.transfer_to(dst, Money(50, "EUR"), date="2000-01-15")
        dst.transfer_to(src, Money(70, "EUR"), date="2000-01-15")

        src.transfer_to(dst, Money(110, "EUR"), date="2000-01-05")
        src.transfer_to(dst, Money(100, "EUR"), date="2000-01-05")

        legs = Leg.objects.filter(account=dst).order_by("transaction__date").all()
        self.assertEqual(legs[0].account_balance_after(), Balance("110", "EUR"))
        self.assertEqual(legs[1].account_balance_after(), Balance("210", "EUR"))
        self.assertEqual(legs[2].account_balance_after(), Balance("260", "EUR"))
        self.assertEqual(legs[3].account_balance_after(), Balance("190", "EUR"))

    def test_account_balance_before_out_of_order_ids_on_same_day(self):
        src = self.account()
        dst = self.account()
        # A more complex version of the above test_account_balance_after_out_of_order_ids()
        # Here we require a mix of ordering by pk and by date because some
        # transactions are dated on the same day, yet we still have to infer a deterministic order
        # from somewhere, so we use the pk
        src.transfer_to(dst, Money(50, "EUR"), date="2000-01-15")
        dst.transfer_to(src, Money(70, "EUR"), date="2000-01-15")

        src.transfer_to(dst, Money(110, "EUR"), date="2000-01-05")
        src.transfer_to(dst, Money(100, "EUR"), date="2000-01-05")

        legs = Leg.objects.filter(account=dst).order_by("transaction__date").all()
        self.assertEqual(legs[0].account_balance_before(), Balance("0", "EUR"))
        self.assertEqual(legs[1].account_balance_before(), Balance("110", "EUR"))
        self.assertEqual(legs[2].account_balance_before(), Balance("210", "EUR"))
        self.assertEqual(legs[3].account_balance_before(), Balance("260", "EUR"))


class TransactionTestCase(DataProvider, DbTransactionTestCase):
    def setUp(self):
        self.account1 = self.account()
        self.account2 = self.account()

    def test_balance(self):
        with db_transaction.atomic():
            transaction = Transaction.objects.create()
            Leg.objects.create(transaction=transaction, account=self.account1, amount=100)
            Leg.objects.create(transaction=transaction, account=self.account2, amount=-100)

        self.assertEqual(transaction.balance(), 0)

    def test_balance_no_legs(self):
        transaction = Transaction.objects.create()
        self.assertEqual(transaction.balance(), 0)


class StatementLineTestCase(DataProvider, DbTransactionTestCase):
    def setUp(self):
        self.bank = self.account(name="Bank", type=Account.TYPES.asset, currencies=["EUR"])
        self.sales = self.account(name="Sales", type=Account.TYPES.income, currencies=["EUR"])
        self.expenses = self.account(
            name="Expenses", type=Account.TYPES.expense, currencies=["EUR"]
        )

        self.statement_import = StatementImport.objects.create(bank_account=self.bank, source="csv")

    def test_is_reconciled(self):
        line = StatementLine.objects.create(
            date="2016-01-01", statement_import=self.statement_import, amount=100
        )
        self.assertEqual(line.is_reconciled, False)
        line.transaction = Transaction()
        self.assertEqual(line.is_reconciled, True)

    def test_create_transaction_money_in(self):
        """Call StatementLine.create_transaction() for a sale"""
        line = StatementLine.objects.create(
            date="2016-01-01", statement_import=self.statement_import, amount=100
        )
        line.refresh_from_db()

        transaction = line.create_transaction(self.sales)
        self.assertEqual(transaction.legs.count(), 2)
        self.assertEqual(transaction.date, date(2016, 1, 1))
        self.assertEqual(self.bank.balance(), Balance(100, "EUR"))
        self.assertEqual(self.sales.balance(), Balance(100, "EUR"))
        line.refresh_from_db()
        self.assertEqual(line.transaction, transaction)
        Account.validate_accounting_equation()

    def test_create_transaction_money_out(self):
        """Call StatementLine.create_transaction() for an expense"""
        line = StatementLine.objects.create(
            date="2016-01-01", statement_import=self.statement_import, amount=-100
        )
        line.refresh_from_db()

        transaction = line.create_transaction(self.expenses)
        self.assertEqual(transaction.legs.count(), 2)
        self.assertEqual(transaction.date, date(2016, 1, 1))
        self.assertEqual(self.bank.balance(), Balance(-100, "EUR"))
        self.assertEqual(self.expenses.balance(), Balance(100, "EUR"))
        line.refresh_from_db()
        self.assertEqual(line.transaction, transaction)
        Account.validate_accounting_equation()
