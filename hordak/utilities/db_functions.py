import json
from datetime import date
from functools import cached_property
from typing import Union

from django.db.models import Func
from django.db.models.expressions import Combinable, Value
from djmoney.models.fields import MoneyField
from moneyed import Money

from hordak.utilities.currency import Balance


class GetBalance(Func):
    """Django representation of the get_balance() custom database function provided by Hordak"""

    function = "GET_BALANCE"

    def __init__(
        self,
        account_id: Union[Combinable, int],
        as_of: Union[Combinable, date] = None,
        output_field=None,
        **extra
    ):
        if as_of is not None:
            if not isinstance(as_of, Combinable):
                as_of = Value(as_of)

        output_field = output_field or MoneyField()
        super().__init__(account_id, as_of, output_field=output_field, **extra)

    @cached_property
    def convert_value(self):
        # Convert the JSON output into a Balance object. Example of a JSON response:
        #    [{"amount": 100.00, "currency": "EUR"}]
        def convertor(value, expression, connection):
            value = json.loads(value)
            return Balance([Money(v["amount"], v["currency"]) for v in value])

        return convertor
