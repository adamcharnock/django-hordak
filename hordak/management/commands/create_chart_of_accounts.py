from django.core.management.base import BaseCommand, CommandError

from hordak.models import Account


class Command(BaseCommand):
    help = 'Create an initial chart of accounts'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            dest='force',
            default=False,
            help='Force creation even if accounts already exist',
        )

        parser.add_argument(
            '--deleteall',
            action='store_true',
            dest='deleteall',
            default=False,
            help='Delete all existing accounts',
        )

        parser.add_argument(
            '--currency',
            nargs='+',
            dest='currency',
            help='The currency of the accounts to create. Can specify multiple times for multiple currency support.',
            required=True,
        )

    def handle(self, *args, **options):
        force = options.get('force')
        delete_all = options.get('deleteall')

        if delete_all:
            Account.objects.delete()

        accounts_exist = Account.objects.count()

        if accounts_exist:
            if force:
                self.stdout.write(self.style.WARNING(
                    'Accounts exist, continuing regardless due to --force'
                ))
            else:
                raise CommandError(
                    'Accounts already exist. Use --force if you are sure you want to do this'
                )

        if isinstance(options['currency'], (list, tuple)):
            currencies = options['currency']
        else:
            currencies = [options['currency']]

        kw = dict(currencies=currencies)
        # Root accounts (level 0)
        T = Account.TYPES
        assets = Account.objects.create(name='Assets', code='1', type=T.asset, **kw)
        liabilities = Account.objects.create(name='Liabilities', code='2', type=T.liability, **kw)
        equity = Account.objects.create(name='Equity', code='3', type=T.equity, **kw)
        income = Account.objects.create(name='Income', code='4', type=T.income, **kw)
        expenses = Account.objects.create(name='Expenses', code='5', type=T.expense, **kw)

        # Asset accounts (level 1)
        assets_current = Account.objects.create(parent=assets, name='Current', code='0', **kw)
        assets_fixed = Account.objects.create(parent=assets, name='Fixed', code='1', **kw)

        # Asset accounts (level 2)
        assets_current_cash = Account.objects.create(parent=assets_current, name='Cash', code='0', **kw)
        assets_current_receivables= Account.objects.create(parent=assets_current, name='Accounts Receivable', code='1', **kw)

        Account.objects.create(parent=assets_fixed, name='Land', code='0', **kw)
        Account.objects.create(parent=assets_fixed, name='Equipment', code='1', **kw)

        # Asset accounts (level 3)
        Account.objects.create(parent=assets_current_cash, name='Bank', code='0', **kw)
        Account.objects.create(parent=assets_current_cash, name='Petty Cash', code='9', **kw)

        # Liabilities (level 1)
        liability_current = Account.objects.create(parent=liabilities, name='Current', code='0', **kw)
        liability_non_current = Account.objects.create(parent=liabilities, name='Non-Current', code='1', **kw)

        # Liabilities (level 2)
        Account.objects.create(parent=liability_current, name='Accounts Payable', code='0', **kw)
        Account.objects.create(parent=liability_current, name='Accruals', code='1', **kw)
        Account.objects.create(parent=liability_current, name='Income in Advance', code='2', **kw)

        Account.objects.create(parent=liability_non_current, name='Loan', code='0', **kw)

        # Equity (level 1)
        Account.objects.create(parent=equity, name='Capital - Ordinary Shares', code='0', **kw)
        Account.objects.create(parent=equity, name='Retained Earnings', code='1', **kw)
        Account.objects.create(parent=equity, name='Order Funds Introduced', code='2', **kw)
        Account.objects.create(parent=equity, name='Order Drawings', code='3', **kw)

        # Income (level 1)
        Account.objects.create(parent=income, name='Sales', code='01', **kw)
        Account.objects.create(parent=income, name='Interest Income', code='05', **kw)
        Account.objects.create(parent=income, name='Other Charges', code='10', **kw)

        # Expenses (level 1)
        expense_direct = Account.objects.create(parent=expenses, name='Direct', code='0', **kw)
        expense_overhead = Account.objects.create(parent=expenses, name='Overhead', code='1', **kw)

        # Expenses (level 2)
        Account.objects.create(parent=expense_direct, name='Direct Wages', code='0', **kw)
        Account.objects.create(parent=expense_direct, name='Direct Expenses', code='1', **kw)

        Account.objects.create(parent=expense_overhead, name='Accountancy & Audit Fees', code='01', **kw)
        Account.objects.create(parent=expense_overhead, name='Bank Fees', code='05', **kw)
        Account.objects.create(parent=expense_overhead, name='Cleaning', code='10', **kw)
        Account.objects.create(parent=expense_overhead, name='Consulting', code='15', **kw)
        Account.objects.create(parent=expense_overhead, name='Depreciation', code='20', **kw)
        Account.objects.create(parent=expense_overhead, name='IT Services', code='25', **kw)
        Account.objects.create(parent=expense_overhead, name='IT Software & Consumables', code='30', **kw)
        Account.objects.create(parent=expense_overhead, name='Repairs & Maintenance', code='35', **kw)
        Account.objects.create(parent=expense_overhead, name='Travel', code='40', **kw)
        Account.objects.create(parent=expense_overhead, name='Corporation Tax', code='45', **kw)
        Account.objects.create(parent=expense_overhead, name='Rates', code='50', **kw)

