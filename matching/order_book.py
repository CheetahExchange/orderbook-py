from decimal import Decimal
from typing import List

from models.types import Side, OrderType, TimeInForceType
from utils.window import Window


class BookOrder(object):
    def __init__(self, order_id: int, user_id: int, price: Decimal, size: Decimal, funds: Decimal,
                 side: Side, _type: OrderType, time_in_force: TimeInForceType):
        self.order_id: int = order_id
        self.user_id: int = user_id
        self.price: Decimal = price
        self.size: Decimal = size
        self.funds: Decimal = funds
        self.side: Side = side
        self.type: OrderType = _type
        self.time_in_force: TimeInForceType = time_in_force


class OrderBookSnapshot(object):
    def __init__(self, product_id, orders, trade_seq, log_seq, order_id_window):
        self.product_id: str = product_id
        self.orders: List[BookOrder] = orders
        self.trade_seq: int = trade_seq
        self.log_seq: int = log_seq
        self.order_id_window: Window = order_id_window
