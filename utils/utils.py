#!/usr/bin/env python
# encoding: utf-8
import json
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from enum import Enum


class JsonEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Enum):
            return str(obj.value)
        elif isinstance(obj, Decimal):
            return str(obj)
        return super().default(obj)


def truncate_decimal(d, places) -> Decimal:
    return d.quantize(Decimal(10) ** -places, rounding=ROUND_DOWN)


def normalize_price(price: Decimal, scale: int) -> Decimal:
    """Normalize price to the specified scale using rounding."""
    return price.quantize(Decimal(10) ** -scale, rounding=ROUND_HALF_UP)


def normalize_size(size: Decimal, scale: int) -> Decimal:
    """Normalize size to the specified scale using rounding."""
    return size.quantize(Decimal(10) ** -scale, rounding=ROUND_HALF_UP)
