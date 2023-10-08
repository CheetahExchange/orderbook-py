#!/usr/bin/env python
# encoding: utf-8
from typing import Dict, List

from matching.log import Log
from utils.kafka import KafkaProducer

TOPIC_BOOK_MESSAGE_PREFIX = "matching_message_"


class KafkaLogStore(object):
    def __init__(self, product_id: str, brokers: Dict[str]):
        self.topic = "".join([TOPIC_BOOK_MESSAGE_PREFIX, product_id])
        self.log_writer = KafkaProducer(brokers=brokers)

    async def store(self, logs: List[Log]):
        payloads = [Log.to_json_str(log).encode("utf8") for log in logs]
        await self.log_writer.send_batch(topic=self.topic, payloads=payloads)
        await self.log_writer.flush()
