#!/usr/bin/env python
# encoding: utf-8
import asyncio
import logging

from matching.engine import Engine
from matching.kafka_log import KafkaLogStore
from matching.kafka_order import KafkaOrderReader
from matching.redis_snapshot import RedisSnapshotStore
from models.models import Product

from config import read_config


async def main():
    config = read_config()

    product = Product(
        _id=config.product.id,
        base_currency=config.product.base_currency,
        quote_currency=config.product.quote_currency,
        base_scale=config.product.base_scale,
        quote_scale=config.product.quote_scale,
    )

    snapshot_store = RedisSnapshotStore(
        product_id=config.product.id,
        ip=config.redis.ip,
        port=config.redis.port,
    )

    log_store = KafkaLogStore(product_id=config.product.id, brokers=config.kafka.brokers)
    await log_store.start()

    order_reader = KafkaOrderReader(
        product_id=config.product.id,
        brokers=config.kafka.brokers,
        group_id=config.kafka.group_id,
    )
    await order_reader.start()

    # engine
    engine = Engine(product=product, order_reader=order_reader, log_store=log_store,
                    snapshot_store=snapshot_store)

    await engine.initialize_snapshot()
    await engine.start()


if __name__ == "__main__":
    config = read_config()
    FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    logging.basicConfig(format=FORMAT, level=getattr(logging, config.log.level, logging.INFO))
    asyncio.run(main())
