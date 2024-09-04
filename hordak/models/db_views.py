from django.db import models
from django.utils.translation import gettext_lazy as _
from djmoney.models.fields import MoneyField

from hordak.defaults import (
    DECIMAL_PLACES,
    MAX_DIGITS,
    default_currency,
    get_internal_currency,
)
from hordak.models import Account, AccountType, Transaction
from hordak.utilities.db import BalanceField


class LegType(models.TextChoices):
    debit = "DR", "Debit"
    credit = "CR", "Credit"


class LegView(models.Model):
    """An accounting view onto the Legs table

    .. warning::

        Hordak's database views are still experimental and may change or be
        removed in a future version.

    This provides a number of features on top of the raw Legs table:

    1. Shows the leg type (debit/credit)
    2. All amounts are reported as positive
    3. Amounts are available in the credit and debit columns (and are NULL if not applicable)
    4. A running total `account_balance` field is provided
    5. Shows some transaction fields (date, description)

    Note that this is a database view and is therefore read-only.

    You can also improve query performance (in Postgresql) by deferring the
    `account_balance` field, assuming the value not required. For example:

        .. code-block:: python

            HordakLegView.objects.defer('account_balance')

    Attributes:

        id (int): The leg ID
        uuid (UUID): The leg UUID
        transaction (Transaction): The transaction which contains this leg
        account (Account): The account this leg is associated with
        date (date): The date when the parent transaction actually occurred
        amount (Balance): The balance of this leg (use ``amount.currency``
                          to get the currency for the other ``Decimal`` fields on this view.
        type (LegType): Either ``LegType.debit`` or ``LegType.credit``.
        credit (Decimal): Amount of this credit, or NULL if not a credit
        debit (Decimal): Amount of this debit, or NULL if not a debit
        account_name (str): The name of account for the leg
        account_full_code (str): The full account code of account for the leg
        account_type (AccountType): The type of account for the leg
        account_balance (Decimal): Account balance following this transaction.
                                   For multiple-currency accounts this will
                                   be the balance of the same currency as the leg amount.
        leg_description (str): Description of the leg
        transaction_description (str): Description of the transaction

    """

    leg = models.OneToOneField(
        "hordak.Leg",
        verbose_name=_("leg"),
        on_delete=models.DO_NOTHING,
        related_name="view",
        db_column="id",
        primary_key=True,
    )
    uuid = models.UUIDField(verbose_name=_("uuid"), editable=False)
    transaction = models.ForeignKey(
        Transaction,
        related_name="legs_view",
        on_delete=models.DO_NOTHING,
        verbose_name=_("transaction"),
    )
    account = models.ForeignKey(
        Account,
        related_name="legs_view",
        on_delete=models.DO_NOTHING,
        verbose_name=_("account"),
    )
    account_name = models.CharField(
        editable=False, max_length=255, verbose_name=_("name")
    )
    account_full_code = models.CharField(
        editable=False,
        max_length=255,
        verbose_name=_("full_code"),
    )
    account_type = models.CharField(
        editable=False,
        max_length=2,
        choices=AccountType.choices,
        verbose_name=_("type"),
    )

    date = models.DateField(
        editable=False,
        help_text="The date on which this transaction leg occurred",
        verbose_name=_("date"),
    )
    amount = MoneyField(
        editable=False,
        max_digits=MAX_DIGITS,
        decimal_places=DECIMAL_PLACES,
        default_currency=default_currency,
        currency_field_name="currency",
        verbose_name=_("amount"),
    )
    legacy_amount = MoneyField(
        editable=False,
        max_digits=MAX_DIGITS,
        decimal_places=DECIMAL_PLACES,
        currency_field_name="currency",
        verbose_name=_("legacy amount"),
        help_text=(
            "The leg amount, credits are positive, debit are negative "
            "(Legacy for Hordak 1.0 compatability)"
        ),
    )
    type = models.CharField(
        editable=False,
        max_length=2,
        help_text="Type of this transaction leg: debit or credit",
        verbose_name=_("type"),
        choices=LegType.choices,
    )
    credit = MoneyField(
        editable=False,
        max_digits=MAX_DIGITS,
        decimal_places=DECIMAL_PLACES,
        help_text="Amount of this credit, or NULL if not a credit",
        currency_field_name="currency",
        verbose_name=_("credit amount"),
        default=None,
        null=True,
        blank=True,
    )
    debit = MoneyField(
        editable=False,
        max_digits=MAX_DIGITS,
        decimal_places=DECIMAL_PLACES,
        help_text="Amount of this debit, or NULL if not a debit",
        default_currency=get_internal_currency,
        currency_field_name="currency",
        verbose_name=_("debit amount"),
        default=None,
        null=True,
        blank=True,
    )
    account_balance = models.DecimalField(
        editable=False,
        max_digits=MAX_DIGITS,
        decimal_places=DECIMAL_PLACES,
        help_text=(
            "Account balance following this transaction. For multiple-currency accounts this will "
            "be the balance of the same currency as the leg amount. Will be NULL/None for non-leaf accounts."
        ),
        verbose_name=_("account balance"),
    )
    leg_description = models.TextField(
        editable=False,
        verbose_name=_("leg description"),
    )
    transaction_description = models.TextField(
        editable=False,
        verbose_name=_("transaction description"),
    )

    objects = models.Manager()

    class Meta:
        managed = False
        db_table = "hordak_leg_view"

    def save(self, *args, **kwargs):
        raise RuntimeError("Cannot save, this is a read-only view")


class TransactionView(models.Model):
    """An accounting view onto the Transaction table

    .. warning::

        Hordak's database views are still experimental and may change or be
        removed in a future version.

    This provides a number of features on top of the raw Transaction table:

    1. Shows the transaction amount (JSON list, one value per currency)
    2. Shows credited/debited account IDs & names

    Note that this is a database view and is therefore read-only.

    You can also improve query performance (in Postgresql) by deferring unneeded
    fields. For example:

        .. code-block:: python

            HordakLegView.objects.defer(
                'credit_account_ids',
                'debit_account_ids',
                'credit_account_names',
                'debit_account_names',
            )
    """

    parent = models.OneToOneField(
        Transaction,
        db_column="id",
        editable=False,
        on_delete=models.DO_NOTHING,
        related_name="view",
        primary_key=True,
    )
    uuid = models.UUIDField(verbose_name=_("uuid"), editable=False)
    timestamp = models.DateTimeField(
        editable=False,
        help_text="The creation date of this transaction object",
        verbose_name=_("timestamp"),
    )
    date = models.DateField(
        editable=False,
        help_text="The date on which this transaction occurred",
        verbose_name=_("date"),
    )
    description = models.TextField(editable=False, verbose_name=_("description"))
    amount = BalanceField(
        editable=False, help_text="The total amount transferred in this transaction"
    )

    credit_account_ids = models.JSONField(
        editable=False,
        help_text="List of account ids for the credit legs of this transaction",
    )
    debit_account_ids = models.JSONField(
        editable=False,
        help_text="List of account ids for the debit legs of this transaction",
    )
    credit_account_names = models.JSONField(
        editable=False,
        help_text="List of account names for the credit legs of this transaction",
    )
    debit_account_names = models.JSONField(
        editable=False,
        help_text="List of account names for the debit legs of this transaction",
    )

    class Meta:
        managed = False
        db_table = "hordak_transaction_view"

    def save(self, *args, **kwargs):
        raise RuntimeError("Cannot save, this is a read-only view")
