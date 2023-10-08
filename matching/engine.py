#!/usr/bin/env python
# encoding: utf-8
import json
from decimal import Decimal
from typing import Optional

from matching.order_book import OrderBookSnapshot, BookOrder
from models.models import OrderException
from models.types import OrderType, Side, TimeInForceType
from utils.utils import JsonEncoder
from utils.window import Window


class Snapshot(object):
    def __init__(self, order_book_snapshot: Optional[OrderBookSnapshot], order_offset: int):
        self.order_book_snapshot: Optional[OrderBookSnapshot] = order_book_snapshot
        self.order_offset: int = order_offset

    @staticmethod
    def to_json_str(snapshot):
        return json.dumps(vars(snapshot), cls=JsonEncoder)

    @staticmethod
    def from_json_str(json_str: str):
        snapshot_dict = json.loads(json_str)
        order_offset = int(snapshot_dict.get("order_offset"))
        order_book_snapshot_dict = snapshot_dict.get("order_book_snapshot")
        if order_book_snapshot_dict is None:
            return Snapshot(order_book_snapshot=None, order_offset=order_offset)

        # parse order_book_snapshot
        product_id = order_book_snapshot_dict.get("product_id")
        orders_list = order_book_snapshot_dict.get("orders")
        trade_seq = int(order_book_snapshot_dict.get("trade_seq"))
        log_seq = int(order_book_snapshot_dict.get("log_seq"))
        order_id_window_dict = order_book_snapshot_dict.get("order_id_window")

        # parse orders
        orders = list()
        orders_list = list() if orders_list is None else orders_list
        for order_dict in orders_list:
            order_id = int(order_dict.get("order_id"))
            user_id = int(order_dict.get("user_id"))
            price = Decimal(order_dict.get("price"))
            size = Decimal(order_dict.get("size"))
            funds = Decimal(order_dict.get("funds"))

            _type = order_dict.get("type")
            if _type == "limit":
                order_type = OrderType.OrderTypeLimit
            elif _type == "market":
                order_type = OrderType.OrderTypeMarket
            else:
                raise OrderException("invalid OrderType")

            side = order_dict.get("side")
            if side == "buy":
                order_side = Side.SideBuy
            elif side == "sell":
                order_side = Side.SideSell
            else:
                raise OrderException("invalid Side")

            time_in_force = order_dict.get("time_in_force")
            if time_in_force == "GTC":
                order_time_in_force = TimeInForceType.GoodTillCanceled
            elif time_in_force == "IOC":
                order_time_in_force = TimeInForceType.ImmediateOrCancel
            elif time_in_force == "GTX":
                order_time_in_force = TimeInForceType.GoodTillCrossing
            elif time_in_force == "FOK":
                order_time_in_force = TimeInForceType.FillOrKill
            else:
                raise OrderException("invalid TimeInForceType")

            book_order = BookOrder(order_id=order_id, user_id=user_id, price=price,
                                   size=size, funds=funds, side=order_side,
                                   _type=order_type, time_in_force=order_time_in_force)
            orders.append(book_order)

        # parse order_id_window
        window_min = int(order_id_window_dict.get("min"))
        window_max = int(order_id_window_dict.get("max"))
        window_cap = int(order_id_window_dict.get("cap"))
        window_bitmap_data = order_id_window_dict.get("bit_map").get("data")
        order_id_window = Window.from_raw(_min=window_min, _max=window_max,
                                          _cap=window_cap, bitmap_data=window_bitmap_data)

        order_book_snapshot = OrderBookSnapshot(product_id=product_id, orders=orders,
                                                trade_seq=trade_seq, log_seq=log_seq,
                                                order_id_window=order_id_window)
        return Snapshot(order_book_snapshot=order_book_snapshot, order_offset=order_offset)
