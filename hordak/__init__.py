from decimal import ROUND_HALF_EVEN

import moneyed
from moneyed.localization import _sign, _format

_sign("en_GB", moneyed.GBP, prefix="£")

_format(
    "en_GB",
    group_size=3,
    group_separator=",",
    decimal_point=".",
    positive_sign="",
    trailing_positive_sign="",
    negative_sign="-",
    trailing_negative_sign="",
    rounding_method=ROUND_HALF_EVEN,
)
