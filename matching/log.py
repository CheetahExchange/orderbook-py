#!/usr/bin/env python
# encoding: utf-8

from decimal import Decimal
from enum import Enum
from matching.order_book import BookOrder
import time

from models.types import DoneReason


class LogType(Enum):
    LogTypeMatch = "match"
    LogTypeOpen = "open"
    LogTypeDone = "done"


class Base(object):
    def __init__(self, _type: LogType, seq: int, product_id: str, _time: int):
        self.type = _type
        self.sequence = seq
        self.product_id = product_id
        self.time = _time

    def get_seq(self) -> int:
        return self.sequence


class OpenLog(Base):
    def __init__(self, log_seq: int, product_id: str, taker_order: BookOrder):
        super().__init__(LogType.LogTypeOpen, log_seq, product_id, time.time_ns())
        self.order_id = taker_order.order_id
        self.user_id = taker_order.user_id
        self.remaining_size = taker_order.size
        self.price = taker_order.price
        self.side = taker_order.side
        self.time_in_force = taker_order.time_in_force

    def get_seq(self) -> int:
        return self.sequence


class DoneLog(Base):
    def __init__(self, log_seq: int, product_id: str, order: BookOrder, remaining_size: Decimal, reason: DoneReason):
        super().__init__(LogType.LogTypeDone, log_seq, product_id, time.time_ns())
        self.order_id = order.order_id
        self.user_id = order.user_id
        self.remaining_size = remaining_size
        self.price = order.price
        self.reason = reason
        self.side = order.side
        self.time_in_force = order.time_in_force

    def get_seq(self) -> int:
        return self.sequence


class MatchLog(Base):
    def __init__(self, log_seq: int, product_id: str, trade_seq: int, taker_order: BookOrder, maker_order: BookOrder,
                 price: Decimal, size: Decimal):
        super().__init__(LogType.LogTypeMatch, log_seq, product_id, time.time_ns())
        self.trade_seq = trade_seq
        self.taker_order_id = taker_order.order_id
        self.maker_order_id = maker_order.order_id
        self.taker_user_id = taker_order.user_id
        self.maker_user_id = maker_order.user_id
        self.side = maker_order.side
        self.price = price
        self.size = size
        self.taker_time_in_force = taker_order.time_in_force
        self.maker_time_in_force = maker_order.time_in_force

    def get_seq(self) -> int:
        return self.sequence
