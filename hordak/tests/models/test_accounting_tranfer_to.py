from django.test.testcases import TransactionTestCase as DbTransactionTestCase
from moneyed.classes import Money

from hordak.models import Account, Leg
from hordak.tests.utils import DataProvider
from hordak.utilities.currency import Balance


class AccountingTransferToTestCase(DataProvider, DbTransactionTestCase):
    def test_net_balance(self):
        bank = self.account(type=Account.TYPES.asset)
        account1 = self.account(type=Account.TYPES.income)
        account2 = self.account(type=Account.TYPES.income)

        # Income -> Bank is increasing both
        # https://accountingo.org/financial/double-entry/is-income-a-debit-or-credit/
        account1.accounting_transfer_to(bank, Money(100, "EUR"))
        account2.accounting_transfer_to(bank, Money(50, "EUR"))

        self.assertEqual(
            Account.objects.filter(type=Account.TYPES.income).net_balance(),
            Balance(150, "EUR"),
        )

    def test_accounting_transfer_to(self):
        account1 = self.account(type=Account.TYPES.income)
        account2 = self.account(type=Account.TYPES.income)
        transaction = account1.accounting_transfer_to(account2, Money(500, "EUR"))
        self.assertEqual(transaction.legs.count(), 2)
        self.assertEqual(account1.balance(), Balance(-500, "EUR"))
        self.assertEqual(account2.balance(), Balance(500, "EUR"))

    def test_accounting_transfer_to_not_money(self):
        account1 = self.account(type=Account.TYPES.income)
        with self.assertRaisesRegex(TypeError, "amount must be of type Money"):
            account1.accounting_transfer_to(account1, 500)

    def test_transfer_income_to_income(self):
        src = self.account(type=Account.TYPES.income)
        dst = self.account(type=Account.TYPES.income)
        src.accounting_transfer_to(dst, Money(100, "EUR"))
        self.assertEqual(src.balance(), Balance(-100, "EUR"))
        self.assertEqual(dst.balance(), Balance(100, "EUR"))
        Account.validate_accounting_equation()

    def test_transfer_income_to_asset(self):
        src = self.account(type=Account.TYPES.income)
        dst = self.account(type=Account.TYPES.asset)
        src.accounting_transfer_to(dst, Money(100, "EUR"))
        self.assertEqual(src.balance(), Balance(100, "EUR"))
        self.assertEqual(dst.balance(), Balance(100, "EUR"))
        Account.validate_accounting_equation()

    def test_transfer_asset_to_income(self):
        src = self.account(type=Account.TYPES.asset)
        dst = self.account(type=Account.TYPES.income)
        src.accounting_transfer_to(dst, Money(100, "EUR"))
        self.assertEqual(src.balance(), Balance(-100, "EUR"))
        self.assertEqual(dst.balance(), Balance(-100, "EUR"))
        Account.validate_accounting_equation()

    def test_transfer_asset_to_asset(self):
        src = self.account(type=Account.TYPES.asset)
        dst = self.account(type=Account.TYPES.asset)
        src.accounting_transfer_to(dst, Money(100, "EUR"))
        self.assertEqual(src.balance(), Balance(-100, "EUR"))
        self.assertEqual(dst.balance(), Balance(100, "EUR"))
        Account.validate_accounting_equation()

    def test_transfer_liability_to_expense(self):
        # Real world: Pay down expected Purchase (i.e. Invoice)
        # When doing this it is probably safe to assume we want to the
        # liability account to contribute to an expense, therefore both should decrease
        src = self.account(type=Account.TYPES.liability)
        dst = self.account(type=Account.TYPES.expense)
        src.accounting_transfer_to(dst, Money(100, "EUR"))
        self.assertEqual(src.balance(), Balance(100, "EUR"))
        self.assertEqual(dst.balance(), Balance(100, "EUR"))
        Account.validate_accounting_equation()

    def test_transfer_expense_to_liability(self):
        # Real world: Refund expected but not yet paid (i.e. Credit to Receivibles)
        # This should perform the reverse action to that in the above test_transfer_liability_to_expense()
        src = self.account(type=Account.TYPES.expense)
        dst = self.account(type=Account.TYPES.liability)
        src.accounting_transfer_to(dst, Money(100, "EUR"))
        self.assertEqual(src.balance(), Balance(-100, "EUR"))
        self.assertEqual(dst.balance(), Balance(-100, "EUR"))
        Account.validate_accounting_equation()

    def test_transfer_liability_to_asset(self):
        # Real world: Loan disbursement (i.e. Loan -> Cash)
        # When doing this it is probably safe to assume we want to the
        # liability account to contribute to an asset (i.e. cash), therefore both should decrease
        src = self.account(type=Account.TYPES.liability)
        dst = self.account(type=Account.TYPES.asset)
        src.accounting_transfer_to(dst, Money(100, "EUR"))
        self.assertEqual(src.balance(), Balance(100, "EUR"))
        self.assertEqual(dst.balance(), Balance(100, "EUR"))
        Account.validate_accounting_equation()

    def test_transfer_asset_to_liability(self):
        # Real world: Cash to pay down Debt (i.e. Cash -> Payables)
        # This should perform the reverse action to that in the above test_transfer_liability_to_asset()
        src = self.account(type=Account.TYPES.asset)
        dst = self.account(type=Account.TYPES.liability)
        src.accounting_transfer_to(dst, Money(100, "EUR"))
        self.assertEqual(src.balance(), Balance(-100, "EUR"))
        self.assertEqual(dst.balance(), Balance(-100, "EUR"))
        Account.validate_accounting_equation()

    def test_pay_rent_via_invoice(self):
        cash = self.account(type=Account.TYPES.asset)
        expense = self.account(type=Account.TYPES.expense)
        payable = self.account(type=Account.TYPES.liability)

        # Jul 1 - Landloard sends Invoice for Rent, $1000
        # We can't pay immediately, so we book it to a Payable (pay later), i.e. Loan
        payable.accounting_transfer_to(expense, Money(1000, "EUR"))
        self.assertEqual(expense.balance(), Balance(1000, "EUR"))
        self.assertEqual(payable.balance(), Balance(1000, "EUR"))

        # Jul 6 - We pay the landlord, $1000
        cash.accounting_transfer_to(payable, Money(1000, "EUR"))
        self.assertEqual(cash.balance(), Balance(-1000, "EUR"))
        self.assertEqual(payable.balance(), Balance(0, "EUR"))
        self.assertEqual(expense.balance(), Balance(1000, "EUR"))

    def test_cash_advance_loan_with_repayments(self):
        cash = self.account(type=Account.TYPES.asset)
        expense = self.account(type=Account.TYPES.expense)
        loan = self.account(type=Account.TYPES.liability)

        loan.accounting_transfer_to(cash, Money(10000, "EUR"))  # principal
        loan.accounting_transfer_to(expense, Money(1000, "EUR"))  # fee
        self.assertEqual(cash.balance(), Balance(10000, "EUR"))
        self.assertEqual(expense.balance(), Balance(1000, "EUR"))
        self.assertEqual(loan.balance(), Balance(11000, "EUR"))

        cash.accounting_transfer_to(loan, Money(100, "EUR"))  # repayment
        self.assertEqual(cash.balance(), Balance(9900, "EUR"))
        self.assertEqual(loan.balance(), Balance(10900, "EUR"))

    def test_currency_exchange(self):
        src = self.account(type=Account.TYPES.asset, currencies=["GBP"])
        trading = self.account(type=Account.TYPES.trading, currencies=["GBP", "EUR"])
        dst = self.account(type=Account.TYPES.asset, currencies=["EUR"])
        src.accounting_transfer_to(trading, Money("100", "GBP"))
        trading.accounting_transfer_to(dst, Money("110", "EUR"))
        self.assertEqual(src.balance(), Balance("-100", "GBP"))
        self.assertEqual(trading.balance(), Balance("-100", "GBP", "110", "EUR"))
        self.assertEqual(dst.balance(), Balance("110", "EUR"))

    def test_debits(self):
        src = self.account(type=Account.TYPES.asset)
        dst = self.account(type=Account.TYPES.asset)
        src.accounting_transfer_to(dst, Money(100, "EUR"))

        debit = Leg.objects.debits().get()
        credit = Leg.objects.credits().get()
        self.assertEqual(debit.account, src)
        self.assertEqual(credit.account, dst)

    def test_account_balance_after(self):
        src = self.account()
        dst = self.account()
        src.accounting_transfer_to(dst, Money(100, "EUR"))
        src.accounting_transfer_to(dst, Money(100, "EUR"))
        src.accounting_transfer_to(dst, Money(50, "EUR"))
        dst.accounting_transfer_to(src, Money(70, "EUR"))

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
        dst.accounting_transfer_to(src, Money(70, "EUR"), date="2000-01-15")
        src.accounting_transfer_to(dst, Money(50, "EUR"), date="2000-01-10")
        src.accounting_transfer_to(dst, Money(100, "EUR"), date="2000-01-05")
        src.accounting_transfer_to(dst, Money(100, "EUR"), date="2000-01-01")

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
        src.accounting_transfer_to(dst, Money(50, "EUR"), date="2000-01-15")
        dst.accounting_transfer_to(src, Money(70, "EUR"), date="2000-01-15")

        src.accounting_transfer_to(dst, Money(110, "EUR"), date="2000-01-05")
        src.accounting_transfer_to(dst, Money(100, "EUR"), date="2000-01-05")

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
        src.accounting_transfer_to(dst, Money(50, "EUR"), date="2000-01-15")
        dst.accounting_transfer_to(src, Money(70, "EUR"), date="2000-01-15")

        src.accounting_transfer_to(dst, Money(110, "EUR"), date="2000-01-05")
        src.accounting_transfer_to(dst, Money(100, "EUR"), date="2000-01-05")

        legs = Leg.objects.filter(account=dst).order_by("transaction__date").all()
        self.assertEqual(legs[0].account_balance_before(), Balance("0", "EUR"))
        self.assertEqual(legs[1].account_balance_before(), Balance("110", "EUR"))
        self.assertEqual(legs[2].account_balance_before(), Balance("210", "EUR"))
        self.assertEqual(legs[3].account_balance_before(), Balance("260", "EUR"))
