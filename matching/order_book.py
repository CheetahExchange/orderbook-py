import sys
from decimal import Decimal
from typing import List, Dict

from models.models import Product, Order
from models.types import Side, OrderType, TimeInForceType
from utils.utils import truncate_decimal
from utils.window import Window
from pytreemap import TreeMap

ORDER_ID_WINDOW_CAP = 10000


class DepthException(Exception):
    pass


class BookOrder(object):
    def __init__(self, order: Order):
        self.order_id: int = order.id
        self.user_id: int = order.user_id
        self.price: Decimal = order.price
        self.size: Decimal = order.size
        self.funds: Decimal = order.funds
        self.side: Side = order.side
        self.type: OrderType = order.type
        self.time_in_force: TimeInForceType = order.time_in_force


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
        asks.queue = TreeMap(comparator=price_order_id_key_asc_comparator)

        bids = Depth()
        bids.queue = TreeMap(comparator=price_order_id_key_desc_comparator)

        self.product: Product = product
        self.depths: Dict[Side, Depth] = dict()
        self.trade_seq = trade_seq
        self.log_seq = log_seq
        self.order_id_window = Window(0, ORDER_ID_WINDOW_CAP)

        self.depths[Side.SideBuy] = bids
        self.depths[Side.SideSell] = asks

    def is_order_will_not_match(self, order: Order) -> bool:
        taker_order = BookOrder(order)
        if taker_order.type == OrderType.OrderTypeMarket:
            if taker_order.side == Side.SideBuy:
                taker_order.price = Decimal(sys.float_info.max)
            else:
                taker_order.price = Decimal(0)

        maker_depth = self.depths[taker_order.side.opposite()]

        if taker_order.side == Side.SideBuy:
            e = maker_depth.queue.first_entry()
            k, v = e.get_key(), e.get_value()
            if k is None or v is None:
                return True

            maker_order: BookOrder = maker_depth.orders[v]
            if taker_order.price.lt(maker_order.price):
                return True
        elif taker_order.side == Side.SideSell:
            e = maker_depth.queue.first_entry()
            k, v = e.get_key(), e.get_value()
            if k is None or v is None:
                return True

            maker_order: BookOrder = maker_depth.orders[v]
            if taker_order.price > maker_order.price:
                return True

        return False

    def is_order_will_full_match(self, order: Order) -> bool:
        taker_order = BookOrder(order)

        if taker_order.type == OrderType.OrderTypeMarket:
            if taker_order.side == Side.SideBuy:
                taker_order.price = Decimal(sys.float_info.max)
            else:
                taker_order.price = Decimal(0)

        maker_depth = self.depths[taker_order.side.opposite()]
        for e in iter(maker_depth.queue):
            maker_order = maker_depth.orders[e.get_value()]

            # check whether there is price crossing between the taker and the maker
            if (taker_order.side == Side.SideBuy and taker_order.price < maker_order.price) or (
                    taker_order.side == Side.SideSell and taker_order.price > maker_order.price):
                break

            price = maker_order.price

            if taker_order.type == OrderType.OrderTypeLimit or (
                    taker_order.type == OrderType.OrderTypeMarket and taker_order.side == Side.SideSell):
                if taker_order.size.is_zero():
                    break

                # Take the minimum size of taker and maker as trade size
                size = taker_order.size.min(maker_order.size)
                # adjust the size of taker order
                taker_order.size = taker_order.size - size
            elif taker_order.type == OrderType.OrderTypeMarket and taker_order.size == Side.SideBuy:
                if taker_order.funds.is_zero():
                    break

                taker_size = truncate_decimal(taker_order.funds / price, self.product.base_scale)
                if taker_size.is_zero():
                    break

                # Take the minimum size of taker and maker as trade size
                size = taker_size.min(maker_order.size)
                funds = size * price

                # adjust the funds of taker order
                taker_order.funds = taker_order.funds - funds

        if taker_order.type == OrderType.OrderTypeLimit and taker_order.size > 0:
            return False

        return True
