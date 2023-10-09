#!/usr/bin/env python
# encoding: utf-8
from decimal import Decimal
from unittest import TestCase

from utils.utils import truncate_decimal


class UtilsTest(TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_truncate_decimal(self):
        d = truncate_decimal(Decimal("1.234567"), 4)
        self.assertEqual(d, Decimal("1.2345"))
