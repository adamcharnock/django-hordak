from django.contrib.auth import get_user_model
from django.contrib.auth.models import User

from hordak.models import Account, StatementImport
from hordak.utilities.currency import Balance


class DataProvider(object):
    """Utility methods for providing data to test cases"""

    def user(self, *, username=None, email=None, password=None, is_superuser=True, is_distributor=False, **kwargs):
        username = username or 'user{}'.format(get_user_model().objects.count() + 1)
        email = email or '{}@example.com'.format(username)

        user = User.objects.create(
            email=email,
            username=username,
            is_superuser=is_superuser,
            **kwargs
        )

        if password:
            user.set_password(password)
            user.save()

        return user

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
            source='csv',
            **kwargs
        )

    def login(self):
        user = get_user_model().objects.create(username='user')
        user.set_password('password')
        user.save()
        self.client.login(username='user', password='password')
        return user


class BalanceUtils(object):

    def assertBalanceEqual(self, balance, value):
        assert not isinstance(value, Balance), 'The second argument to assertBalanceEqual() should be a regular ' \
                                               'integer/Decimal type, not a Balance object. If you wish to compare ' \
                                               'two Balance objects then use assertEqual()'

        monies = balance.monies()
        assert len(monies) in (0, 1), 'Can only compare balances which contain a single currency'
        if not monies and value == 0:
            # Allow comparing balances without a currency to zero
            return

        assert len(monies) == 1, 'Can only compare balances which contain a single currency'
        balance_amount = balance.monies()[0].amount
        assert balance_amount == value, 'Balance {} != {}'.format(balance_amount, value)
