#!/usr/bin/env python
# encoding: utf-8

from typing import Optional

from matching.order_book import OrderBookSnapshot


class Snapshot(object):
    def __init__(self, order_book_snapshot, order_offset: int):
        self.order_book_snapshot: Optional[OrderBookSnapshot] = order_book_snapshot
        self.order_offset: int = order_offset
