#!/usr/bin/env python
# encoding: utf-8

from decimal import Decimal, ROUND_DOWN


def truncate_decimal(d, places) -> Decimal:
    """Truncate Decimal d to the given number of places.

    >>> truncate_decimal(Decimal('1.234567'), 4)
    Decimal('1.2345')
    >>> truncate_decimal(Decimal('-0.999'), 1)
    Decimal('-0.9')
    """
    return d.quantize(Decimal(10) ** -places, rounding=ROUND_DOWN)
