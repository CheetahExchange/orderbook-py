from decimal import Decimal
from typing import List, Dict

from models.models import Product
from models.types import Side, OrderType, TimeInForceType
from utils.window import Window

ORDER_ID_WINDOW_CAP = 10000


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
    def __init__(self, product_id: str, orders: List, trade_seq: int, log_seq: int, order_id_window: Window):
        self.product_id: str = product_id
        self.orders: List[BookOrder] = orders
        self.trade_seq: int = trade_seq
        self.log_seq: int = log_seq
        self.order_id_window: Window = order_id_window


class Depth(object):
    def __init__(self):
        self.orders: Dict[int, BookOrder] = dict()
        self.queue = None


class OrderBook(object):
    def __init__(self, product: Product, trade_seq: int, log_seq: int):
        self.product: Product = product
        self.depths: Dict[Side, Depth] = dict()
        self.trade_seq = trade_seq
        self.log_seq = log_seq
        self.order_id_window = Window(0, ORDER_ID_WINDOW_CAP)
