#!/usr/bin/env python
# encoding: utf-8
import asyncio
import json
import logging
import sys
from asyncio import Queue, wait, FIRST_COMPLETED, wait_for, gather
from typing import Optional, List

from matching.kafka_log import KafkaLogStore
from matching.kafka_order import KafkaOrderReader
from matching.log import Log
from matching.order_book import OrderBookSnapshot, OrderBook
from models.models import Product, Order
from models.types import TimeInForceType, OrderStatus
from utils.time_window import current_time_since_snowflake_epoch


class Snapshot(object):
    def __init__(self, order_book_snapshot: Optional[OrderBookSnapshot], order_offset: int):
        self.order_book_snapshot: Optional[OrderBookSnapshot] = order_book_snapshot
        self.order_offset: int = order_offset

    def to_dict(self) -> dict:
        return {
            "order_book_snapshot": self.order_book_snapshot.to_dict() if self.order_book_snapshot else None,
            "order_offset": self.order_offset,
        }

    @staticmethod
    def to_json_str(snapshot):
        return json.dumps(snapshot.to_dict())

    @staticmethod
    def from_json_str(json_str: str):
        snapshot_dict = json.loads(json_str)
        order_offset = int(snapshot_dict.get("order_offset"))
        order_book_snapshot_dict = snapshot_dict.get("order_book_snapshot")
        if order_book_snapshot_dict is None:
            return Snapshot(order_book_snapshot=None, order_offset=order_offset)

        order_book_snapshot = OrderBookSnapshot.from_dict(order_book_snapshot_dict)
        return Snapshot(order_book_snapshot=order_book_snapshot, order_offset=order_offset)


class OffsetOrder(object):
    def __init__(self, offset: int, order: Order):
        self.offset: int = offset
        self.order: Order = order


class Engine(object):
    def __init__(self, product: Product, order_reader: KafkaOrderReader, log_store: KafkaLogStore,
                 snapshot_store):
        # productId is the unique identifier of an engine, and each product corresponds to an engine
        self.product_id: str = product.id
        # The orderBook held by the engine, corresponding to the product, needs
        # a snapshot and is restored from the snapshot
        self.order_book: OrderBook = OrderBook(product, 0, 0)
        # for reading order
        self.order_reader: KafkaOrderReader = order_reader
        # Read the starting offset of the order, which will be restored from the snapshot when it is first started
        self.order_offset: int = 0
        # Used to save orderBook log
        self.log_store: KafkaLogStore = log_store
        # The storage method of persistent snapshot should support multiple methods, such as local disk, redis, etc.
        self.snapshot_store = snapshot_store
        # The read order will be written to chan, and the offset of the order needs
        # to be carried when writing the order.
        self.order_chan: Queue = Queue(maxsize=10000)
        # The log is written to the queue, and all the logs to be written need to enter the chan and wait
        self.log_chan: Queue = Queue(maxsize=10000)
        # To initiate a snapshot request, you need to carry the offset of the last snapshot
        self.snapshot_req_chan: Queue = Queue(maxsize=32)
        # The snapshot is completely ready, you need to ensure that all data before the snapshot has been committed
        self.snapshot_approve_req_chan: Queue = Queue(maxsize=32)
        # The snapshot data is ready and all data before the snapshot has been committed
        self.snapshot_chan: Queue = Queue(maxsize=32)

    def restore(self, snapshot: Snapshot):
        self.order_offset = snapshot.order_offset
        self.order_book.restore(snapshot=snapshot.order_book_snapshot)

    async def initialize_snapshot(self):
        # Get the latest snapshot and use the snapshot for recovery
        snapshot = await self.snapshot_store.get_latest()
        if snapshot is not None:
            self.restore(snapshot=snapshot)

    async def start(self):
        task1 = asyncio.create_task(self.run_fetcher())
        task2 = asyncio.create_task(self.run_applier())
        task3 = asyncio.create_task(self.run_committer())
        task4 = asyncio.create_task(self.run_snapshots())
        task5 = asyncio.create_task(self.run_window_cleanup())
        await gather(task1, task2, task3, task4, task5)

    # Responsible for continuously pulling orders and writing to chan
    async def run_fetcher(self):
        offset = self.order_offset
        if offset > 0:
            offset += 1

        try:
            await self.order_reader.set_offset(offset)
        except Exception as ex:
            logging.fatal("set order reader offset error: {}".format(ex))
            sys.exit()

        while True:
            try:
                offset, order = await self.order_reader.fetch_order()
                if order is None:
                    continue
                logging.info("fetch_order: {}".format(Order.to_json_str(order)))
                await self.order_chan.put(OffsetOrder(offset=offset, order=order))
            except Exception as ex:
                logging.error("{}".format(str(ex)))

    # Get the order from the local queue, execute the orderBook operation, and
    # respond to the snapshot request at the same time
    async def run_applier(self):
        order_offset: int = 0

        while True:
            task1 = asyncio.create_task(self.order_chan.get())
            task2 = asyncio.create_task(self.snapshot_req_chan.get())
            done, pending = await wait({task1, task2}, return_when=FIRST_COMPLETED)

            # Cancel the pending task that didn't complete
            for t in pending:
                t.cancel()
                try:
                    await t
                except asyncio.CancelledError:
                    pass

            for t in done:
                result = t.result()
                if isinstance(result, OffsetOrder):
                    offset_order: OffsetOrder = result
                    logs: List[Log] = list()
                    if offset_order.order.status == OrderStatus.OrderStatusCancelling:
                        logs = self.order_book.cancel_order(offset_order.order)
                    else:
                        # IOC
                        if offset_order.order.time_in_force == TimeInForceType.ImmediateOrCancel:
                            logs = self.order_book.apply_order(offset_order.order)
                            # cancel the rest size
                            ioc_logs = self.order_book.cancel_order(offset_order.order)
                            if len(ioc_logs) != 0:
                                logs.extend(ioc_logs)
                        elif offset_order.order.time_in_force == TimeInForceType.GoodTillCrossing:
                            # GTX
                            if self.order_book.is_order_will_not_match(offset_order.order):
                                logs = self.order_book.apply_order(offset_order.order)
                            else:
                                logs = self.order_book.nullify_order(offset_order.order)
                        elif offset_order.order.time_in_force == TimeInForceType.FillOrKill:
                            # FOK
                            if self.order_book.is_order_will_full_match(offset_order.order):
                                logs = self.order_book.apply_order(offset_order.order)
                            else:
                                logs = self.order_book.nullify_order(offset_order.order)
                        elif offset_order.order.time_in_force == TimeInForceType.GoodTillCanceled:
                            # GTC
                            logs = self.order_book.apply_order(offset_order.order)

                    # Write the log generated by orderBook to chan for persistence
                    for log in logs:
                        await self.log_chan.put(log)

                    # The offset of the record order is used to determine whether a snapshot needs to be taken
                    order_offset = offset_order.offset

                elif isinstance(result, Snapshot):
                    snapshot: Snapshot = result
                    # Receive a snapshot request and determine whether it is really necessary to perform a snapshot
                    delta = order_offset - snapshot.order_offset
                    if delta <= 1000:
                        continue

                    logging.info(
                        "should take snapshot: {} {}-[{}]-{}->".format(self.product_id, snapshot.order_offset, delta,
                                                                       order_offset))

                    # Execute the snapshot, and write the snapshot data to the approval chan
                    snapshot.order_book_snapshot = self.order_book.snapshot()
                    snapshot.order_offset = order_offset
                    await self.snapshot_approve_req_chan.put(snapshot)

    # Periodically clean up expired orders in time window to prevent memory leaks
    async def run_window_cleanup(self):
        while True:
            await asyncio.sleep(10)
            now_time = current_time_since_snowflake_epoch()
            self.order_book.time_window.cleanup(now_time)

    # Persist the log generated by orderBook, and need to respond to snapshot approval
    async def run_committer(self):
        seq: int = self.order_book.log_seq
        pending_snapshot: Optional[Snapshot] = None
        logs: List[Log] = list()

        while True:
            task1 = asyncio.create_task(self.log_chan.get())
            task2 = asyncio.create_task(self.snapshot_approve_req_chan.get())
            done, pending = await wait({task1, task2}, return_when=FIRST_COMPLETED)

            # Cancel the pending task that didn't complete
            for t in pending:
                t.cancel()
                try:
                    await t
                except asyncio.CancelledError:
                    pass

            for t in done:
                result = t.result()
                if isinstance(result, Log):
                    log: Log = result
                    # discard duplicate log
                    if log.get_seq() <= seq:
                        logging.info("discard log seq={}".format(seq))
                        continue

                    logs.append(log)

                    # Drain more logs from channel if available (batch read)
                    for _ in range(100):
                        try:
                            log = self.log_chan.get_nowait()
                        except asyncio.QueueEmpty:
                            break
                        if log.get_seq() <= seq:
                            logging.info("discard log seq={}".format(seq))
                            continue
                        logs.append(log)

                    try:
                        # store log first, only update seq after successful persistence
                        await self.log_store.store(logs)
                    except Exception as ex:
                        logging.fatal("{}".format(ex))
                        sys.exit()

                    # Store succeeded, safely update seq to persisted values
                    for l in logs:
                        if l.get_seq() > seq:
                            seq = l.get_seq()
                    logs.clear()

                    # approve pending snapshot
                    if pending_snapshot is not None and seq >= pending_snapshot.order_book_snapshot.log_seq:
                        await self.snapshot_chan.put(pending_snapshot)
                        pending_snapshot = None

                elif isinstance(result, Snapshot):
                    snapshot: Snapshot = result
                    # The written seq has reached or exceeded the snapshot seq, and the snapshot request is approved
                    if seq >= snapshot.order_book_snapshot.log_seq:
                        await self.snapshot_chan.put(snapshot)
                        pending_snapshot = None
                        continue

                    # There are currently unapproved snapshots, but there are new snapshot requests, discard the old ones
                    if pending_snapshot is not None:
                        logging.info("discard snapshot request (seq={}), new one (seq={}) received".format(
                            pending_snapshot.order_book_snapshot.log_seq, snapshot.order_book_snapshot.log_seq))
                    pending_snapshot = snapshot

                break

    # Initiate snapshot requests regularly, and be responsible for persisting approved snapshots
    async def run_snapshots(self):
        # order orderOffset at the last snapshot
        order_offset = self.order_offset

        while True:
            task1 = asyncio.create_task(self.snapshot_chan.get())
            try:
                snapshot: Snapshot = await wait_for(task1, timeout=30)
                # store snapshot
                await self.snapshot_store.store(snapshot=snapshot)

                logging.info("new snapshot stored: product={} OrderOffset={} LogSeq={}".format(
                    self.product_id, snapshot.order_offset, snapshot.order_book_snapshot.log_seq))

                # update offset for next snapshot request
                order_offset = snapshot.order_offset

            except asyncio.TimeoutError:
                # make a new snapshot request
                await self.snapshot_req_chan.put(Snapshot(order_book_snapshot=None, order_offset=order_offset))
