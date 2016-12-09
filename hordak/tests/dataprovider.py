from hordak.models import Account


class DataProvider(object):
    """Utility methods for providing data to test cases"""

    def account(self, name=None, parent=None, type=Account.TYPES.income, code=None, currencies=('EUR',), **kwargs):
        name = name or 'Account {}'.format(Account.objects.count() + 1)
        code = code if code is not None else Account.objects.filter(parent=parent).count()

        return Account.objects.create(
            name=name,
            parent=parent,
            type=type,
            code=code,
            currencies=currencies,
            **kwargs
        )

