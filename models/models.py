#!/usr/bin/env python
# encoding: utf-8
import json
from decimal import Decimal

from models.types import OrderType, Side, TimeInForceType, OrderStatus
from utils.utils import JsonEncoder


class OrderException(Exception):
    pass


class Product(object):
    def __init__(self, _id: str, base_currency: str, quote_currency: str, base_scale: int, quote_scale: int):
        self.id: str = _id
        self.base_currency: str = base_currency
        self.quote_currency: str = quote_currency
        self.base_scale: int = base_scale
        self.quote_scale: int = quote_scale


class Order(object):
    def __init__(self, _id: int, created_at: int, product_id: str, user_id: int, client_oid: str, price: Decimal,
                 size: Decimal, funds: Decimal, _type: OrderType, side: Side, time_in_force: TimeInForceType,
                 status: OrderStatus):
        self.id: int = _id
        self.created_at: int = created_at
        self.product_id: str = product_id
        self.user_id: int = user_id
        self.client_oid: str = client_oid
        self.price: Decimal = price
        self.size: Decimal = size
        self.funds: Decimal = funds
        self.type: OrderType = _type
        self.side: Side = side
        self.time_in_force: TimeInForceType = time_in_force
        self.status: OrderStatus = status

    @staticmethod
    def to_json_str(order):
        return json.dumps(vars(order), cls=JsonEncoder)

    @staticmethod
    def from_json_str(json_str: str):
        order_dict = json.loads(json_str)

        order_id = int(order_dict.get("id"))
        order_created_at = int(order_dict.get("created_at"))
        order_product_id = order_dict.get("product_id")
        order_user_id = int(order_dict.get("user_id"))
        order_client_oid = order_dict.get("client_oid")
        order_price = Decimal(order_dict.get("price"))
        order_size = Decimal(order_dict.get("size"))
        order_funds = Decimal(order_dict.get("funds"))

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

        status = order_dict.get("status")
        if status == "new":
            order_status = OrderStatus.OrderStatusNew
        elif status == "open":
            order_status = OrderStatus.OrderStatusOpen
        elif status == "cancelling":
            order_status = OrderStatus.OrderStatusCancelling
        elif status == "cancelled":
            order_status = OrderStatus.OrderStatusCancelled
        elif status == "partial":
            order_status = OrderStatus.OrderStatusPartial
        elif status == "filled":
            order_status = OrderStatus.OrderStatusFilled
        else:
            raise OrderException("invalid OrderStatus")

        return Order(_id=order_id, created_at=order_created_at, product_id=order_product_id, user_id=order_user_id,
                     client_oid=order_client_oid, price=order_price, size=order_size, funds=order_funds,
                     _type=order_type, side=order_side, time_in_force=order_time_in_force, status=order_status)
