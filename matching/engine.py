#!/usr/bin/env python
# encoding: utf-8
import asyncio
import json
import logging
import sys
from asyncio import Queue, wait, FIRST_COMPLETED, wait_for, gather
from decimal import Decimal
from typing import Optional, List

from matching.kafka_log import KafkaLogStore
from matching.kafka_order import KafkaOrderReader
from matching.log import Log
from matching.order_book import OrderBookSnapshot, BookOrder, OrderBook
from models.models import OrderException, Product, Order
from models.types import OrderType, Side, TimeInForceType, OrderStatus
from utils.utils import JsonEncoder
from utils.window import Window


class Snapshot(object):
    def __init__(self, order_book_snapshot: Optional[OrderBookSnapshot], order_offset: int):
        self.order_book_snapshot: Optional[OrderBookSnapshot] = order_book_snapshot
        self.order_offset: int = order_offset

    @staticmethod
    def to_json_str(snapshot):
        return json.dumps(vars(snapshot), cls=JsonEncoder)

    @staticmethod
    def from_json_str(json_str: str):
        snapshot_dict = json.loads(json_str)
        order_offset = int(snapshot_dict.get("order_offset"))
        order_book_snapshot_dict = snapshot_dict.get("order_book_snapshot")
        if order_book_snapshot_dict is None:
            return Snapshot(order_book_snapshot=None, order_offset=order_offset)

        # parse order_book_snapshot
        product_id = order_book_snapshot_dict.get("product_id")
        orders_list = order_book_snapshot_dict.get("orders")
        trade_seq = int(order_book_snapshot_dict.get("trade_seq"))
        log_seq = int(order_book_snapshot_dict.get("log_seq"))
        order_id_window_dict = order_book_snapshot_dict.get("order_id_window")

        # parse orders
        orders = list()
        orders_list = list() if orders_list is None else orders_list
        for order_dict in orders_list:
            order_id = int(order_dict.get("order_id"))
            user_id = int(order_dict.get("user_id"))
            price = Decimal(order_dict.get("price"))
            size = Decimal(order_dict.get("size"))
            funds = Decimal(order_dict.get("funds"))

            _type = order_dict.get("type")
            if _type == "limit":
                order_type = OrderType.OrderTypeLimit
            elif _type == "market":
                order_type = OrderType.OrderTypeMarket
            else:
                raise OrderException("invalid OrderType")

            side = order_dict.get("side")
            if side == "buy":
                order_side = Side.SideBuy
            elif side == "sell":
                order_side = Side.SideSell
            else:
                raise OrderException("invalid Side")

            time_in_force = order_dict.get("time_in_force")
            if time_in_force == "GTC":
                order_time_in_force = TimeInForceType.GoodTillCanceled
            elif time_in_force == "IOC":
                order_time_in_force = TimeInForceType.ImmediateOrCancel
            elif time_in_force == "GTX":
                order_time_in_force = TimeInForceType.GoodTillCrossing
            elif time_in_force == "FOK":
                order_time_in_force = TimeInForceType.FillOrKill
            else:
                raise OrderException("invalid TimeInForceType")

            book_order = BookOrder(order_id=order_id, user_id=user_id, price=price,
                                   size=size, funds=funds, side=order_side,
                                   _type=order_type, time_in_force=order_time_in_force)
            orders.append(book_order)

        # parse order_id_window
        window_min = int(order_id_window_dict.get("min"))
        window_max = int(order_id_window_dict.get("max"))
        window_cap = int(order_id_window_dict.get("cap"))
        window_bitmap_data = order_id_window_dict.get("bit_map").get("data")
        order_id_window = Window.from_raw(_min=window_min, _max=window_max,
                                          _cap=window_cap, bitmap_data=window_bitmap_data)

        order_book_snapshot = OrderBookSnapshot(product_id=product_id, orders=orders,
                                                trade_seq=trade_seq, log_seq=log_seq,
                                                order_id_window=order_id_window)
        return Snapshot(order_book_snapshot=order_book_snapshot, order_offset=order_offset)


class OffsetOrder(object):
    def __init__(self, offset: int, order: Order):
        self.offset: int = offset
        self.order: Order = order


class Engine(object):
    def __init__(self, product: Product, order_reader: KafkaOrderReader, log_store: KafkaLogStore,
                 snapshot_store):
        self.product_id: str = product.id
        self.order_book: OrderBook = OrderBook(product, 0, 0)
        self.order_reader: KafkaOrderReader = order_reader
        self.order_offset: int = 0
        self.log_store: KafkaLogStore = log_store
        self.snapshot_store = snapshot_store
        self.log_chan: Queue = Queue(maxsize=10000)
        self.order_chan: Queue = Queue(maxsize=10000)
        self.snapshot_req_chan: Queue = Queue(maxsize=32)
        self.snapshot_approve_req_chan: Queue = Queue(maxsize=32)
        self.snapshot_chan: Queue = Queue(maxsize=32)

    def restore(self, snapshot: Snapshot):
        self.order_offset = snapshot.order_offset
        self.order_book.restore(snapshot=snapshot.order_book_snapshot)

    async def initialize_snapshot(self):
        snapshot = await self.snapshot_store.get_latest()
        if snapshot is not None:
            self.restore(snapshot=snapshot)

    async def start(self):
        task1 = asyncio.create_task(self.run_fetcher())
        task2 = asyncio.create_task(self.run_applier())
        task3 = asyncio.create_task(self.run_committer())
        task4 = asyncio.create_task(self.run_snapshots())
        await gather(task1, task2, task3, task4)

    async def run_fetcher(self):
        offset = self.order_offset
        if offset > 0:
            offset += 1

        try:
            self.order_reader.set_offset(offset)
        except Exception as ex:
            logging.fatal("set order reader offset error: {}".format(ex))
            sys.exit()

        while True:
            try:
                offset, order = await self.order_reader.fetch_order()
                logging.info("fetch_order: {}".format(Order.to_json_str(order)))
                await self.order_chan.put(OffsetOrder(offset=offset, order=order))
            except Exception as ex:
                logging.error("{}".format(str(ex)))

    async def run_applier(self):
        order_offset: int = 0

        while True:
            task1 = self.order_chan.get()
            task2 = self.snapshot_req_chan.get()
            done, pending = await wait({task1, task2}, return_when=FIRST_COMPLETED)
            for t in done:
                result = t.result()
                if isinstance(result, OffsetOrder):
                    offset_order: OffsetOrder = result
                    logs: List[Log] = list()
                    if offset_order.order.status == OrderStatus.OrderStatusCancelling:
                        logs = self.order_book.cancel_order(offset_order.order)
                    else:
                        if offset_order.order.time_in_force == TimeInForceType.ImmediateOrCancel:
                            logs = self.order_book.apply_order(offset_order.order)
                            ioc_logs = self.order_book.cancel_order(offset_order.order)
                            if len(ioc_logs) != 0:
                                logs.extend(ioc_logs)
                        elif offset_order.order.time_in_force == TimeInForceType.GoodTillCrossing:
                            if self.order_book.is_order_will_not_match(offset_order.order):
                                logs = self.order_book.apply_order(offset_order.order)
                            else:
                                logs = self.order_book.nullify_order(offset_order.order)
                        elif offset_order.order.time_in_force == TimeInForceType.FillOrKill:
                            if self.order_book.is_order_will_full_match(offset_order.order):
                                logs = self.order_book.apply_order(offset_order.order)
                            else:
                                logs = self.order_book.nullify_order(offset_order.order)
                        elif offset_order.order.time_in_force == TimeInForceType.GoodTillCanceled:
                            logs = self.order_book.apply_order(offset_order.order)

                    for log in logs:
                        await self.log_chan.put(log)

                    order_offset = offset_order.offset

                elif isinstance(result, Snapshot):
                    snapshot: Snapshot = result
                    delta = order_offset - snapshot.order_offset
                    if delta <= 1000:
                        break

                    logging.info(
                        "should take snapshot: {} {}-[{}]-{}->".format(self.product_id, snapshot.order_offset, delta,
                                                                       order_offset))

                    snapshot.order_book_snapshot = self.order_book.snapshot()
                    snapshot.order_offset = order_offset
                    await self.snapshot_approve_req_chan.put(snapshot)

                break

    async def run_committer(self):
        seq: int = self.order_book.log_seq
        pending_snapshot: Optional[Snapshot] = None
        logs: List[Log] = list()

        while True:
            task1 = self.log_chan.get()
            task2 = self.snapshot_approve_req_chan.get()
            done, pending = await wait({task1, task2}, return_when=FIRST_COMPLETED)
            for t in done:
                result = t.result()
                if isinstance(result, Log):
                    log: Log = result
                    if log.get_seq() <= seq:
                        logging.info("discard log seq={}".format(seq))
                        break

                    if self.log_chan.qsize() > 0 and len(logs) < 100:
                        break
                    try:
                        await self.log_store.store(logs)
                    except Exception as ex:
                        logging.fatal("{}".format(ex))
                        sys.exit()

                    if pending_snapshot is not None and seq >= pending_snapshot.order_book_snapshot.log_seq:
                        await self.snapshot_chan.put(pending_snapshot)
                        pending_snapshot = None

                elif isinstance(result, Snapshot):
                    snapshot: Snapshot = result
                    if seq >= snapshot.order_book_snapshot.log_seq:
                        await self.snapshot_chan.put(snapshot)
                        pending_snapshot = None
                        break

                    if pending_snapshot is not None:
                        logging.info("discard snapshot request (seq={}), new one (seq={}) received".format(
                            pending_snapshot.order_book_snapshot.log_seq, snapshot.order_book_snapshot.log_seq))
                    pending_snapshot = snapshot

                break

    async def run_snapshots(self):
        order_offset = self.order_offset

        while True:
            task1 = self.snapshot_chan.get()
            try:
                snapshot: Snapshot = await wait_for(task1, timeout=30)
                await self.snapshot_store.store(snapshot=snapshot)

                logging.info("new snapshot stored: product={} OrderOffset={} LogSeq={}".format(
                    self.product_id, snapshot.order_offset, snapshot.order_book_snapshot.log_seq))

                order_offset = snapshot.order_offset

            except asyncio.TimeoutError:
                await self.snapshot_req_chan.put(Snapshot(order_book_snapshot=None, order_offset=order_offset))
