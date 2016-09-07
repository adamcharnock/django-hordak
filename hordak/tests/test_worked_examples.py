from django.test import TestCase
from django.db import transaction as db_transaction

from hordak.models import Account, Transaction, Leg

class PrepaidRentTestCase(TestCase):
    """Prepay three months rent in advance

    Based on example here:
    http://www.double-entry-bookkeeping.com/other-current-assets/prepaid-rent/
    """

    def setUp(self):
        self.cash = Account.objects.create(name='Cash', type=Account.TYPES.asset, code='1')
        self.rent_expense = Account.objects.create(name='Rent Expense', type=Account.TYPES.expense, code='2')
        self.prepaid_rent = Account.objects.create(name='Prepaid Rent', type=Account.TYPES.asset, code='2')

    @db_transaction.atomic()
    def pay_rent(self):
        transaction = Transaction.objects.create()
        debit = Leg.objects.create(transaction=transaction, account=self.cash, amount=-3000)
        credit = Leg.objects.create(transaction=transaction, account=self.prepaid_rent, amount=3000)

    @db_transaction.atomic()
    def month_end(self):
        transaction = Transaction.objects.create()
        debit = Leg.objects.create(transaction=transaction, account=self.prepaid_rent, amount=-1000)
        credit = Leg.objects.create(transaction=transaction, account=self.rent_expense, amount=1000)

    def test_prepaid_rent(self):
        # All accounts start at 0
        self.assertEqual(self.cash.balance(), 0)
        self.assertEqual(self.rent_expense.balance(), 0)
        self.assertEqual(self.prepaid_rent.balance(), 0)

        # Pay the rent to the landlord
        self.pay_rent()
        self.assertEqual(self.cash.balance(), 3000)
        self.assertEqual(self.rent_expense.balance(), 0)
        self.assertEqual(self.prepaid_rent.balance(), -3000)

        # Now the end of the month, so turn 1k of rent into an expense
        self.month_end()
        self.assertEqual(self.cash.balance(), 3000)
        self.assertEqual(self.rent_expense.balance(), -1000)
        self.assertEqual(self.prepaid_rent.balance(), -2000)

        # Now two more months
        self.month_end()
        self.assertEqual(self.cash.balance(), 3000)
        self.assertEqual(self.rent_expense.balance(), -2000)
        self.assertEqual(self.prepaid_rent.balance(), -1000)

        self.month_end()
        self.assertEqual(self.cash.balance(), 3000)
        self.assertEqual(self.rent_expense.balance(), -3000)
        self.assertEqual(self.prepaid_rent.balance(), 0)
