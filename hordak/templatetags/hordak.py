from __future__ import absolute_import
import logging

import babel.numbers
from django import template
from django.utils.safestring import mark_safe
from hordak.utilities.currency import Balance
from moneyed import Money
from decimal import Decimal

register = template.Library()
logger = logging.getLogger(__name__)


@register.filter(name="abs")
def abs_val(value):
    return abs(value)


@register.filter()
def inv(value):
    if not value:
        return value
    return value * -1


@register.filter()
def currency(value):
    if value is None:
        return None

    if isinstance(value, Balance):
        locale_values = []
        for money in value.monies():
            locale_value = babel.numbers.format_currency(
                abs(money.amount), currency=money.currency.code
            )
            locale_value = locale_value if money.amount >= 0 else "({})".format(locale_value)
            locale_values.append(locale_value)
    else:
        locale_value = babel.numbers.format_decimal(abs(value))
        locale_value = locale_value if value >= 0 else "({})".format(locale_value)
        locale_values = [locale_value]

    return ", ".join(locale_values)


@register.filter(is_safe=True)
def color_currency(value, flip=False):
    value = value or 0
    if isinstance(value, Money):
        value = value.amount
    if value > 0:
        css_class = "neg" if flip else "pos"
    elif value < 0:
        css_class = "pos" if flip else "neg"
    else:
        css_class = "zero"
    out = """<div class="%s">%s</div>""" % (css_class, currency(value))
    return mark_safe(out)


@register.filter(is_safe=True)
def color_currency_inv(value):
    return color_currency(value, flip=True)


@register.filter(is_safe=True)
def negative(value):
    value = value or 0
    return abs(value) * -1


def valid_numeric(arg):
    if isinstance(arg, (int, float, Decimal)):
        return arg
    try:
        return int(arg)
    except ValueError:
        return float(arg)


# Pulled from django-mathfilters


def handle_float_decimal_combinations(value, arg, operation):
    if isinstance(value, float) and isinstance(arg, Decimal):
        logger.warning("Unsafe operation: {0!r} {1} {2!r}.".format(value, operation, arg))
        value = Decimal(str(value))
    if isinstance(value, Decimal) and isinstance(arg, float):
        logger.warning("Unsafe operation: {0!r} {1} {2!r}.".format(value, operation, arg))
        arg = Decimal(str(arg))
    return value, arg


@register.filter
def sub(value, arg):
    """Subtract the arg from the value."""
    try:
        nvalue, narg = handle_float_decimal_combinations(
            valid_numeric(value), valid_numeric(arg), "-"
        )
        return nvalue - narg
    except (ValueError, TypeError):
        try:
            return value - arg
        except Exception:
            return ""


sub.is_safe = False


@register.filter(name="addition")
def addition(value, arg):
    """Float-friendly replacement for Django's built-in `add` filter."""
    try:
        nvalue, narg = handle_float_decimal_combinations(
            valid_numeric(value), valid_numeric(arg), "+"
        )
        return nvalue + narg
    except (ValueError, TypeError):
        try:
            return value + arg
        except Exception:
            return ""


addition.is_safe = False
