#!/usr/bin/env python
# encoding: utf-8
from enum import Enum


class OrderType(Enum):
    OrderTypeLimit = "limit"
    OrderTypeMarket = "market"


class Side(Enum):
    SideBuy = "buy"
    SideSell = "sell"

    def opposite(self):
        if self == Side.SideBuy:
            return Side.SideSell
        return Side.SideBuy


def opposite(side: Side) -> Side:
    if side == Side.SideBuy:
        return Side.SideSell
    elif side == Side.SideSell:
        return Side.SideBuy


class TimeInForceType(Enum):
    GoodTillCanceled = "GTC"
    ImmediateOrCancel = "IOC"
    GoodTillCrossing = "GTX"
    FillOrKill = "FOK"


class OrderStatus(Enum):
    OrderStatusNew = "new"
    OrderStatusOpen = "open"
    OrderStatusCancelling = "cancelling"
    OrderStatusCancelled = "cancelled"
    OrderStatusPartial = "partial"
    OrderStatusFilled = "filled"


class DoneReason(Enum):
    DoneReasonFilled = "filled"
    DoneReasonCancelled = "cancelled"
