import json

from django import forms
from djmoney.settings import CURRENCY_CHOICES

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
        exclude = ["full_code"]

    currencies = forms.JSONField()

    def __init__(self, *args, **kwargs):
        self.is_updating = bool(kwargs.get("instance")) and kwargs["instance"].pk

        if not self.is_updating:
            # Set a sensible default account code when creating
            initial = kwargs.get("kwargs", {})
            if "code" not in initial:
                # TODO: This could be made more robust
                try:
                    account_code = Account.objects.latest("pk").id + 1
                except Account.DoesNotExist:
                    account_code = 1
                initial["code"] = "{0:02d}".format(account_code)
            kwargs["initial"] = initial

        super(AccountForm, self).__init__(*args, **kwargs)

        try:
            self.tmp_currencies = args[0].get("currencies")
        except IndexError:
            self.tmp_currencies = kwargs.get("data", {}).get("currencies")

        if self.is_updating:
            del self.fields["type"]
            del self.fields["currencies"]
            del self.fields["is_bank_account"]

    def _check_currencies_json(self):
        currencies = self.tmp_currencies

        if isinstance(self.tmp_currencies, str):
            try:
                currencies = json.loads(self.tmp_currencies)
            except json.JSONDecodeError:
                if "currencies" in self.fields:
                    self.add_error(
                        "currencies",
                        'Currencies needs to be valid JSON (i.e. ["USD", "EUR"] or ["USD"])'
                        + f" - {self.tmp_currencies} is not valid JSON.",
                    )

                return

        for currency in currencies:
            if currency not in [choice[0] for choice in CURRENCY_CHOICES]:
                if "currencies" in self.fields:
                    self.add_error(
                        "currencies",
                        f"Select a valid choice. {currency} is not one of the available choices.",
                    )

    def clean(self):
        cleaned_data = super(AccountForm, self).clean()
        is_bank_account = (
            self.instance.is_bank_account
            if self.is_updating
            else cleaned_data["is_bank_account"]
        )

        if (
            not self.is_updating
            and is_bank_account
            and cleaned_data["type"] != Account.TYPES.asset
        ):
            raise forms.ValidationError("Bank accounts must also be asset accounts.")

        if (
            not self.is_updating
            and is_bank_account
            and len(cleaned_data["currencies"]) > 1
        ):
            raise forms.ValidationError("Bank accounts may only have one currency.")

        self._check_currencies_json()

        return cleaned_data
