from django.db import models
from django.utils import timezone
from django.db import transaction as db_transaction
from django.utils.timezone import make_aware
from django_smalluuid.models import SmallUUIDField, uuid_default

from mptt.models import MPTTModel, TreeForeignKey, TreeManager
from model_utils import Choices

from hordak import exceptions

DEBIT = 'debit'
CREDIT = 'credit'


class AccountQuerySet(models.QuerySet):

    def net_balance(self, raw=False):
        return sum(account.balance(raw) for account in self)


class AccountManager(TreeManager):

    def get_by_natural_key(self, uuid):
        return self.get(uuid=uuid)


class Account(MPTTModel):
    TYPES = Choices(
        ('AS', 'asset', 'Asset'),  # Cash in bank
        ('LI', 'liability', 'Liability'),
        ('IN', 'income', 'Income'),  # Incoming rent, contributions
        ('EX', 'expense', 'Expense'),  # Shopping, outgoing rent
        ('EQ', 'equity', 'Equity'),
    )

    uuid = SmallUUIDField(default=uuid_default(), editable=False)
    name = models.CharField(max_length=50)
    parent = TreeForeignKey('self', null=True, blank=True, related_name='children', db_index=True)
    # TODO: Denormalise account code (in order to allow lookup by it)
    code = models.CharField(max_length=3)
    # TODO: Implement this child_code_width field, as it is probably a good idea
    # child_code_width = models.PositiveSmallIntegerField(default=1)
    _type = models.CharField(max_length=2, choices=TYPES, blank=True)
    has_statements = models.BooleanField(default=False, blank=True,
                                         help_text='Does this account have statements to reconcile against. '
                                                   'This is typically the case for bank accounts.')

    objects = AccountManager.from_queryset(AccountQuerySet)()

    class MPTTMeta:
        order_insertion_by = ['code']

    class Meta:
        unique_together = (('parent', 'code'),)

    @classmethod
    def validate_accounting_equation(cls):
        """Check that all accounts sum to 0"""
        balances = [account.balance(raw=True) for account in Account.objects.root_nodes()]
        if sum(balances) != 0:
            raise exceptions.AccountingEquationViolationError(
                'Account balances do not sum to zero. They sum to {}'.format(sum(balances))
            )

    def __str__(self):
        name = self.name or 'Unnamed Account'
        if self.is_leaf_node():
            return '{} [{}]'.format(name, self.full_code or '-')
        else:
            return name

    def natural_key(self):
        return (self.uuid,)

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

        Further details here: https://en.wikipedia.org/wiki/Debits_and_credits

        """
        return -1 if self.type in (Account.TYPES.asset, Account.TYPES.expense) else 1

    def balance(self, as_of=None, raw=False):
        """Get the balance for this account, including child accounts

        See simple_balance() for argument reference.

        Returns:
            Decimal:
        """
        balances = [
            account.simple_balance(as_of=as_of, raw=raw)
            for account
            in self.get_descendants(include_self=True)
        ]
        return sum(balances)

    def simple_balance(self, as_of=None, raw=False):
        """Get the balance for this account, ignoring all child accounts

        Args:
            raw (bool): If true the returned balance will not have its sign
                        adjusted for display purposes.

        Returns
            Decimal:
        """
        legs = self.legs
        if as_of:
            legs = legs.filter(transaction__date__lte=as_of)
        return legs.sum_amount() * (1 if raw else self.sign)

    @db_transaction.atomic()
    def transfer_to(self, to_account, amount, **transaction_kwargs):
        """Create a transaction which transfers amount to to_account"""
        if to_account.sign == 1:
            # Transferring from two positive-signed accounts implies that
            # the caller wants to reduce the first account and increase the second
            # (which is opposite to the implicit behaviour)
            # Question: Is this actually a good idea?
            direction = -1
        else:
            direction = 1

        transaction = Transaction.objects.create(**transaction_kwargs)
        Leg.objects.create(transaction=transaction, account=self, amount=+amount * direction)
        Leg.objects.create(transaction=transaction, account=to_account, amount=-amount * direction)
        return transaction


class TransactionManager(models.Manager):

    def get_by_natural_key(self, uuid):
        return self.get(uuid=uuid)


class Transaction(models.Model):
    uuid = SmallUUIDField(default=uuid_default(), editable=False)
    timestamp = models.DateTimeField(default=timezone.now, help_text='The creation date of this transaction object')
    date = models.DateField(default=timezone.now, help_text='The date on which this transaction occurred')
    description = models.TextField(default='', blank=True)

    objects = TransactionManager()

    def balance(self):
        return self.legs.sum_amount()

    def natural_key(self):
        return (self.uuid,)


class LegQuerySet(models.QuerySet):

    def sum_amount(self):
        return self.aggregate(models.Sum('amount'))['amount__sum'] or 0

    def debits(self):
        return self.filter(amount__gt=0)

    def credits(self):
        return self.filter(amount__lt=0)


class LegManager(models.Manager):

    def get_by_natural_key(self, uuid):
        return self.get(uuid=uuid)


class Leg(models.Model):
    uuid = SmallUUIDField(default=uuid_default(), editable=False)
    transaction = models.ForeignKey(Transaction, related_name='legs', on_delete=models.CASCADE)
    account = models.ForeignKey(Account, related_name='legs')
    amount = models.DecimalField(max_digits=13, decimal_places=2,
                                 help_text='Record debits as positive, credits as negative')
    description = models.TextField(default='', blank=True)

    objects = LegManager.from_queryset(LegQuerySet)()

    def save(self, *args, **kwargs):
        if self.amount == 0:
            raise exceptions.ZeroAmountError()
        return super(Leg, self).save(*args, **kwargs)

    def natural_key(self):
        return (self.uuid,)

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


class StatementImportManager(models.Manager):

    def get_by_natural_key(self, uuid):
        return self.get(uuid=uuid)


class StatementImport(models.Model):
    uuid = SmallUUIDField(default=uuid_default(), editable=False)
    timestamp = models.DateTimeField(default=timezone.now)
    # TODO: Add constraint to ensure destination account expects statements
    bank_account = models.ForeignKey(Account, related_name='imports')

    objects = StatementImportManager()

    def natural_key(self):
        return (self.uuid,)


class StatementLineManager(models.Manager):

    def get_by_natural_key(self, uuid):
        return self.get(uuid=uuid)


class StatementLine(models.Model):
    uuid = SmallUUIDField(default=uuid_default(), editable=False)
    timestamp = models.DateTimeField(default=timezone.now)
    date = models.DateField()
    statement_import = models.ForeignKey(StatementImport, related_name='lines')
    amount = models.DecimalField(max_digits=13, decimal_places=2)
    description = models.TextField(default='', blank=True)
    # TODO: Add constraint to ensure transaction amount = statement line amount
    # TODO: Add constraint to ensure one statement line per transaction
    transaction = models.ForeignKey(Transaction, default=None, blank=True, null=True,
                                    help_text='Reconcile this statement line to this transaction')

    objects = StatementLineManager()

    def natural_key(self):
        return (self.uuid,)

    @property
    def is_reconciled(self):
        return bool(self.transaction)

    @db_transaction.atomic()
    def create_transaction(self, to_account):
        """Create a transaction for this statement amount and acount, into to_account

        This will also set this StatementLine's ``transaction`` attribute to the newly
        created transaction.

        Args:
            to_account (Account): The account the transaction is into / out of

        Returns:
            Transaction: The newly created (and committed) transaction

        """
        from_account = self.statement_import.bank_account

        transaction = Transaction.objects.create()
        Leg.objects.create(transaction=transaction, account=from_account, amount=+(self.amount * -1))
        Leg.objects.create(transaction=transaction, account=to_account, amount=-(self.amount * -1))

        transaction.date = self.date
        transaction.save()

        self.transaction = transaction
        self.save()
        return transaction
