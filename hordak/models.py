from django.db import models
from django.utils import timezone

from mptt.models import MPTTModel, TreeForeignKey
from model_utils import Choices

from hordak import exceptions

DEBIT = 'debit'
CREDIT = 'credit'


class Account(MPTTModel):
    TYPES = Choices(
        ('AS', 'asset', 'Asset'),  # Cash in bank
        ('LI', 'liability', 'Liability'),
        ('IN', 'income', 'Income'),  # Incoming rent, contributions
        ('EX', 'expense', 'Expense'),  # Shopping, outgoing rent
        ('EQ', 'equity', 'Equity'),
    )

    name = models.CharField(max_length=50)
    parent = TreeForeignKey('self', null=True, blank=True, related_name='children', db_index=True)
    code = models.CharField(max_length=3)
    _type = models.CharField(max_length=2, choices=TYPES)

    class MPTTMeta:
        order_insertion_by = ['code']

    class Meta:
        unique_together = (('parent', 'code'),)

    @classmethod
    def validate_accounting_equation(cls):
        """Check that all accounts sum to 0"""
        balances = [account.balance() for account in Account.objects.root_nodes()]
        if sum(balances) != 0:
            raise exceptions.AccountingEquationViolationError()

    def __str__(self):
        name = self.name or 'Unnamed Account'
        if self.is_leaf_node():
            return '{} [{}]'.format(name, self.full_code or '-')
        else:
            return name

    @property
    def full_code(self):
        """Get the full code for this account

        Do this by concatenating this account's code with that
        of all the parent accounts.
        """
        if not self.pk:
            # Has not been saved to the DB so we cannot get ancestors
            return None
        else:
            return ''.join(account.code for account in self.get_ancestors(include_self=True))

    @property
    def type(self):
        if self.is_root_node():
            return self._type
        else:
            return self.get_root()._type

    @type.setter
    def type(self, value):
        """
        Only root nodes can have an account type. This seems like a
        sane limitation until proven otherwise.
        """
        if self.is_root_node():
            self._type = value
        else:
            raise exceptions.AccountTypeOnChildNode()

    @property
    def sign(self):
        """
        Returns 1 if a credit should increase the value of the
        account, or -1 if a credit should decrease the value of the
        account.

        This is based on the account type as is standard accounting practice.
        The signs can be derrived from the following expanded form of the
        accounting equation:

            Assets = Liabilities + Equity + (Income - Expenses)

        Which can be rearranged as:

            0 = Liabilities + Equity + Income - Expenses - Assets

        """
        return -1 if self.type in (Account.TYPES.asset, Account.TYPES.expense) else 1

    def balance(self):
        """Get the balance for this account, including child accounts"""
        balances = [account.simple_balance() for account in self.get_descendants(include_self=True)]
        return sum(balances)

    def simple_balance(self):
        """Get the balance for this account, ignoring all child accounts"""
        return self.legs.sum_amount() * self.sign


class Transaction(models.Model):
    timestamp = models.DateTimeField(default=timezone.now)
    description = models.TextField(default='', blank=True)

    def balance(self):
        return self.legs.sum_amount()


class LegQuerySet(models.QuerySet):

    def sum_amount(self):
        return self.aggregate(models.Sum('amount'))['amount__sum'] or 0


LegManager = LegQuerySet.as_manager()


class Leg(models.Model):
    transaction = models.ForeignKey(Transaction, related_name='legs')
    account = models.ForeignKey(Account, related_name='legs')
    amount = models.DecimalField(max_digits=13, decimal_places=2,
                                 help_text='Record debits as positive, credits as negative')
    description = models.TextField(default='', blank=True)

    objects = LegManager

    def save(self, *args, **kwargs):
        if self.amount == 0:
            raise exceptions.ZeroAmountError()
        return super(Leg, self).save(*args, **kwargs)

    @property
    def type(self):
        if self.amount < 0:
            return DEBIT
        elif self.amount > 0:
            return CREDIT
        else:
            # This should have been caught earlier by the database integrity check.
            # If you are seeing this then something is wrong with your DB checks.
            raise exceptions.ZeroAmountError()

    def is_debit(self):
        return self.type == DEBIT

    def is_credit(self):
        return self.type == CREDIT

