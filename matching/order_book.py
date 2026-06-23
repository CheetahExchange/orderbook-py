#!/usr/bin/env python
# encoding: utf-8
import logging
import sys
from decimal import Decimal
from typing import List, Dict
import copy

_MAX_PRICE = Decimal(sys.float_info.max)

from matching.log import MatchLog, DoneLog, OpenLog
from models.models import Product, Order, _safe_decimal
from models.types import Side, OrderType, TimeInForceType, DoneReason
from utils.utils import truncate_decimal, normalize_price, normalize_size
from utils.time_window import TimeWindow, TimeWindowException, TimeWindowSnapshot, current_time_since_snowflake_epoch
from pytreemap import TreeMap


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

    def to_dict(self) -> dict:
        return {
            "order_id": self.order_id,
            "user_id": self.user_id,
            "price": str(self.price),
            "size": str(self.size),
            "funds": str(self.funds),
            "type": self.type.value,
            "side": self.side.value,
            "time_in_force": self.time_in_force.value,
        }

    @staticmethod
    def from_dict(d: dict):
        _type = d.get("type")
        if _type == "limit":
            order_type = OrderType.OrderTypeLimit
        elif _type == "market":
            order_type = OrderType.OrderTypeMarket
        else:
            raise DepthException("invalid OrderType")

        side = d.get("side")
        if side == "buy":
            order_side = Side.SideBuy
        elif side == "sell":
            order_side = Side.SideSell
        else:
            raise DepthException("invalid Side")

        time_in_force = d.get("time_in_force")
        if time_in_force == "GTC":
            order_time_in_force = TimeInForceType.GoodTillCanceled
        elif time_in_force == "IOC":
            order_time_in_force = TimeInForceType.ImmediateOrCancel
        elif time_in_force == "GTX":
            order_time_in_force = TimeInForceType.GoodTillCrossing
        elif time_in_force == "FOK":
            order_time_in_force = TimeInForceType.FillOrKill
        else:
            raise DepthException("invalid TimeInForceType")

        order_id = int(d.get("order_id"))
        user_id = int(d.get("user_id"))
        if order_id < 0 or user_id < 0:
            raise DepthException("invalid order_id or user_id: must be non-negative")

        return BookOrder(
            order_id=order_id,
            user_id=user_id,
            price=_safe_decimal(d.get("price"), "price"),
            size=_safe_decimal(d.get("size"), "size"),
            funds=_safe_decimal(d.get("funds"), "funds"),
            side=order_side,
            _type=order_type,
            time_in_force=order_time_in_force,
        )


class OrderBookSnapshot(object):
    def __init__(self, product_id: str, orders: List, trade_seq: int, log_seq: int,
                 time_window: TimeWindowSnapshot, last_trade_price: Decimal = Decimal(0)):
        self.product_id: str = product_id
        self.orders: List[BookOrder] = orders
        self.trade_seq: int = trade_seq
        self.log_seq: int = log_seq
        self.time_window: TimeWindowSnapshot = time_window
        self.last_trade_price: Decimal = last_trade_price

    def to_dict(self) -> dict:
        return {
            "product_id": self.product_id,
            "orders": [o.to_dict() for o in self.orders],
            "trade_seq": self.trade_seq,
            "log_seq": self.log_seq,
            "time_window": self.time_window.to_dict(),
            "last_trade_price": str(self.last_trade_price),
        }

    @staticmethod
    def from_dict(d: dict):
        tw_dict = d.get("time_window")
        time_window = TimeWindowSnapshot.from_dict(tw_dict) if tw_dict else TimeWindowSnapshot()

        orders_list = d.get("orders") or []
        orders = [BookOrder.from_dict(o) for o in orders_list]

        return OrderBookSnapshot(
            product_id=d.get("product_id"),
            orders=orders,
            trade_seq=int(d.get("trade_seq", 0)),
            log_seq=int(d.get("log_seq", 0)),
            time_window=time_window,
            last_trade_price=Decimal(d.get("last_trade_price", "0")),
        )


class PriceOrderIdKey(object):
    def __init__(self, price: Decimal, order_id: int):
        self.price = price
        self.order_id = order_id

    def __eq__(self, other):
        if not isinstance(other, PriceOrderIdKey):
            return NotImplemented
        return self.price == other.price and self.order_id == other.order_id

    def __hash__(self):
        return hash((self.price, self.order_id))


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
        # all orders
        self.orders: Dict[int, BookOrder] = dict()
        # price first, time first order queue for order match
        # priceOrderIdKey -> orderId
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
        self.time_window = TimeWindow()
        self.last_trade_price = Decimal(0)

        self.depths[Side.SideBuy] = bids
        self.depths[Side.SideSell] = asks

    def is_order_will_not_match(self, order: Order) -> bool:
        taker_order = BookOrder.from_order(order)

        # If it's a Market-Buy order, set price to infinite high, and if it's market-sell,
        # set price to zero, which ensures that prices will cross.
        if taker_order.type == OrderType.OrderTypeMarket:
            if taker_order.side == Side.SideBuy:
                taker_order.price = _MAX_PRICE
            else:
                taker_order.price = Decimal(0)

        maker_depth = self.depths[taker_order.side.opposite()]

        if len(maker_depth.queue) == 0:
            return True

        if taker_order.side == Side.SideBuy:
            v = maker_depth.queue.first_entry().get_value()
            if v is None:
                return True
            maker_order: BookOrder = maker_depth.orders[v]
            if taker_order.price < maker_order.price:
                return True
        elif taker_order.side == Side.SideSell:
            v = maker_depth.queue.first_entry().get_value()
            if v is None:
                return True
            maker_order: BookOrder = maker_depth.orders[v]
            if taker_order.price > maker_order.price:
                return True

        return False

    def is_order_will_full_match(self, order: Order) -> bool:
        taker_order = BookOrder.from_order(order)

        # If it's a Market-Buy order, set price to infinite high, and if it's market-sell,
        # set price to zero, which ensures that prices will cross.
        if taker_order.type == OrderType.OrderTypeMarket:
            if taker_order.side == Side.SideBuy:
                taker_order.price = _MAX_PRICE
            else:
                taker_order.price = Decimal(0)

        maker_depth = self.depths[taker_order.side.opposite()]
        for v in maker_depth.queue.values():
            maker_order = maker_depth.orders.get(v)
            if maker_order is None:
                continue

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
            elif taker_order.type == OrderType.OrderTypeMarket and taker_order.side == Side.SideBuy:
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

        # prevent orders from being submitted repeatedly to the matching engine
        try:
            now_time = current_time_since_snowflake_epoch()
            self.time_window.put(order.id, now_time)
        except TimeWindowException as ex:
            # Check if this is an "expired" order (window has moved past this order's time)
            # This can happen when Kafka replays old messages after a restart or rebalance.
            # If the order is not in the order book, it was never processed or already completed,
            # so we should process it anyway.
            found_in_buy = order.id in self.depths[Side.SideBuy].orders
            found_in_sell = order.id in self.depths[Side.SideSell].orders

            if found_in_buy or found_in_sell:
                logging.info("expired order {} already in order book, skipping".format(order.id))
                return logs

            logging.info("expired order {} not in order book, processing anyway".format(order.id))

        taker_order = BookOrder.from_order(order)

        # Normalize price and size to product scales
        taker_order.price = normalize_price(taker_order.price, self.product.quote_scale)
        taker_order.size = normalize_size(taker_order.size, self.product.base_scale)

        # If it's a Market-Buy order, set price to infinite high, and if it's market-sell,
        # set price to zero, which ensures that prices will cross.
        if taker_order.type == OrderType.OrderTypeMarket:
            if taker_order.side == Side.SideBuy:
                taker_order.price = _MAX_PRICE
            else:
                taker_order.price = Decimal(0)

        maker_depth = self.depths[taker_order.side.opposite()]
        # Collect order IDs first to avoid modifying dict while iterating
        order_ids = list(maker_depth.queue.values())

        for order_id in order_ids:
            maker_order = maker_depth.orders.get(order_id)
            if maker_order is None:
                continue
            # Clone maker_order to avoid stale reference after decr_size modifies the dict
            maker_order = BookOrder(
                order_id=maker_order.order_id, user_id=maker_order.user_id, price=maker_order.price,
                size=maker_order.size, funds=maker_order.funds, side=maker_order.side,
                _type=maker_order.type, time_in_force=maker_order.time_in_force)

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
            elif taker_order.type == OrderType.OrderTypeMarket and taker_order.side == Side.SideBuy:
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

            self.last_trade_price = maker_order.price

            # maker is filled
            if maker_order.size.is_zero():
                done_log = DoneLog(self.next_log_seq(), self.product.id, maker_order, maker_order.size,
                                   DoneReason.DoneReasonFilled)
                logging.info("DoneLog: {}".format(DoneLog.to_json_str(done_log)))
                logs.append(done_log)

            # check if taker is exhausted after this match
            if taker_order.type == OrderType.OrderTypeLimit:
                if taker_order.size.is_zero():
                    break
            elif taker_order.type == OrderType.OrderTypeMarket:
                if taker_order.funds.is_zero():
                    break

        if taker_order.type == OrderType.OrderTypeLimit and taker_order.size > 0:
            # If taker has an uncompleted size, put taker in orderBook
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

        if order.side not in self.depths:
            return logs

        try:
            now_time = current_time_since_snowflake_epoch()
            self.time_window.put(order.id, now_time)
        except TimeWindowException as ex:
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
            now_time = current_time_since_snowflake_epoch()
            self.time_window.put(order.id, now_time)
        except TimeWindowException as ex:
            pass

        book_order = BookOrder.from_order(order)
        done_log = DoneLog(self.next_log_seq(), self.product.id, book_order, order.size,
                           DoneReason.DoneReasonCancelled)
        logging.info("DoneLog: {}".format(DoneLog.to_json_str(done_log)))
        logs.append(done_log)
        return logs

    def snapshot(self) -> OrderBookSnapshot:
        snapshot = OrderBookSnapshot(self.product.id, list(), self.trade_seq, self.log_seq,
                                    self.time_window.snapshot(), self.last_trade_price)
        for order in self.depths[Side.SideSell].orders.values():
            snapshot.orders.append(copy.copy(order))
        for order in self.depths[Side.SideBuy].orders.values():
            snapshot.orders.append(copy.copy(order))
        return snapshot

    def restore(self, snapshot: OrderBookSnapshot):
        self.log_seq = snapshot.log_seq
        self.trade_seq = snapshot.trade_seq
        self.last_trade_price = snapshot.last_trade_price
        self.time_window.restore(snapshot.time_window)

        for order in snapshot.orders:
            self.depths[order.side].add(order)

    def cleanup_time_window(self):
        now_time = current_time_since_snowflake_epoch()
        self.time_window.cleanup(now_time)

    def next_log_seq(self) -> int:
        self.log_seq += 1
        return self.log_seq

    def net_trade_seq(self) -> int:
        self.trade_seq += 1
        return self.trade_seq
