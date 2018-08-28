"""
Design Overview
---------------

The core models consist of:

- ``Account`` - Such as 'Accounts Receivable', a bank account, etc. Accounts can be arranged as a tree structure,
  where the balance of the parent account is the summation of the balances of all its children.
- ``Transaction`` - Represents a movement between accounts. Each transaction must have two or more legs.
- ``Leg`` - Represents a flow of money into (debit) or out of (credit) a transaction. Debits are represented by
  negative amounts, and credits by positive amounts. The sum of all a transaction's legs must equal zero. This is
  enforced with a database constraint.

Additionally, there are models which related to the import of external bank statement data:

- ``StatementImport`` - Represents a simple import of zero or more statement lines relating to a specific ``Account``.
- ``StatementLine`` - Represents a statement line. ``StatementLine.create_transaction()`` may be called to
  create a transaction for the statement line.
"""

from django.contrib.postgres.fields.array import ArrayField
from django.contrib.postgres.fields.jsonb import JSONField
from django.db import models
from django.utils import timezone
from django.db import transaction as db_transaction
from django_smalluuid.models import SmallUUIDField, uuid_default
from djmoney.models.fields import MoneyField
from moneyed import Money

from mptt.models import MPTTModel, TreeForeignKey, TreeManager
from model_utils import Choices

from hordak import defaults
from hordak import exceptions

from hordak.utilities.currency import Balance


#: Debit
DEBIT = 'debit'
#: Credit
CREDIT = 'credit'


def json_default():
    return {}


class AccountQuerySet(models.QuerySet):

    def net_balance(self, raw=False):
        return sum((account.balance(raw) for account in self), Balance())


class AccountManager(TreeManager):

    def get_by_natural_key(self, uuid):
        return self.get(uuid=uuid)


class Account(MPTTModel):
    """ Represents an account

    An account may have a parent, and may have zero or more children. Only root
    accounts can have a type, all child accounts are assumed to have the same
    type as their parent.

    An account's balance is calculated as the sum of all of the transaction Leg's
    referencing the account.

    Attributes:

        uuid (SmallUUID): UUID for account. Use to prevent leaking of IDs (if desired).
        name (str): Name of the account. Required.
        parent (Account|None): Parent account, nonen if root account
        code (str): Account code. Must combine with account codes of parent
            accounts to get fully qualified account code.
        type (str): Type of account as defined by :attr:`Account.TYPES`. Can only be set on
            root accounts. Child accounts are assumed to have the same time as their parent.
        TYPES (Choices): Available account types. Uses ``Choices`` from ``django-model-utils``. Types can be
            accessed in the form ``Account.TYPES.asset``, ``Account.TYPES.expense``, etc.
        is_bank_account (bool): Is this a bank account. This implies we can import bank statements into
            it and that it only supports a single currency.


    """
    TYPES = Choices(
        ('AS', 'asset', 'Asset'),              # Eg. Cash in bank
        ('LI', 'liability', 'Liability'),      # Eg. Loans, bills paid after the fact (in arrears)
        ('IN', 'income', 'Income'),            # Eg. Sales, housemate contributions
        ('EX', 'expense', 'Expense'),          # Eg. Office supplies, paying bills
        ('EQ', 'equity', 'Equity'),            # Eg. Money from shares
        ('TR', 'trading', 'Currency Trading')  # Used to represent currency conversions
    )
    uuid = SmallUUIDField(default=uuid_default(), editable=False)
    name = models.CharField(max_length=50)
    parent = TreeForeignKey('self', null=True, blank=True, related_name='children', db_index=True, on_delete=models.CASCADE)
    code = models.CharField(max_length=3, null=True, blank=True)
    full_code = models.CharField(max_length=100, db_index=True, unique=True, null=True, blank=True)
    # TODO: Implement this child_code_width field, as it is probably a good idea
    # child_code_width = models.PositiveSmallIntegerField(default=1)
    type = models.CharField(max_length=2, choices=TYPES, blank=True)
    is_bank_account = models.BooleanField(default=False, blank=True,
                                          help_text='Is this a bank account. This implies we can import bank '
                                                    'statements into it and that it only supports a single currency')
    currencies = ArrayField(models.CharField(max_length=3), db_index=True)

    objects = AccountManager.from_queryset(AccountQuerySet)()

    class MPTTMeta:
        order_insertion_by = ['code']

    class Meta:
        unique_together = (('parent', 'code'),)

    def __init__(self, *args, **kwargs):
        super(Account, self).__init__(*args, **kwargs)
        self._initial_code = self.code

    def save(self, *args, **kwargs):
        is_creating = not bool(self.pk)
        super(Account, self).save(*args, **kwargs)
        do_refresh = False

        # If we've just created a non-root node then we're going to need to load
        # the type back from the DB (as it is set by trigger)
        if is_creating and not self.is_root_node():
            do_refresh = True

        # If we've just create this account or if the code has changed then we're
        # going to need to reload from the DB (full_code is set by trigger)
        if is_creating or self._initial_code != self.code:
            do_refresh = True

        if do_refresh:
            self.refresh_from_db()

    @classmethod
    def validate_accounting_equation(cls):
        """Check that all accounts sum to 0"""
        balances = [account.balance(raw=True) for account in Account.objects.root_nodes()]
        if sum(balances, Balance()) != 0:
            raise exceptions.AccountingEquationViolationError(
                'Account balances do not sum to zero. They sum to {}'.format(sum(balances))
            )

    def __str__(self):
        name = self.name or 'Unnamed Account'
        if self.is_leaf_node():
            try:
                balance = self.balance()
            except ValueError:
                if self.full_code:
                    return '{} {}'.format(self.full_code, name)
                else:
                    return name
            else:
                if self.full_code:
                    return '{} {} [{}]'.format(self.full_code, name, balance)
                else:
                    return '{} [{}]'.format(name, balance)

        else:
            return name

    def natural_key(self):
        return (self.uuid,)

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

    def balance(self, as_of=None, raw=False, leg_query=None, **kwargs):
        """Get the balance for this account, including child accounts

        Args:
            as_of (Date): Only include transactions on or before this date
            raw (bool): If true the returned balance should not have its sign
                        adjusted for display purposes.
            kwargs (dict): Will be used to filter the transaction legs

        Returns:
            Balance

        See Also:
            :meth:`simple_balance()`
        """
        balances = [
            account.simple_balance(as_of=as_of, raw=raw, leg_query=leg_query, **kwargs)
            for account
            in self.get_descendants(include_self=True)
        ]
        return sum(balances, Balance())

    def simple_balance(self, as_of=None, raw=False, leg_query=None, **kwargs):
        """Get the balance for this account, ignoring all child accounts

        Args:
            as_of (Date): Only include transactions on or before this date
            raw (bool): If true the returned balance should not have its sign
                        adjusted for display purposes.
            leg_query (models.Q): Django Q-expression, will be used to filter the transaction legs.
                                  allows for more complex filtering than that provided by **kwargs.
            kwargs (dict): Will be used to filter the transaction legs

        Returns:
            Balance
        """
        legs = self.legs
        if as_of:
            legs = legs.filter(transaction__date__lte=as_of)

        if leg_query or kwargs:
            leg_query = leg_query or models.Q()
            legs = legs.filter(leg_query, **kwargs)

        return legs.sum_to_balance() * (1 if raw else self.sign) + self._zero_balance()

    def _zero_balance(self):
        """Get a balance for this account with all currencies set to zero"""
        return Balance([Money('0', currency) for currency in self.currencies])

    @db_transaction.atomic()
    def transfer_to(self, to_account, amount, **transaction_kwargs):
        """Create a transaction which transfers amount to to_account

        This is a shortcut utility method which simplifies the process of
        transferring between accounts.

        This method attempts to perform the transaction in an intuitive manner.
        For example:

          * Transferring income -> income will result in the former decreasing and the latter increasing
          * Transferring asset (i.e. bank) -> income will result in the balance of both increasing
          * Transferring asset -> asset will result in the former decreasing and the latter increasing

        .. note::

            Transfers in any direction between ``{asset | expense} <-> {income | liability | equity}``
            will always result in both balances increasing. This may change in future if it is
            found to be unhelpful.

            Transfers to trading accounts will always behave as normal.

        Args:

            to_account (Account): The destination account.
            amount (Money): The amount to be transferred.
            transaction_kwargs: Passed through to transaction creation. Useful for setting the
                transaction `description` field.
        """
        if not isinstance(amount, Money):
            raise TypeError('amount must be of type Money')

        if to_account.sign == 1 and to_account.type != self.TYPES.trading:
            # Transferring from two positive-signed accounts implies that
            # the caller wants to reduce the first account and increase the second
            # (which is opposite to the implicit behaviour)
            direction = -1
        elif self.type == self.TYPES.liability and to_account.type == self.TYPES.expense:
            # Transfers from liability -> asset accounts should reduce both.
            # For example, moving money from Rent Payable (liability) to your Rent (expense) account
            # should use the funds you've built up in the liability account to pay off the expense account.
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
    """ Represents a transaction

    A transaction is a movement of funds between two accounts. Each transaction
    will have two or more legs, each leg specifies an account and an amount.

    .. note:

        When working with Hordak Transaction objects you will typically need to do so
        within a database transaction. This is because the database has integrity checks in
        place to ensure the validity of the transaction (i.e. money in = money out).

    See Also:

        :meth:`Account.transfer_to()` is a useful shortcut to avoid having to create transactions manually.

    Examples:

        You can manually create a transaction as follows::

            from django.db import transaction as db_transaction
            from hordak.models import Transaction, Leg

            with db_transaction.atomic():
                transaction = Transaction.objects.create()
                Leg.objects.create(transaction=transaction, account=my_account1, amount=Money(100, 'EUR'))
                Leg.objects.create(transaction=transaction, account=my_account2, amount=Money(-100, 'EUR'))

    Attributes:

        uuid (SmallUUID): UUID for transaction. Use to prevent leaking of IDs (if desired).
        timestamp (datetime): The datetime when the object was created.
        date (date): The date when the transaction actually occurred, as this may be different to
            :attr:`timestamp`.
        description (str): Optional user-provided description

    """
    uuid = SmallUUIDField(default=uuid_default(), editable=False)
    timestamp = models.DateTimeField(default=timezone.now, help_text='The creation date of this transaction object')
    date = models.DateField(default=timezone.now, help_text='The date on which this transaction occurred')
    description = models.TextField(default='', blank=True)

    objects = TransactionManager()

    class Meta:
        get_latest_by = 'date'

    def balance(self):
        return self.legs.sum_to_balance()

    def natural_key(self):
        return (self.uuid,)


class LegQuerySet(models.QuerySet):

    def sum_to_balance(self):
        """Sum the Legs of the QuerySet to get a `Balance`_ object
        """
        result = self.values('amount_currency').annotate(total=models.Sum('amount'))
        return Balance(
            [Money(r['total'], r['amount_currency']) for r in result]
        )


class LegManager(models.Manager):

    def get_by_natural_key(self, uuid):
        return self.get(uuid=uuid)

    def debits(self):
        """Filter for legs that were debits"""
        return self.filter(amount__gt=0)

    def credits(self):
        """Filter for legs that were credits"""
        return self.filter(amount__lt=0)


class Leg(models.Model):
    """ The leg of a transaction

    Represents a single amount either into or out of a transaction. All legs for a transaction
    must sum to zero, all legs must be of the same currency.

    Attributes:

        uuid (SmallUUID): UUID for transaction leg. Use to prevent leaking of IDs (if desired).
        transaction (Transaction): Transaction to which the Leg belongs.
        account (Account): Account the leg is transferring to/from.
        amount (Money): The amount being transferred
        description (str): Optional user-provided description
        type (str): :attr:`hordak.models.DEBIT` or :attr:`hordak.models.CREDIT`.

    """
    uuid = SmallUUIDField(default=uuid_default(), editable=False)
    transaction = models.ForeignKey(Transaction, related_name='legs', on_delete=models.CASCADE)
    account = models.ForeignKey(Account, related_name='legs',on_delete=models.CASCADE)
    amount = MoneyField(max_digits=13, decimal_places=2,
                        help_text='Record debits as positive, credits as negative',
                        default_currency=defaults.INTERNAL_CURRENCY)
    description = models.TextField(default='', blank=True)

    objects = LegManager.from_queryset(LegQuerySet)()

    def save(self, *args, **kwargs):
        if self.amount.amount == 0:
            raise exceptions.ZeroAmountError()
        return super(Leg, self).save(*args, **kwargs)

    def natural_key(self):
        return (self.uuid,)

    @property
    def type(self):
        if self.amount.amount < 0:
            return DEBIT
        elif self.amount.amount > 0:
            return CREDIT
        else:
            # This should have been caught earlier by the database integrity check.
            # If you are seeing this then something is wrong with your DB checks.
            raise exceptions.ZeroAmountError()

    def is_debit(self):
        return self.type == DEBIT

    def is_credit(self):
        return self.type == CREDIT

    def account_balance_after(self):
        """Get the balance of the account associated with this leg following the transaction"""
        # TODO: Consider moving to annotation, particularly once we can count on Django 1.11's subquery support
        transaction_date = self.transaction.date
        return self.account.balance(leg_query=(
            models.Q(transaction__date__lt=transaction_date)
            | (models.Q(transaction__date=transaction_date) & models.Q(transaction_id__lte=self.transaction_id))
        ))

    def account_balance_before(self):
        """Get the balance of the account associated with this leg before the transaction"""
        # TODO: Consider moving to annotation, particularly once we can count on Django 1.11's subquery support
        transaction_date = self.transaction.date
        return self.account.balance(leg_query=(
            models.Q(transaction__date__lt=transaction_date)
            | (models.Q(transaction__date=transaction_date) & models.Q(transaction_id__lt=self.transaction_id))
        ))


class StatementImportManager(models.Manager):

    def get_by_natural_key(self, uuid):
        return self.get(uuid=uuid)


class StatementImport(models.Model):
    """ Records an import of a bank statement

    Attributes:

        uuid (SmallUUID): UUID for statement import. Use to prevent leaking of IDs (if desired).
        timestamp (datetime): The datetime when the object was created.
        bank_account (Account): The account the import is for (should normally point to an asset
            account which represents your bank account)

    """
    uuid = SmallUUIDField(default=uuid_default(), editable=False)
    timestamp = models.DateTimeField(default=timezone.now)
    # TODO: Add constraint to ensure destination account expects statements (copy 0007)
    bank_account = models.ForeignKey(Account, related_name='imports',on_delete=models.CASCADE)
    source = models.CharField(max_length=20,
                              help_text='A value uniquely identifying where this data came from. '
                                        'Examples: "csv", "teller.io".')
    extra = JSONField(default=json_default, help_text='Any extra data relating to the import, probably specific '
                                            'to the data source.')

    objects = StatementImportManager()

    def natural_key(self):
        return (self.uuid,)


class StatementLineManager(models.Manager):

    def get_by_natural_key(self, uuid):
        return self.get(uuid=uuid)


class StatementLine(models.Model):
    """ Records an single imported bank statement line

    A StatementLine is purely a utility to aid in the creation of transactions
    (in the process known as reconciliation). StatementLines have no impact on
    account balances.

    However, the :meth:`StatementLine.create_transaction()` method can be used to create
    a transaction based on the information in the StatementLine.

    Attributes:

        uuid (SmallUUID): UUID for statement line. Use to prevent leaking of IDs (if desired).
        timestamp (datetime): The datetime when the object was created.
        date (date): The date given by the statement line
        statement_import (StatementImport): The import to which the line belongs
        amount (Decimal): The amount for the statement line, positive or nagative.
        description (str): Any description/memo information provided
        transaction (Transaction): Optionally, the transaction created for this statement line. This normally
            occurs during reconciliation. See also :meth:`StatementLine.create_transaction()`.
    """
    uuid = SmallUUIDField(default=uuid_default(), editable=False)
    timestamp = models.DateTimeField(default=timezone.now)
    date = models.DateField()
    statement_import = models.ForeignKey(StatementImport, related_name='lines',on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=13, decimal_places=2)
    description = models.TextField(default='', blank=True)
    type = models.CharField(max_length=50, default='')
    # TODO: Add constraint to ensure transaction amount = statement line amount
    # TODO: Add constraint to ensure one statement line per transaction
    transaction = models.ForeignKey(Transaction, default=None, blank=True, null=True,
                                    help_text='Reconcile this statement line to this transaction',
                                    on_delete=models.SET_NULL)
    source_data = JSONField(default=json_default, help_text='Original data received from the data source.')

    objects = StatementLineManager()

    def natural_key(self):
        return (self.uuid,)

    @property
    def is_reconciled(self):
        """Has this statement line been reconciled?

        Determined as ``True`` if :attr:`transaction` has been set.

        Returns:
            bool: ``True`` if reconciled, ``False`` if not.
        """
        return bool(self.transaction)

    @db_transaction.atomic()
    def create_transaction(self, to_account):
        """Create a transaction for this statement amount and account, into to_account

        This will also set this StatementLine's ``transaction`` attribute to the newly
        created transaction.

        Args:
            to_account (Account): The account the transaction is into / out of.

        Returns:
            Transaction: The newly created (and committed) transaction.

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
