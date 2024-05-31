from decimal import Decimal

from hordak.defaults import DECIMAL_PLACES


def ratio_split(amount, ratios, precision=None):
    """Split in_value according to the ratios specified in `ratios`

    This is special in that it ensures the returned values always sum to
    in_value (i.e. we avoid losses or gains due to rounding errors). As a
    result, this method returns a list of `Decimal` values with length equal
    to that of `ratios`.

    Examples:

        .. code-block:: python

            >>> from hordak.utilities.money import ratio_split
            >>> from decimal import Decimal
            >>> ratio_split(Decimal('10'), [Decimal('1'), Decimal('2')])
            [Decimal('3.33'), Decimal('6.67')]

        Note the returned values sum to the original input of ``10``. If we were to
        do this calculation in a naive fashion then the returned values would likely
        be ``3.33`` and ``6.66``, which would sum to ``9.99``, thereby loosing
        ``0.01``.

    Args:
        amount (Decimal): The amount to be split
        ratios (list[Decimal]): The ratios that will determine the split
        precision (Optional[Decimal]): How many decimal places to round to
            (defaults to the `HORDAK_DECIMAL_PLACES` setting)

    Returns: list(Decimal)

    """
    if precision is None:
        precision = Decimal(10) ** Decimal(-DECIMAL_PLACES)
    assert amount == amount.quantize(precision), (
        "Input amount is not at the required precision (%s)" % precision
    )

    # Distribute the amount according to the ratios:
    ratio_total = sum(ratios)
    assert ratio_total > 0, "Ratio sum cannot be zero"
    values = [amount * ratio / ratio_total for ratio in ratios]

    # Now round the values to the desired number of decimal places:
    rounded = [v.quantize(precision) for v in values]

    # The rounded values may not add up to the exact amount.
    # Use the Largest Remainder algorithm to distribute the
    # difference between participants with non-zero ratios:
    participants = [i for i in range(len(ratios)) if ratios[i] != Decimal(0)]
    for p in sorted(participants, key=lambda i: rounded[i] - values[i]):
        total = sum(rounded)
        if total < amount:
            rounded[p] += precision
        elif total > amount:
            rounded[p] -= precision
        else:
            break

    rounded_sum = sum(rounded)
    assert rounded_sum == amount, (
        "Sanity check failed, output total (%s) did not match input amount"
        % rounded_sum
    )

    return rounded
