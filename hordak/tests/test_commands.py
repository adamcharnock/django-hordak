from django.test.testcases import TestCase
from django.core.management import call_command

from hordak.models import Account

class CreateChartOfAccountsTestCase(TestCase):

    def test_simple(self):
        call_command('create_chart_of_accounts')
        self.assertGreater(Account.objects.count(), 10)
