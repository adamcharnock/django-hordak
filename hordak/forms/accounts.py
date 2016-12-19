from django import forms

from hordak.models import Account


class AccountForm(forms.ModelForm):
    """Form for updating & creating accounts

    Note that this form prevents the ``_type`` and ``currencies``
    fields from being updated as this could be a problem for accounts
    which transactions have been created for. This could be made more
    liberal in future as required.
    """

    class Meta:
        model = Account
        exclude = []

    def __init__(self, *args, **kwargs):
        updating = bool(kwargs.get('instance'))

        if not updating:
            # Set a sensible default code when creating only
            initial = kwargs.get('kwargs', {})
            if 'code' not in initial:
                # TODO: This could be made more robust
                initial['code'] = '{0:02d}'.format(Account.objects.count() + 1)
            kwargs['initial'] = initial

        super(AccountForm, self).__init__(*args, **kwargs)

        if updating:
            # Don't allow type and currencies to be edited
            del self.fields['_type']
            del self.fields['currencies']

    def clean(self):
        cleaned_data = super(AccountForm, self).clean()
        is_bank_account = cleaned_data['is_bank_account']

        if is_bank_account and cleaned_data['_type'] != Account.TYPES.asset:
            raise forms.ValidationError('Bank accounts must also be asset accounts.')

        if is_bank_account and len(cleaned_data['currencies']) > 1:
            raise forms.ValidationError('Bank accounts may only have one currency.')

        return cleaned_data
