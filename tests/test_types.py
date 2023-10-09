#!/usr/bin/env python
# encoding: utf-8
from unittest import TestCase

from models.types import Side


class UtilsTest(TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_side_opposite(self):
        self.assertEqual(Side.SideBuy.opposite(), Side.SideSell)
        self.assertEqual(Side.SideSell.opposite(), Side.SideBuy)
