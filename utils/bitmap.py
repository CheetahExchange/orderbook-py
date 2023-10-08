#!/usr/bin/env python
# encoding: utf-8
from typing import List

TA = [1, 2, 4, 8, 16, 32, 64, 128]
TB = [254, 253, 251, 247, 239, 223, 191, 127]


class BitMap(object):
    def __init__(self, length):
        r = 1 if length % 8 != 0 else 0
        self.data = [0] * (length // 8 + r)

    def get(self, i) -> bool:
        return self.data[i // 8] & TA[i % 8] != 0

    def set(self, i, v):
        idx, bit = i // 8, i % 8
        if v:
            self.data[idx] = self.data[idx] | TA[bit]
        else:
            self.data[idx] = self.data[idx] & TB[bit]

    @staticmethod
    def from_data(data: List[int]):
        bitmap = BitMap(0)
        bitmap.data = data
        return bitmap
