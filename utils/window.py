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
        if val < self.min:
            raise WindowException("expired val {}, current Window [{}-{}]"
                                  .format(val, self.min, self.max))
        elif val >= self.max:
            delta = val - self.max + 1
            _range = self.cap if delta > self.cap else delta
            for i in range(_range):
                self.bit_map.set((self.min + i) % self.cap, False)
            self.min += delta
            self.max += delta
            self.bit_map.set(val % self.cap, True)
        elif self.bit_map.get(val % self.cap):
            raise WindowException("existed val {}".format(val))
        else:
            self.bit_map.set(val % self.cap, True)

    def contains(self, val):
        if val < self.min or val >= self.max:
            return False
        return self.bit_map.get(val % self.cap)

    @staticmethod
    def from_raw(_min: int, _max: int, _cap: int, bitmap_data: List[int]):
        assert _cap == _max - _min and len(bitmap_data) == (_cap + 7) // 8
        window = Window(_min, _max)
        window.min = _min
        window.max = _max
        window.cap = _cap
        window.bit_map = BitMap.from_data(bitmap_data)
        return window
