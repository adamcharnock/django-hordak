from django import forms
from django.forms import inlineformset_factory

from hordak.models import Account, TransactionCsvImport, StatementImport, TransactionCsvImportColumn


class TransactionCsvImportForm(forms.ModelForm):
    bank_account = forms.ModelChoiceField(
        Account.objects.filter(is_bank_account=True), label="Import data for account"
    )

    class Meta:
        model = TransactionCsvImport
        fields = ("has_headings", "file")

    def save(self, commit=True):
        exists = bool(self.instance.pk)
        self.instance.hordak_import = StatementImport.objects.create(
            bank_account=self.cleaned_data["bank_account"], source="csv"
        )
        obj = super(TransactionCsvImportForm, self).save()
        if not exists:
            obj.create_columns()
        return obj


class TransactionCsvImportColumnForm(forms.ModelForm):
    class Meta:
        model = TransactionCsvImportColumn
        fields = ("to_field",)


TransactionCsvImportColumnFormSet = inlineformset_factory(
    parent_model=TransactionCsvImport,
    model=TransactionCsvImportColumn,
    form=TransactionCsvImportColumnForm,
    extra=0,
    can_delete=False,
)
