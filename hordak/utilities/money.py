from decimal import Decimal


def ratio_split(amount, ratios):
    """ Split in_value according to the ratios specified in `ratios`

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

    Returns: list(Decimal)

    """
    ratio_total = sum(ratios)
    divided_value = amount / ratio_total
    values = []
    for ratio in ratios:
        value = divided_value * ratio
        values.append(value)

    # Now round the values, keeping track of the bits we cut off
    rounded = [v.quantize(Decimal('0.01')) for v in values]
    remainders = [v - rounded[i] for i, v in enumerate(values)]
    remainder = sum(remainders)
    # Give the last person the (positive or negative) remainder
    rounded[-1] = (rounded[-1] + remainder).quantize(Decimal('0.01'))

    assert sum(rounded) == amount

    return rounded
