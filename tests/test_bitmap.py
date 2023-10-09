#!/usr/bin/env python
# encoding: utf-8
from unittest import TestCase

from utils.bitmap import BitMap


class UtilsTest(TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_len(self):
        bitmap = BitMap(100)
        self.assertEqual(len(bitmap.data), 13)

    def test_get_set(self):
        bitmap = BitMap(100)

        b = bitmap.get(3)
        self.assertEqual(b, False)

        bitmap.set(3, True)
        b = bitmap.get(3)
        self.assertEqual(b, True)

        bitmap.set(3, False)
        b = bitmap.get(3)
        self.assertEqual(b, False)
