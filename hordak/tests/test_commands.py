from django.test.testcases import TestCase
from django.core.management import call_command

from hordak.models import Account


class CreateChartOfAccountsTestCase(TestCase):

    def test_simple(self):
        call_command('create_chart_of_accounts', *['--currency', 'USD'])
        self.assertGreater(Account.objects.count(), 10)
        account = Account.objects.all()[0]
        self.assertEqual(account.currencies, ['USD'])

    def test_multi_currency(self):
        call_command('create_chart_of_accounts', *['--currency', 'USD', 'EUR'])
        self.assertGreater(Account.objects.count(), 10)
        account = Account.objects.all()[0]
        self.assertEqual(account.currencies, ['USD', 'EUR'])
