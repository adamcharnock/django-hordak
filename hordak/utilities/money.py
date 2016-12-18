from decimal import Decimal


def ratio_split(amount, ratios, precision=2):
    """ Split in_value according to the ratios specified in `ratios`

    This is special in that it ensures the returned values always sum to
    in_value (i.e. we avoid losses or gains due to rounding errors)

    Args:
        amount (Decimal):
        ratios (list[Decimal]):
        precision (int):

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
