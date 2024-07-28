import json
from datetime import date
from functools import cached_property
from typing import Union

from django.db.models import Func
from django.db.models.expressions import Combinable, Value
from djmoney.models.fields import MoneyField
from moneyed import Money

from hordak import defaults
from hordak.utilities.currency import Balance


class GetBalance(Func):
    """Django representation of the get_balance() custom database function provided by Hordak"""

    function = "GET_BALANCE"

    def __init__(
        self,
        account_id: Union[Combinable, int],
        as_of: Union[Combinable, date, str] = None,
        as_of_leg_id: Union[Combinable, int] = None,
        output_field=None,
        **extra
    ):
        """Create a new GetBalance()

        Examples:

            .. code-block:: python

                from hordak.utilities.db_functions import GetBalance

                GetBalance(account_id=5)
                GetBalance(account_id=5, as_of='2000-01-01')

                Account.objects.all().annotate(
                    balance=GetBalance(F("id"), as_of='2000-01-01')
                )

        """
        if as_of is not None:
            if not isinstance(as_of, Combinable):
                as_of = Value(as_of)

        if as_of is None and as_of_leg_id is not None:
            raise ValueError("as_of cannot be None when specifying as_of_leg_id")

        output_field = output_field or MoneyField()
        super().__init__(
            account_id, as_of, as_of_leg_id, output_field=output_field, **extra
        )

    @cached_property
    def convert_value(self):
        # Convert the JSON output into a Balance object. Example of a JSON response:
        #    [{"amount": 100.00, "currency": "EUR"}]
        def convertor(value, expression, connection):
            if not value:
                return Balance([Money("0", defaults.DEFAULT_CURRENCY)])
            value = json.loads(value)
            return Balance([Money(v["amount"], v["currency"]) for v in value])

        return convertor
