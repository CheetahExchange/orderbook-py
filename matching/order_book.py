#!/usr/bin/env python
# encoding: utf-8
import logging
import sys
import copy
from decimal import Decimal
from typing import List, Dict

from matching.log import MatchLog, DoneLog, OpenLog
from models.models import Product, Order
from models.types import Side, OrderType, TimeInForceType, DoneReason
from utils.utils import truncate_decimal
from utils.window import Window, WindowException
from pytreemap import TreeMap

ORDER_ID_WINDOW_CAP: int = 10000


class DepthException(Exception):
    pass


class BookOrder(object):
    def __init__(self, order_id: int, user_id: int, price: Decimal,
                 size: Decimal, funds: Decimal, side: Side, _type: OrderType,
                 time_in_force: TimeInForceType):
        self.order_id: int = order_id
        self.user_id: int = user_id
        self.price: Decimal = price
        self.size: Decimal = size
        self.funds: Decimal = funds
        self.side: Side = side
        self.type: OrderType = _type
        self.time_in_force: TimeInForceType = time_in_force

    @staticmethod
    def from_order(order: Order):
        return BookOrder(order_id=order.id, user_id=order.user_id, price=order.price,
                         size=order.size, funds=order.funds, side=order.side,
                         _type=order.type, time_in_force=order.time_in_force)


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
        taker_order = BookOrder.from_order(order)
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
        taker_order = BookOrder.from_order(order)

        if taker_order.type == OrderType.OrderTypeMarket:
            if taker_order.side == Side.SideBuy:
                taker_order.price = Decimal(sys.float_info.max)
            else:
                taker_order.price = Decimal(0)

        maker_depth = self.depths[taker_order.side.opposite()]
        for v in maker_depth.queue.values():
            maker_order = maker_depth.orders[v]

            # check whether there is price crossing between the taker and the maker
            if (taker_order.side == Side.SideBuy and taker_order.price < maker_order.price) or (
                    taker_order.side == Side.SideSell and taker_order.price > maker_order.price):
                break

            price = maker_order.price
            size = Decimal(0)

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

    def apply_order(self, order: Order) -> list:
        logs = list()

        try:
            self.order_id_window.put(order.id)
        except WindowException as ex:
            logging.error("{}".format(str(ex)))
            return logs

        taker_order = BookOrder.from_order(order)

        if taker_order.type == OrderType.OrderTypeMarket:
            if taker_order.side == Side.SideBuy:
                taker_order.price = Decimal(sys.float_info.max)
            else:
                taker_order.price = Decimal(0)

        maker_depth = copy.deepcopy(self.depths[taker_order.side.opposite()])
        for v in maker_depth.queue.values():
            maker_order = maker_depth.orders[v]

            # check whether there is price crossing between the taker and the maker
            if (taker_order.side == Side.SideBuy and taker_order.price < maker_order.price) or (
                    taker_order.side == Side.SideSell and taker_order.price > maker_order.price):
                break

            price = maker_order.price
            size = Decimal(0)

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

            try:
                self.depths[taker_order.side.opposite()].decr_size(maker_order.order_id, size)
                maker_order.size -= size
            except DepthException as ex:
                logging.fatal("{}".format(ex))
                sys.exit()

            # matched, write a log
            match_log = MatchLog(self.next_log_seq(), self.product.id, self.net_trade_seq(), taker_order, maker_order,
                                 price, size)
            logging.info("MatchLog: {}".format(MatchLog.to_json_str(match_log)))
            logs.append(match_log)

            # maker is filled
            if maker_order.size.is_zero():
                done_log = DoneLog(self.next_log_seq(), self.product.id, maker_order, maker_order.size,
                                   DoneReason.DoneReasonFilled)
                logging.info("DoneLog: {}".format(DoneLog.to_json_str(done_log)))
                logs.append(done_log)

        if taker_order.type == OrderType.OrderTypeLimit and taker_order.size > 0:
            self.depths[taker_order.side].add(taker_order)
            open_log = OpenLog(self.next_log_seq(), self.product.id, taker_order)
            logging.info("OpenLog: {}".format(OpenLog.to_json_str(open_log)))
            logs.append(open_log)
        else:
            remaining_size = taker_order.size
            reason = DoneReason.DoneReasonFilled

            if taker_order.type == OrderType.OrderTypeMarket:
                taker_order.price = Decimal(0)
                remaining_size = Decimal(0)
                if (taker_order.side == Side.SideSell and taker_order.size > 0) or (
                        taker_order.side == Side.SideBuy and taker_order.funds > 0):
                    reason = DoneReason.DoneReasonCancelled

            done_log = DoneLog(self.next_log_seq(), self.product.id, taker_order, remaining_size, reason)
            logging.info("DoneLog: {}".format(DoneLog.to_json_str(done_log)))
            logs.append(done_log)

        return logs

    def cancel_order(self, order: Order) -> list:
        logs = list()

        try:
            self.order_id_window.put(order.id)
        except WindowException as ex:
            pass

        book_order = self.depths[order.side].orders.get(order.id)
        if book_order is None:
            return logs

        remaining_size = book_order.size
        try:
            self.depths[order.side].decr_size(order.id, book_order.size)
        except DepthException as ex:
            logging.fatal("{}".format(ex))
            sys.exit()

        done_log = DoneLog(self.next_log_seq(), self.product.id, book_order, remaining_size,
                           DoneReason.DoneReasonCancelled)
        logging.info("DoneLog: {}".format(DoneLog.to_json_str(done_log)))
        logs.append(done_log)
        return logs

    def nullify_order(self, order: Order) -> list:
        logs = list()

        try:
            self.order_id_window.put(order.id)
        except WindowException as ex:
            pass

        book_order = BookOrder.from_order(order)
        done_log = DoneLog(self.next_log_seq(), self.product.id, book_order, order.size,
                           DoneReason.DoneReasonCancelled)
        logging.info("DoneLog: {}".format(DoneLog.to_json_str(done_log)))
        logs.append(done_log)
        return logs

    def snapshot(self) -> OrderBookSnapshot:
        snapshot = OrderBookSnapshot(self.product.id, list(), self.trade_seq, self.log_seq, self.order_id_window)
        for order in self.depths[Side.SideSell].orders.values():
            snapshot.orders.append(order)
        for order in self.depths[Side.SideBuy].orders.values():
            snapshot.orders.append(order)
        return snapshot

    def restore(self, snapshot: OrderBookSnapshot):
        self.log_seq = snapshot.log_seq
        self.trade_seq = snapshot.trade_seq
        self.order_id_window = snapshot.order_id_window
        if self.order_id_window.cap == 0:
            self.order_id_window = Window(0, ORDER_ID_WINDOW_CAP)

        for order in snapshot.orders:
            self.depths[order.side].add(order)

    def next_log_seq(self) -> int:
        self.log_seq += 1
        return self.log_seq

    def net_trade_seq(self) -> int:
        self.trade_seq += 1
        return self.trade_seq
