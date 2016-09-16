from django.test import TestCase
from django.db import transaction as db_transaction

from hordak.models import Account, Transaction, Leg, StatementImport, StatementLine


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
        self.assertEqual(self.gas_expense.balance(), 100)
        self.assertEqual(self.gas_payable.balance(), 100)

        # Month 2
        self.gas_expense.transfer_to(self.gas_payable, 100)

        self.assertEqual(self.cash.balance(), 0)
        self.assertEqual(self.gas_expense.balance(), 200)
        self.assertEqual(self.gas_payable.balance(), 200)

        # Month 3
        self.gas_expense.transfer_to(self.gas_payable, 100)

        self.assertEqual(self.cash.balance(), 0)
        self.assertEqual(self.gas_expense.balance(), 300)
        self.assertEqual(self.gas_payable.balance(), 300)

        # We receive the actual bill (we are moving a negative amount of money,
        # as this is an outgoing)
        self.cash.transfer_to(self.gas_payable, -300)

        # We are now 300 overdrawn, but the payable account has been cleared
        self.assertEqual(self.cash.balance(), -300)
        self.assertEqual(self.gas_expense.balance(), 300)
        self.assertEqual(self.gas_payable.balance(), 0)

        Account.validate_accounting_equation()


class CommunalHouseholdTestCase(TestCase):

    def setUp(self):
        T = Account.TYPES

        self.bank = Account.objects.create(name='Bank', type=T.asset, code='0')

        self.lia = Account.objects.create(name='Liabilities', type=T.liability, code='1')
        # self.lia_deposits = Account.objects.create('Deposits', type=Account.TYPES.liability, code='1')
        self.lia_elec_payable = Account.objects.create(name='Gas & Electricity Payable', parent=self.lia, code='2')
        self.lia_rates_payable = Account.objects.create(name='Council Tax Payable', parent=self.lia, code='3')

        self.inc = Account.objects.create(name='Income', type=T.income, code='2')
        self.inc_housemate = Account.objects.create(name='Housemate Income', parent=self.inc, code='1')
        self.inc_housemate_1 = Account.objects.create(name='Housemate 1 Income', parent=self.inc_housemate, code='1')
        self.inc_housemate_2 = Account.objects.create(name='Housemate 2 Income', parent=self.inc_housemate, code='2')
        self.inc_donation = Account.objects.create(name='Donation', parent=self.inc, code='2')

        self.ex = Account.objects.create(name='Expenses', type=T.expense, code='3')
        self.ex_rent = Account.objects.create(name='Rent', parent=self.ex, code='1')
        self.ex_elec = Account.objects.create(name='Gas & Electricity', parent=self.ex, code='2')
        self.ex_rates = Account.objects.create(name='Council Tax', parent=self.ex, code='3')
        self.ex_food = Account.objects.create(name='Food', parent=self.ex, code='4')

    def create_incoming_rent_payments(self, amount1, amount2):
        statement_import = StatementImport.objects.create(bank_account=self.bank)
        line1 = StatementLine.objects.create(date='2016-01-01', statement_import=statement_import, amount=amount1)
        line2 = StatementLine.objects.create(date='2016-01-01', statement_import=statement_import, amount=amount2)
        line1.refresh_from_db()
        line2.refresh_from_db()
        return (line1, line2)

    def test_one_month(self):
        """ Test payments over the course of three months

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
        self.bank.transfer_to(self.ex_food, 35)
        self.bank.transfer_to(self.ex_food, 35)
        # Now we have negative money in the bank, and food expenses recorded
        self.assertEqual(self.bank.balance(), -70)
        self.assertEqual(self.ex_food.balance(), 70)

        # Also, the landlord wants the rent in advance, so that gets paid
        self.bank.transfer_to(self.ex_rent, 1000)
        # Now we are even more overdrawn
        self.assertEqual(self.bank.balance(), -70 + -1000)
        self.assertEqual(self.ex_rent.balance(), 1000)

        # Create two statement lines and assign each to the housemate income account
        line1, line2 = self.create_incoming_rent_payments(620, 620)
        line1.create_transaction(self.inc_housemate_1)
        line2.create_transaction(self.inc_housemate_2)

        # Create transaction for housemate1's payment
        with db_transaction.atomic():
            transaction = Transaction.objects.create(date='2016-01-31')
            Leg.objects.create(transaction=transaction, account=self.inc_housemate_1, amount=-620)
            Leg.objects.create(transaction=transaction, account=self.ex_rent, amount=500)
            Leg.objects.create(transaction=transaction, account=self.ex_elec, amount=20)
            Leg.objects.create(transaction=transaction, account=self.ex_rates, amount=30)
            Leg.objects.create(transaction=transaction, account=self.ex_food, amount=70)

            line1.transaction = transaction
            line1.save()

        # Create transaction for housemate2's payment
        with db_transaction.atomic():
            transaction = Transaction.objects.create(date='2016-01-31')
            Leg.objects.create(transaction=transaction, account=self.inc_housemate_2, amount=-620)
            Leg.objects.create(transaction=transaction, account=self.ex_rent, amount=500)
            Leg.objects.create(transaction=transaction, account=self.ex_elec, amount=20)
            Leg.objects.create(transaction=transaction, account=self.ex_rates, amount=30)
            Leg.objects.create(transaction=transaction, account=self.ex_food, amount=70)

            line2.transaction = transaction
            line2.save()

        # We should have a lot more money in the bank now
        self.assertEqual(self.bank.balance(), 1240 - 1000 - 70)  # money received - rent - food spending
        # The housemate income account should be empty as we've dispersed it to the relevant
        # expense accounts
        self.assertEqual(self.inc_housemate_1.balance(), 0)
        self.assertEqual(self.inc_housemate_2.balance(), 0)
        self.assertEqual(self.ex_rent.balance(), 0)  # Rent had already been paid out, some incoming money has cancelled it out
        # Each expense account is negative (i.e. we're waiting for expenses to come in)
        self.assertEqual(self.ex_elec.balance(), -120 / 3)  # 120 per 3 months
        self.assertEqual(self.ex_rates.balance(), -180 / 3)  # 180 per 3 months
        self.assertEqual(self.ex_food.balance(), -140 + 70)

        # Now we're half way through the month, so we need to order food a couple more times
        self.bank.transfer_to(self.ex_food, 35)
        self.bank.transfer_to(self.ex_food, 35)
        self.assertEqual(self.bank.balance(), 1240 - 1000 - 70 - 70)  # money received - rent - two batches of food spending
        self.assertEqual(self.ex_food.balance(), 0)  # Now we've spent all our food money for the month

        # Ok, it's the end of the month now, so time to do a little admin...

        # Firstly, we pay rates & electricity every 3 months, so dump
        # the contents of those expense accounts into the relevant
        # 'Payable' accounts (as we'll need it to pay the bills when they
        # eventually arrive)
        self.ex_elec.transfer_to(self.lia_elec_payable, 120 / 3)
        self.ex_rates.transfer_to(self.lia_rates_payable, 180 / 3)

        # The expense accounts should now be zeroed...
        self.assertEqual(self.ex_elec.balance(), 0)
        self.assertEqual(self.ex_rates.balance(), 0)

        # ...and the payable accounts now have a positive balance
        # (and we'll pay the bills out of these accounts when they
        # eventually come in)
        self.assertEqual(self.lia_elec_payable.balance(), 120 / 3)
        self.assertEqual(self.lia_rates_payable.balance(), 180 / 3)
        # And we have that money sat in the bank account
        self.assertEqual(self.bank.balance(), 120 / 3 + 180 / 3)

        # See! Accounting is fun!



    # def test_three_months(self):
    #     self.test_one_month()
    #     self.test_one_month()
    #     self.test_one_month()
    #





