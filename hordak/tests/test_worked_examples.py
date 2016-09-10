from django.test import TestCase
from django.db import transaction as db_transaction

from hordak.models import Account, Transaction, Leg


class InitialEquityTestCase(TestCase):

    def setUp(self):
        self.cash = Account.objects.create(name='Cash', type=Account.TYPES.asset, code='1')
        self.equity = Account.objects.create(name='Equity', type=Account.TYPES.equity, code='2')

    def test_initial_equity(self):
        self.equity.transfer_to(self.cash, 100000)
        self.assertEqual(self.cash.balance(), 100000)
        self.assertEqual(self.equity.balance(), 100000)


class CapitalGainsTestCase(TestCase):

    def setUp(self):
        self.cash = Account.objects.create(name='Cash', type=Account.TYPES.asset, code='1')
        self.equity = Account.objects.create(name='Equity', type=Account.TYPES.equity, code='2')
        self.painting_cost = Account.objects.create(name='Painting - cost', type=Account.TYPES.asset, code='3')
        self.painting_unrealised_gain = Account.objects.create(name='Painting - unrealised gain', type=Account.TYPES.asset, code='4')
        self.income_realised_gain = Account.objects.create(name='Painting - unrealised gain', type=Account.TYPES.income, code='5')
        self.income_unrealised_gain = Account.objects.create(name='Painting - unrealised gain', type=Account.TYPES.income, code='6')

    def test_capital_gains(self):
        # Initial investment
        self.equity.transfer_to(self.cash, 100000)

        # Buy the painting
        self.cash.transfer_to(self.painting_cost, 100000)

        self.assertEqual(self.cash.balance(), 0)
        self.assertEqual(self.painting_cost.balance(), 100000)

        # Painting goes up in value by 10k
        self.income_unrealised_gain.transfer_to(self.painting_unrealised_gain, 10000)

        self.assertEqual(self.painting_unrealised_gain.balance(), 10000)
        self.assertEqual(self.income_unrealised_gain.balance(), 10000)

        # Painting goes up in value by 20k
        self.income_unrealised_gain.transfer_to(self.painting_unrealised_gain, 20000)

        self.assertEqual(self.painting_unrealised_gain.balance(), 30000)
        self.assertEqual(self.income_unrealised_gain.balance(), 30000)

        # We sell the painting (having accurately estimated the gains in value)
        self.income_unrealised_gain.transfer_to(self.income_realised_gain, 30000)
        self.painting_cost.transfer_to(self.cash, 100000)
        self.painting_unrealised_gain.transfer_to(self.cash, 30000)

        self.assertEqual(self.cash.balance(), 130000)
        self.assertEqual(self.painting_cost.balance(), 0)
        self.assertEqual(self.painting_unrealised_gain.balance(), 0)
        self.assertEqual(self.income_realised_gain.balance(), 30000)
        self.assertEqual(self.income_unrealised_gain.balance(), 0)



class PrepaidRentTestCase(TestCase):
    """Prepay three months rent in advance

    Based on example here:
    http://www.double-entry-bookkeeping.com/other-current-assets/prepaid-rent/
    """

    def setUp(self):
        self.cash = Account.objects.create(name='Cash', type=Account.TYPES.asset, code='1')
        self.rent_expense = Account.objects.create(name='Rent Expense', type=Account.TYPES.expense, code='2')
        self.prepaid_rent = Account.objects.create(name='Prepaid Rent', type=Account.TYPES.asset, code='2')

    def test_prepaid_rent(self):
        # All accounts start at 0
        self.assertEqual(self.cash.balance(), 0)
        self.assertEqual(self.rent_expense.balance(), 0)
        self.assertEqual(self.prepaid_rent.balance(), 0)

        # Pay the rent to the landlord
        self.cash.transfer_to(self.prepaid_rent, 3000)
        self.assertEqual(self.cash.balance(), -3000)
        self.assertEqual(self.rent_expense.balance(), 0)
        self.assertEqual(self.prepaid_rent.balance(), 3000)

        # Now the end of the month, so turn 1k of rent into an expense
        self.prepaid_rent.transfer_to(self.rent_expense, 1000)
        self.assertEqual(self.cash.balance(), -3000)
        self.assertEqual(self.rent_expense.balance(), 1000)
        self.assertEqual(self.prepaid_rent.balance(), 2000)

        # Now two more months
        self.prepaid_rent.transfer_to(self.rent_expense, 1000)
        self.assertEqual(self.cash.balance(), -3000)
        self.assertEqual(self.rent_expense.balance(), 2000)
        self.assertEqual(self.prepaid_rent.balance(), 1000)

        self.prepaid_rent.transfer_to(self.rent_expense, 1000)
        self.assertEqual(self.cash.balance(), -3000)
        self.assertEqual(self.rent_expense.balance(), 3000)
        self.assertEqual(self.prepaid_rent.balance(), 0)

        Account.validate_accounting_equation()


class UtilityBillTestCase(TestCase):
    """Pay an estimateable sum every 3 months"""

    def setUp(self):
        self.cash = Account.objects.create(name='Cash', type=Account.TYPES.asset, code='1')
        self.gas_expense = Account.objects.create(name='Gas Expense', type=Account.TYPES.expense, code='2')
        self.gas_payable = Account.objects.create(name='Gas Payable', type=Account.TYPES.liability, code='3')

    def test_utility_bill(self):
        # Month 1
        self.gas_expense.transfer_to(self.gas_payable, 100)

        self.assertEqual(self.cash.balance(), 0)
        self.assertEqual(self.gas_expense.balance(), -100)
        self.assertEqual(self.gas_payable.balance(), -100)

        # Month 2
        self.gas_expense.transfer_to(self.gas_payable, 100)

        self.assertEqual(self.cash.balance(), 0)
        self.assertEqual(self.gas_expense.balance(), -200)
        self.assertEqual(self.gas_payable.balance(), -200)

        # Month 3
        self.gas_expense.transfer_to(self.gas_payable, 100)

        self.assertEqual(self.cash.balance(), 0)
        self.assertEqual(self.gas_expense.balance(), -300)
        self.assertEqual(self.gas_payable.balance(), -300)

        # We receive the actual bill
        self.gas_payable.transfer_to(self.cash, 300)

        self.assertEqual(self.cash.balance(), 300)
        self.assertEqual(self.gas_expense.balance(), -300)
        self.assertEqual(self.gas_payable.balance(), 0)

        Account.validate_accounting_equation()
