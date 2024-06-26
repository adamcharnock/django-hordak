from django.db import models
from django.utils.translation import gettext_lazy as _
from djmoney.models.fields import MoneyField

from hordak.defaults import DECIMAL_PLACES, MAX_DIGITS, get_internal_currency
from hordak.models import Account, Transaction


class LegType(models.TextChoices):
    debit = "DR", "Debit"
    credit = "CR", "Credit"


class LegView(models.Model):
    """An accounting view onto the Legs table

    This provides a number of features on top of the raw Legs table:

    1. Shows the leg type (debit/credit)
    2. All amounts are reported as positive
    3. Amounts are available in the credit and debit columns (and are NULL if not applicable)
    4. A running total `account_balance` field is provided
    5. Shows some transaction fields (date, description)

    Note that this is a database view and is therefore read-only.

    You can also improve query performance (in Postgresql) by deferring the
    `account_balance` field, assuming the value not required. For example:

        HordakLegView.objects.defer('account_balance')

    """

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
    date = models.DateField(
        help_text="The date on which this transaction leg occurred",
        verbose_name=_("date"),
    )
    amount = MoneyField(
        max_digits=MAX_DIGITS,
        decimal_places=DECIMAL_PLACES,
        default_currency=get_internal_currency,
        verbose_name=_("amount"),
    )
    type = models.CharField(
        max_length=2,
        help_text="Type of this transaction leg: debit or credit",
        verbose_name=_("type"),
        choices=LegType,
    )
    credit = models.DecimalField(
        max_digits=MAX_DIGITS,
        decimal_places=DECIMAL_PLACES,
        help_text="Amount of this credit, or NULL if not a credit",
        verbose_name=_("credit amount"),
    )
    debit = models.DecimalField(
        max_digits=MAX_DIGITS,
        decimal_places=DECIMAL_PLACES,
        help_text="Amount of this debit, or NULL if not a debit",
        verbose_name=_("debit amount"),
    )
    account_balance = models.DecimalField(
        max_digits=MAX_DIGITS,
        decimal_places=DECIMAL_PLACES,
        help_text=(
            "Account balance following this transaction. For multiple-currency accounts this will "
            "be the balance of the same currency as the leg amount."
        ),
        verbose_name=_("account balance"),
    )
    leg_description = models.TextField(
        verbose_name=_("leg description"),
    )
    transaction_description = models.TextField(
        verbose_name=_("transaction description"),
    )

    class Meta:
        managed = False
        db_table = "hordak_leg_view"

    def save(self, *args, **kwargs):
        raise RuntimeError("Cannot save, this is a read-only view")
