import json
from typing import List, Union

from django.core.exceptions import ValidationError
from django.db import models
from moneyed import Money

from hordak.utilities.currency import Balance


class BalanceField(models.JSONField):
    def from_db_value(self, value, expression, connection):
        """
        Converts the JSON string from the database to a Balance object.
        """
        if value is None:
            return value
        try:
            return json_to_balance(value)
        except ValueError:
            raise ValidationError("Invalid JSON format")

    def to_python(self, value):
        """
        Converts the value into Balance objects when accessing it via Python.
        """
        if value is None:
            return value
        try:
            return json_to_balance(value)
        except ValueError:
            raise ValidationError("Invalid JSON format")

    def get_prep_value(self, value):
        """
        Converts the Balance object to JSON string before saving to the database.
        """
        if isinstance(value, list):
            return json.dumps(
                [{"amount": bal.amount, "currency": bal.currency} for bal in value]
            )
        return super().get_prep_value(value)


def json_to_balance(json_: Union[str, List[dict]]) -> Balance:
    if isinstance(json_, str):
        json_ = json.loads(json_)
    return Balance([Money(m["amount"], m["currency"]) for m in json_])


def balance_to_json(balance: Balance) -> List[dict]:
    return [{"amount": m.amount, "currency": m.currency.code} for m in balance]
