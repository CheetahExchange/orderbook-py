#!/usr/bin/env python
# encoding: utf-8
import asyncio
import logging

from matching.engine import Engine
from matching.kafka_log import KafkaLogStore
from matching.kafka_order import KafkaOrderReader
from matching.redis_snapshot import RedisSnapshotStore
from models.models import Product


async def main():
    product = Product(_id="BTC-USD", base_currency="BTC", quote_currency="USD", base_scale=6, quote_scale=2)
    snapshot_store = RedisSnapshotStore(product_id=product.id, ip="192.168.1.123", port=6379)
    order_reader = KafkaOrderReader(product_id=product.id, brokers=["192.168.1.123:9092"],
                                    group_id="order-reader-{}-group".format(product.id))
    log_store = KafkaLogStore(product_id=product.id, brokers=["192.168.1.123:9092"])
    await order_reader.start()

    engine = Engine(product=product, order_reader=order_reader, log_store=log_store,
                    snapshot_store=snapshot_store)
    await engine.initialize_snapshot()
    await engine.start()


if __name__ == "__main__":
    FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    logging.basicConfig(format=FORMAT, level=logging.INFO)
    asyncio.run(main())
