from decimal import Decimal
from typing import List, Dict

from models.models import Product
from models.types import Side, OrderType, TimeInForceType
from utils.window import Window
from pytreemap import TreeMap

ORDER_ID_WINDOW_CAP = 10000


class DepthException(Exception):
    pass


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


class PriceOrderIdKey(object):
    def __init__(self, price: Decimal, order_id: int):
        self.price = price
        self.order_id = order_id


def price_order_id_key_asc_comparator(l: PriceOrderIdKey, r: PriceOrderIdKey):
    if l.price < r.price:
        return -1
    elif l.price > r.price:
        return 1
    else:
        if l.order_id < r.order_id:
            return -1
        elif l.order_id > r.order_id:
            return 1
        else:
            return 0


def price_order_id_key_desc_comparator(l: PriceOrderIdKey, r: PriceOrderIdKey):
    if l.price < r.price:
        return 1
    elif l.price > r.price:
        return -1
    else:
        if l.order_id < r.order_id:
            return -1
        elif l.order_id > r.order_id:
            return 1
        else:
            return 0


class Depth(object):
    def __init__(self):
        self.orders: Dict[int, BookOrder] = dict()
        self.queue: TreeMap = TreeMap()

    def add(self, order: BookOrder):
        self.orders[order.order_id] = order
        self.queue[PriceOrderIdKey(order.price, order.order_id)] = order.order_id

    def decr_size(self, order_id: int, size: Decimal):
        order = self.orders.get(order_id)
        if order is None:
            raise DepthException("order {} not found on book".format(order_id))

        if order.size < size:
            raise DepthException("order {} Size {} less than {}".format(order_id, order.size, size))

        order.size -= size
        self.orders[order_id] = order
        if order.size.is_zero():
            del self.orders[order_id]
            self.queue.remove(PriceOrderIdKey(order.price, order.order_id))


class OrderBook(object):
    def __init__(self, product: Product, trade_seq: int, log_seq: int):
        asks = Depth()
        asks.queue = TreeMap(price_order_id_key_asc_comparator)

        bids = Depth()
        bids.queue = TreeMap(price_order_id_key_desc_comparator)

        self.product: Product = product
        self.depths: Dict[Side, Depth] = dict()
        self.trade_seq = trade_seq
        self.log_seq = log_seq
        self.order_id_window = Window(0, ORDER_ID_WINDOW_CAP)

        self.depths[Side.SideBuy] = bids
        self.depths[Side.SideSell] = asks
