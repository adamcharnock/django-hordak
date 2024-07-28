import warnings

from django.db import transaction as db_transaction
from django.test import TestCase
from moneyed import Money

from hordak.models import (
    Account,
    AccountType,
    Leg,
    StatementImport,
    StatementLine,
    Transaction,
)
from hordak.tests.utils import BalanceUtils, DataProvider
from hordak.utilities.currency import Balance


warnings.simplefilter("ignore", category=DeprecationWarning)


class InitialEquityTestCase(DataProvider, TestCase):
    def setUp(self):
        self.cash = self.account(type=AccountType.asset)
        self.equity = self.account(type=AccountType.equity)

    def test_initial_equity(self):
        self.equity.transfer_to(self.cash, Money(100000, "EUR"))
        self.assertEqual(self.cash.get_balance(), Balance(100000, "EUR"))
        self.assertEqual(self.equity.get_balance(), Balance(100000, "EUR"))


class CapitalGainsTestCase(DataProvider, BalanceUtils, TestCase):
    def setUp(self):
        self.cash = self.account(type=AccountType.asset)
        self.equity = self.account(type=AccountType.equity)
        self.painting_cost = self.account(type=AccountType.asset)
        self.painting_unrealised_gain = self.account(type=AccountType.asset)
        self.income_realised_gain = self.account(type=AccountType.income)
        self.income_unrealised_gain = self.account(type=AccountType.income)

    def test_capital_gains(self):
        # Initial investment
        self.equity.transfer_to(self.cash, Money(100000, "EUR"))

        # Buy the painting
        self.cash.transfer_to(self.painting_cost, Money(100000, "EUR"))

        self.assertBalanceEqual(self.cash.get_balance(), 0)
        self.assertBalanceEqual(self.painting_cost.get_balance(), 100000)

        # Painting goes up in value by 10k
        self.income_unrealised_gain.transfer_to(
            self.painting_unrealised_gain, Money(10000, "EUR")
        )

        self.assertBalanceEqual(self.painting_unrealised_gain.get_balance(), 10000)
        self.assertBalanceEqual(self.income_unrealised_gain.get_balance(), 10000)

        # Painting goes up in value by 20k
        self.income_unrealised_gain.transfer_to(
            self.painting_unrealised_gain, Money(20000, "EUR")
        )

        self.assertBalanceEqual(self.painting_unrealised_gain.get_balance(), 30000)
        self.assertBalanceEqual(self.income_unrealised_gain.get_balance(), 30000)

        # We sell the painting (having accurately estimated the gains in value)
        self.income_realised_gain.transfer_to(
            self.income_unrealised_gain, Money(30000, "EUR")
        )
        self.painting_cost.transfer_to(self.cash, Money(100000, "EUR"))
        self.painting_unrealised_gain.transfer_to(self.cash, Money(30000, "EUR"))

        self.assertBalanceEqual(self.cash.get_balance(), 130000)
        self.assertBalanceEqual(self.painting_cost.get_balance(), 0)
        self.assertBalanceEqual(self.painting_unrealised_gain.get_balance(), 0)
        self.assertBalanceEqual(self.income_realised_gain.get_balance(), 30000)
        self.assertBalanceEqual(self.income_unrealised_gain.get_balance(), 0)


class PrepaidRentTestCase(DataProvider, BalanceUtils, TestCase):
    """Prepay three months rent in advance

    Based on example here:
    http://www.double-entry-bookkeeping.com/other-current-assets/prepaid-rent/
    """

    def setUp(self):
        self.cash = self.account(type=AccountType.asset)
        self.rent_expense = self.account(type=AccountType.expense)
        self.prepaid_rent = self.account(type=AccountType.asset)

    def test_prepaid_rent(self):
        # All accounts start at 0
        self.assertBalanceEqual(self.cash.get_balance(), 0)
        self.assertBalanceEqual(self.rent_expense.get_balance(), 0)
        self.assertBalanceEqual(self.prepaid_rent.get_balance(), 0)

        # Pay the rent to the landlord
        self.cash.transfer_to(self.prepaid_rent, Money(3000, "EUR"))
        self.assertBalanceEqual(self.cash.get_balance(), -3000)
        self.assertBalanceEqual(self.rent_expense.get_balance(), 0)
        self.assertBalanceEqual(self.prepaid_rent.get_balance(), 3000)

        # Now the end of the month, so turn 1k of rent into an expense
        self.prepaid_rent.transfer_to(self.rent_expense, Money(1000, "EUR"))
        self.assertBalanceEqual(self.cash.get_balance(), -3000)
        self.assertBalanceEqual(self.rent_expense.get_balance(), 1000)
        self.assertBalanceEqual(self.prepaid_rent.get_balance(), 2000)

        # Now two more months
        self.prepaid_rent.transfer_to(self.rent_expense, Money(1000, "EUR"))
        self.assertBalanceEqual(self.cash.get_balance(), -3000)
        self.assertBalanceEqual(self.rent_expense.get_balance(), 2000)
        self.assertBalanceEqual(self.prepaid_rent.get_balance(), 1000)

        self.prepaid_rent.transfer_to(self.rent_expense, Money(1000, "EUR"))
        self.assertBalanceEqual(self.cash.get_balance(), -3000)
        self.assertBalanceEqual(self.rent_expense.get_balance(), 3000)
        self.assertBalanceEqual(self.prepaid_rent.get_balance(), 0)

        Account.validate_accounting_equation()


class UtilityBillTestCase(DataProvider, TestCase):
    """Pay an estimateable sum every 3 months"""

    def setUp(self):
        self.cash = self.account(name="Cash", type=AccountType.asset)
        self.gas_expense = self.account(name="Gas Expense", type=AccountType.expense)
        self.gas_payable = self.account(name="Gas Payable", type=AccountType.liability)

    def test_utility_bill(self):
        # Month 1
        self.gas_payable.transfer_to(self.gas_expense, Money(100, "EUR"))

        self.assertEqual(self.cash.get_balance(), 0)
        self.assertEqual(self.gas_expense.get_balance(), Balance(100, "EUR"))
        self.assertEqual(self.gas_payable.get_balance(), Balance(100, "EUR"))

        # Month 2
        self.gas_payable.transfer_to(self.gas_expense, Money(100, "EUR"))

        self.assertEqual(self.cash.get_balance(), 0)
        self.assertEqual(self.gas_expense.get_balance(), Balance(200, "EUR"))
        self.assertEqual(self.gas_payable.get_balance(), Balance(200, "EUR"))

        # Month 3
        self.gas_payable.transfer_to(self.gas_expense, Money(100, "EUR"))

        self.assertEqual(self.cash.get_balance(), 0)
        self.assertEqual(self.gas_expense.get_balance(), Balance(300, "EUR"))
        self.assertEqual(self.gas_payable.get_balance(), Balance(300, "EUR"))

        # We receive the actual bill (we are moving a negative amount of money,
        # as this is an outgoing)
        self.cash.transfer_to(self.gas_payable, Money(300, "EUR"))

        # We are now 300 overdrawn, but the payable account has been cleared
        self.assertEqual(self.cash.get_balance(), Balance(-300, "EUR"))
        self.assertEqual(self.gas_expense.get_balance(), Balance(300, "EUR"))
        self.assertEqual(self.gas_payable.get_balance(), 0)

        Account.validate_accounting_equation()


class CommunalHouseholdTestCase(DataProvider, BalanceUtils, TestCase):
    def setUp(self):
        T = AccountType

        self.bank = self.account(name="Bank", type=T.asset, code="0")

        self.lia = self.account(name="Liabilities", type=T.liability, code="1")
        self.lia_elec_payable = self.account(
            name="Gas & Electricity Payable", parent=self.lia, code="2"
        )
        self.lia_rates_payable = self.account(
            name="Council Tax Payable", parent=self.lia, code="3"
        )

        self.inc = self.account(name="Income", type=T.income, code="2")
        self.inc_housemate = self.account(
            name="Housemate Income", parent=self.inc, code="1"
        )
        self.inc_housemate_1 = self.account(
            name="Housemate 1 Income", parent=self.inc_housemate, code="1"
        )
        self.inc_housemate_2 = self.account(
            name="Housemate 2 Income", parent=self.inc_housemate, code="2"
        )
        self.inc_donation = self.account(name="Donation", parent=self.inc, code="2")

        self.ex = self.account(name="Expenses", type=T.expense, code="3")
        self.ex_rent = self.account(name="Rent", parent=self.ex, code="1")
        self.ex_elec = self.account(name="Gas & Electricity", parent=self.ex, code="2")
        self.ex_rates = self.account(name="Council Tax", parent=self.ex, code="3")
        self.ex_food = self.account(name="Food", parent=self.ex, code="4")

    def create_incoming_rent_payments(self, amount1, amount2):
        statement_import = StatementImport.objects.create(
            bank_account=self.bank, source="csv"
        )
        line1 = StatementLine.objects.create(
            date="2016-01-01", statement_import=statement_import, amount=amount1
        )
        line2 = StatementLine.objects.create(
            date="2016-01-01", statement_import=statement_import, amount=amount2
        )
        line1.refresh_from_db()
        line2.refresh_from_db()
        return (line1, line2)

    def test_one_month(self):
        """Test payments over the course of three months

        Costs are:

          - 1000 rent per month (500/month/housemate)
          - 120 electricity per 3 months, estimate (20/month/housemate, estimate)
          - 180 rates per 3 months (30/month/housemate)
          - 140 food per month, estimate in arrears (70/month/housemate, estimate)

        Total: 620/month/housemate (with some estimation)

        """
        # Month 0 - We start by billing housemates for rent & gas & rates.
        # (for now we have no 'bills', but assume housemates have paid).
        # We have two housemates

        # Firstly, before we even collect any money from housemates, we spend some on food
        self.bank.transfer_to(self.ex_food, Money(35, "EUR"))
        self.bank.transfer_to(self.ex_food, Money(35, "EUR"))

        # Now we have negative money in the bank, and food expenses recorded
        self.assertBalanceEqual(self.bank.get_balance(), -70)
        self.assertBalanceEqual(self.ex_food.get_balance(), 70)

        # Also, the landlord wants the rent in advance, so that gets paid
        self.bank.transfer_to(self.ex_rent, Money(1000, "EUR"))
        # Now we are even more overdrawn
        self.assertBalanceEqual(self.bank.get_balance(), -70 + -1000)
        self.assertBalanceEqual(self.ex_rent.get_balance(), 1000)

        # Create two statement lines and assign each to the housemate income account
        line1, line2 = self.create_incoming_rent_payments(620, 620)
        line1.create_transaction(self.inc_housemate_1)
        line2.create_transaction(self.inc_housemate_2)

        # Create transaction for housemate1's payment
        with db_transaction.atomic():
            transaction = Transaction.objects.create(date="2016-01-31")
            Leg.objects.create(
                transaction=transaction, account=self.inc_housemate_1, debit=620
            )
            Leg.objects.create(
                transaction=transaction, account=self.ex_rent, credit=500
            )
            Leg.objects.create(transaction=transaction, account=self.ex_elec, credit=20)
            Leg.objects.create(
                transaction=transaction, account=self.ex_rates, credit=30
            )
            Leg.objects.create(transaction=transaction, account=self.ex_food, credit=70)

            line1.transaction = transaction
            line1.save()

        # Create transaction for housemate2's payment
        with db_transaction.atomic():
            transaction = Transaction.objects.create(date="2016-01-31")
            Leg.objects.create(
                transaction=transaction, account=self.inc_housemate_2, debit=620
            )
            Leg.objects.create(
                transaction=transaction, account=self.ex_rent, credit=500
            )
            Leg.objects.create(transaction=transaction, account=self.ex_elec, credit=20)
            Leg.objects.create(
                transaction=transaction, account=self.ex_rates, credit=30
            )
            Leg.objects.create(transaction=transaction, account=self.ex_food, credit=70)

            line2.transaction = transaction
            line2.save()

        # We should have a lot more money in the bank now
        self.assertBalanceEqual(
            self.bank.get_balance(), 1240 - 1000 - 70
        )  # money received - rent - food spending
        # The housemate income account should be empty as we've dispersed it to the relevant
        # expense accounts
        self.assertBalanceEqual(self.inc_housemate_1.get_balance(), 0)
        self.assertBalanceEqual(self.inc_housemate_2.get_balance(), 0)
        self.assertBalanceEqual(
            self.ex_rent.get_balance(), 0
        )  # Rent had already been paid out, some incoming money has cancelled it out
        # Each expense account is negative (i.e. we're waiting for expenses to come in)
        self.assertBalanceEqual(
            self.ex_elec.get_balance(), -120 / 3
        )  # 120 per 3 months
        self.assertBalanceEqual(
            self.ex_rates.get_balance(), -180 / 3
        )  # 180 per 3 months
        self.assertBalanceEqual(self.ex_food.get_balance(), -140 + 70)

        # Now we're half way through the month, so we need to order food a couple more times
        self.bank.transfer_to(self.ex_food, Money(35, "EUR"))
        self.bank.transfer_to(self.ex_food, Money(35, "EUR"))
        self.assertBalanceEqual(
            self.bank.get_balance(), 1240 - 1000 - 70 - 70
        )  # money received - rent - two batches of food spending
        self.assertBalanceEqual(
            self.ex_food.get_balance(), 0
        )  # Now we've spent all our food money for the month

        # Ok, it's the end of the month now, so time to do a little admin...

        # Firstly, we pay rates & electricity every 3 months, so dump
        # the contents of those expense accounts into the relevant
        # 'Payable' accounts (as we'll need it to pay the bills when they
        # eventually arrive)
        self.lia_elec_payable.transfer_to(self.ex_elec, Money(120 / 3, "EUR"))
        self.lia_rates_payable.transfer_to(self.ex_rates, Money(180 / 3, "EUR"))

        # The expense accounts should now be zeroed...
        self.assertBalanceEqual(self.ex_elec.get_balance(), 0)
        self.assertBalanceEqual(self.ex_rates.get_balance(), 0)

        # ...and the payable accounts now have a positive balance
        # (and we'll pay the bills out of these accounts when they
        # eventually come in)
        self.assertBalanceEqual(self.lia_elec_payable.get_balance(), 120 / 3)
        self.assertBalanceEqual(self.lia_rates_payable.get_balance(), 180 / 3)
        # And we have that money sat in the bank account
        self.assertBalanceEqual(self.bank.get_balance(), 120 / 3 + 180 / 3)

        # See! Accounting is fun!

    # def test_three_months(self):
    #     self.test_one_month()
    #     self.test_one_month()
    #     self.test_one_month()
    #
