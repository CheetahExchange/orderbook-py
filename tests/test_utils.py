#!/usr/bin/env python
# encoding: utf-8
from decimal import Decimal
from unittest import TestCase

from models.models import Order
from models.types import OrderType, Side, TimeInForceType, OrderStatus
from utils.utils import truncate_decimal


class UtilsTest(TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_truncate_decimal(self):
        d = truncate_decimal(Decimal("1.234567"), 4)
        self.assertEqual(d, Decimal("1.2345"))

    def test_serialize_order(self):
        order = Order(_id=1, created_at=1695783003020967000, product_id="BTC-USD", user_id=1, client_oid="",
                      price=Decimal("20.00"), size=Decimal("3000.00"), funds=Decimal("0.00"),
                      _type=OrderType.OrderTypeLimit,
                      side=Side.SideBuy, time_in_force=TimeInForceType.GoodTillCanceled,
                      status=OrderStatus.OrderStatusNew)
        message = Order.to_json_str(order=order)
        order_dict = Order.from_json_str(message)
        print(message)
        print(order_dict)
