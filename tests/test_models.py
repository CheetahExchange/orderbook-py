#!/usr/bin/env python
# encoding: utf-8
from decimal import Decimal
from unittest import TestCase

from models.models import Order
from models.types import TimeInForceType, OrderType, Side, OrderStatus


class UtilsTest(TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_serialize_order(self):
        order = Order(_id=1, created_at=1695783003020967000, product_id="BTC-USD", user_id=1, client_oid="",
                      price=Decimal("20.00"), size=Decimal("3000.00"), funds=Decimal("0.00"),
                      _type=OrderType.OrderTypeLimit,
                      side=Side.SideBuy, time_in_force=TimeInForceType.GoodTillCanceled,
                      status=OrderStatus.OrderStatusNew)
        message = Order.to_json_str(order=order)
        order2 = Order.from_json_str(message)
        self.assertEqual(order.id, order2.id)
        self.assertEqual(order.created_at, order2.created_at)
        self.assertEqual(order.product_id, order2.product_id)
        self.assertEqual(order.user_id, order2.user_id)
        self.assertEqual(order.client_oid, order2.client_oid)
        self.assertEqual(order.price, order2.price)
        self.assertEqual(order.size, order2.size)
        self.assertEqual(order.funds, order2.funds)
        self.assertEqual(order.type, order2.type)
        self.assertEqual(order.side, order2.side)
        self.assertEqual(order.time_in_force, order2.time_in_force)
        self.assertEqual(order.status, order2.status)
