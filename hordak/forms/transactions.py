from django import forms
from django.core.exceptions import ValidationError
from django.forms import BaseInlineFormSet, inlineformset_factory
from djmoney.forms import MoneyField
from hordak.models import Account, Transaction, Leg
from moneyed import Money
from mptt.forms import TreeNodeChoiceField


class SimpleTransactionForm(forms.ModelForm):
    """A simplified form for transferring an an amount from one account to another

    This only allows the creation of transactions with two legs. This also uses
    :meth:`Account.transfer_to()`.

    See Also:

        * :meth:`hordak.models.Account.transfer_to()`.
    """
    from_account = forms.ModelChoiceField(queryset=Account.objects.filter(children__isnull=True), to_field_name='uuid')
    to_account = forms.ModelChoiceField(queryset=Account.objects.filter(children__isnull=True), to_field_name='uuid')
    amount = MoneyField(decimal_places=2)

    class Meta:
        model = Transaction
        fields = ['amount', 'from_account', 'to_account', 'description', ]

    def save(self, commit=True):
        from_account = self.cleaned_data.get('from_account')
        to_account = self.cleaned_data.get('to_account')
        amount = self.cleaned_data.get('amount')

        return from_account.transfer_to(
            to_account=to_account,
            amount=amount,
            description=self.cleaned_data.get('description')
        )


class TransactionForm(forms.ModelForm):
    """A form for managing transactions with an arbitrary number of legs.

    You will almost certainly
    need to combine this with :class:`LegFormSet` in order to
    create & edit transactions.

    .. note::

        For simple transactions (with a single credit and single debit) you a probably
        better of using the :class:`SimpleTransactionForm`. This significantly simplifies
        both the interface and implementation.

    Attributes:

        description (forms.CharField): Optional description/notes for this transaction

    See Also:

        This is a `ModelForm` for the :class:`Transaction model <hordak.models.Transaction>`.
    """
    description = forms.CharField(label='Transaction notes', required=False)

    class Meta:
        model = Transaction
        fields = ('description', )

    def save(self, commit=True):
        return super(TransactionForm, self).save(commit)


class LegForm(forms.ModelForm):
    """A form for representing a single transaction leg

    Attributes:

        account (TreeNodeChoiceField): Choose an account the leg will interact with
        description (forms.CharField): Optional description/notes for this leg
        amount (MoneyField): The amount for this leg. Positive values indicate money coming into the transaction,
            negative values indicate money leaving the transaction.

    See Also:

        This is a `ModelForm` for the :class:`Leg model <hordak.models.Leg>`.
    """
    account = TreeNodeChoiceField(Account.objects.all(), to_field_name='uuid')
    description = forms.CharField(required=False)
    amount = MoneyField(required=True, decimal_places=2)

    class Meta:
        model = Leg
        fields = ('amount', 'account', 'description')

    def __init__(self, *args, **kwargs):
        self.statement_line = kwargs.pop('statement_line', None)
        super(LegForm, self).__init__(*args, **kwargs)

    def clean_amount(self):
        amount = self.cleaned_data['amount']
        if amount.amount <= 0:
            raise ValidationError('Amount must be greater than zero')

        if self.statement_line and self.statement_line.amount < 0:
            amount *= -1

        return amount


class BaseLegFormSet(BaseInlineFormSet):

    def __init__(self, **kwargs):
        self.statement_line = kwargs.pop('statement_line')
        self.currency = self.statement_line.statement_import.bank_account.currencies[0]
        super(BaseLegFormSet, self).__init__(**kwargs)

    def get_form_kwargs(self, index):
        kwargs = super(BaseLegFormSet, self).get_form_kwargs(index)
        kwargs.update(statement_line=self.statement_line)
        if index == 0:
            kwargs.update(initial=dict(
                amount=Money(abs(self.statement_line.amount), self.currency)
            ))
        return kwargs

    def clean(self):
        super(BaseLegFormSet, self).clean()

        if any(self.errors):
            return

        amounts = [f.cleaned_data['amount'] for f in self.forms if f.has_changed()]
        if Money(self.statement_line.amount, self.currency) != sum(amounts):
            raise ValidationError('Amounts must add up to {}'.format(self.statement_line.amount))


LegFormSet = inlineformset_factory(
    parent_model=Transaction,
    model=Leg,
    form=LegForm,
    extra=4,
    can_delete=False,
    formset=BaseLegFormSet,
)
