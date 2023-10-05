#!/usr/bin/env python
# encoding: utf-8

import json
from typing import Dict

from models.models import Order
from utils.kafka import KafkaConsumer

TOPIC_ORDER_PREFIX = "matching_order_"


class KafkaOrderReader(object):
    def __init__(self, product_id: str, brokers: Dict[str], group_id: str):
        self.order_reader = KafkaConsumer(brokers=brokers, topic="".join([TOPIC_ORDER_PREFIX, product_id]),
                                          group_id=group_id)

    async def start(self):
        await self.order_reader.start()

    def set_offset(self, offset):
        self.set_offset(offset)

    async def fetch_order(self) -> (int, Order):
        message = await self.order_reader.fetch_message()
        if message is None:
            return 0, None

        o = json.loads(message.value)
        return message.offset, o
