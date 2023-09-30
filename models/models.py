from decimal import Decimal

from models.types import OrderType, Side, TimeInForceType, OrderStatus


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
