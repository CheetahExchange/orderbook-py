#!/usr/bin/env python
# encoding: utf-8
from typing import List

from utils.bitmap import BitMap


class WindowException(Exception):
    pass


class Window(object):
    def __init__(self, _min, _max):
        self.min = _min
        self.max = _max
        self.cap = _max - _min
        self.bit_map = BitMap(_max - _min)

    def put(self, val):
        if val <= self.min:
            raise WindowException("expired val {}, current Window [{}-{}]"
                                  .format(val, self.min, self.max))
        elif val > self.max:
            delta = val - self.max
            self.min += delta
            self.max += delta
            self.bit_map.set(val % self.cap, True)
        elif self.bit_map.get(val % self.cap):
            raise WindowException("existed val {}".format(val))
        else:
            self.bit_map.set(val % self.cap, True)

    @staticmethod
    def from_raw(_min: int, _max: int, _cap: int, bitmap_data: List[int]):
        window = Window(_min, _max)
        window.min = _min
        window.max = _max
        window.cap = _cap
        window.bit_map = BitMap.from_data(bitmap_data)
        return window
