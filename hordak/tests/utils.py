from hordak.models import Account, StatementImport


class DataProvider(object):
    """Utility methods for providing data to test cases"""

    def account(self, name=None, parent=None, type=Account.TYPES.income, code=None, currencies=('EUR',), **kwargs):
        """ Utility for creating accounts for use in test cases

        Returns:
            Account
        """
        name = name or 'Account {}'.format(Account.objects.count() + 1)
        code = code if code is not None else Account.objects.filter(parent=parent).count()

        return Account.objects.create(
            name=name,
            parent=parent,
            type=None if parent else type,
            code=code,
            currencies=currencies,
            **kwargs
        )

    def statement_import(self, bank_account=None, **kwargs):
        return StatementImport.objects.create(
            bank_account=bank_account or self.account(type=Account.TYPES.asset),
            **kwargs
        )



class BalanceUtils(object):

    def assertBalanceEqual(self, balance, value):
        monies = balance.monies()
        assert len(monies) in (0, 1), 'Can only compare balances which contain a single currency'
        if not monies and value == 0:
            # Allow comparing balances without a currency to zero
            return

        assert len(monies) == 1, 'Can only compare balances which contain a single currency'
        balance_amount = balance.monies()[0].amount
        assert balance_amount == value, 'Balance {} != value'.format(balance_amount, value)
