#!/usr/bin/env python
# encoding: utf-8
import asyncio
import logging

from matching.engine import Engine
from matching.kafka_log import KafkaLogStore
from matching.kafka_order import KafkaOrderReader
from matching.redis_snapshot import RedisSnapshotStore
from models.models import Product

from config import *


async def main():
    product = Product(_id=product_id, base_currency=base_currency, quote_currency=quote_currency, base_scale=base_scale,
                      quote_scale=quote_scale)

    snapshot_store = RedisSnapshotStore(product_id=product_id, ip=redis_ip, port=redis_port)

    log_store = KafkaLogStore(product_id=product.id, brokers=kafka_brokers)

    order_reader = KafkaOrderReader(product_id=product_id, brokers=kafka_brokers, group_id=group_id)
    await order_reader.start()

    # engine
    engine = Engine(product=product, order_reader=order_reader, log_store=log_store,
                    snapshot_store=snapshot_store)

    await engine.initialize_snapshot()
    await engine.start()


if __name__ == "__main__":
    FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    logging.basicConfig(format=FORMAT, level=logging.INFO)
    asyncio.run(main())
