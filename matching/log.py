#!/usr/bin/env python
# encoding: utf-8
import json
from decimal import Decimal
from enum import Enum
import time

from models.types import DoneReason, Side, TimeInForceType
from utils.utils import JsonEncoder


class LogType(Enum):
    LogTypeMatch = "match"
    LogTypeOpen = "open"
    LogTypeDone = "done"


class Log(object):
    def __init__(self, _type: LogType, seq: int, product_id: str, _time: int):
        self.type: LogType = _type
        self.sequence: int = seq
        self.product_id: str = product_id
        self.time: int = _time

    def get_seq(self) -> int:
        return self.sequence

    @staticmethod
    def to_json_str(log):
        return json.dumps(vars(log), cls=JsonEncoder)


class OpenLog(Log):
    def __init__(self, log_seq: int, product_id: str, taker_order):
        super().__init__(LogType.LogTypeOpen, log_seq, product_id, time.time_ns())
        self.order_id: int = taker_order.order_id
        self.user_id: int = taker_order.user_id
        self.remaining_size: Decimal = taker_order.size
        self.price: Decimal = taker_order.price
        self.side: Side = taker_order.side
        self.time_in_force: TimeInForceType = taker_order.time_in_force

    def get_seq(self) -> int:
        return self.sequence

    @staticmethod
    def to_json_str(log):
        return json.dumps(vars(log), cls=JsonEncoder)


class DoneLog(Log):
    def __init__(self, log_seq: int, product_id: str, order, remaining_size: Decimal, reason: DoneReason):
        super().__init__(LogType.LogTypeDone, log_seq, product_id, time.time_ns())
        self.order_id: int = order.order_id
        self.user_id: int = order.user_id
        self.remaining_size: Decimal = remaining_size
        self.price: Decimal = order.price
        self.reason: DoneReason = reason
        self.side: Side = order.side
        self.time_in_force: TimeInForceType = order.time_in_force

    def get_seq(self) -> int:
        return self.sequence

    @staticmethod
    def to_json_str(log):
        return json.dumps(vars(log), cls=JsonEncoder)


class MatchLog(Log):
    def __init__(self, log_seq: int, product_id: str, trade_seq: int, taker_order, maker_order,
                 price: Decimal, size: Decimal):
        super().__init__(LogType.LogTypeMatch, log_seq, product_id, time.time_ns())
        self.trade_seq: int = trade_seq
        self.taker_order_id: int = taker_order.order_id
        self.maker_order_id: int = maker_order.order_id
        self.taker_user_id: int = taker_order.user_id
        self.maker_user_id: int = maker_order.user_id
        self.side: Side = maker_order.side
        self.price: Decimal = price
        self.size: Decimal = size
        self.taker_time_in_force: TimeInForceType = taker_order.time_in_force
        self.maker_time_in_force: TimeInForceType = maker_order.time_in_force

    def get_seq(self) -> int:
        return self.sequence

    @staticmethod
    def to_json_str(log):
        return json.dumps(vars(log), cls=JsonEncoder)
