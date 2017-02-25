from django import forms
from django.forms import inlineformset_factory

from hordak.models import Account, TransactionImport, StatementImport, TransactionImportColumn


class TransactionImportForm(forms.ModelForm):
    bank_account = forms.ModelChoiceField(Account.objects.filter(is_bank_account=True), label='Import data for account')

    class Meta:
        model = TransactionImport
        fields = ('has_headings', 'file')

    def save(self, commit=True):
        exists = bool(self.instance.pk)
        self.instance.hordak_import = StatementImport.objects.create(
            bank_account=self.cleaned_data['bank_account'],
        )
        obj = super(TransactionImportForm, self).save()
        if not exists:
            obj.create_columns()
        return obj


class TransactionImportColumnForm(forms.ModelForm):

    class Meta:
        model = TransactionImportColumn
        fields = ('to_field',)


TransactionImportColumnFormSet = inlineformset_factory(
    parent_model=TransactionImport,
    model=TransactionImportColumn,
    form=TransactionImportColumnForm,
    extra=0,
    can_delete=False,
)
