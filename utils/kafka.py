from typing import Dict

from aiokafka import AIOKafkaProducer, AIOKafkaConsumer


class KafkaProducer(object):
    def __init__(self, brokers: Dict):
        self.producer = AIOKafkaProducer(bootstrap_servers=','.join(brokers))

    async def start(self):
        await self.producer.start()

    async def send(self, topic: str, payload: bytes):
        await self.producer.send(topic=topic, value=payload)

    async def send_and_wait(self, topic: str, payload: bytes):
        await self.producer.send_and_wait(topic=topic, value=payload)


class KafkaConsumer(object):
    def __init__(self, brokers: Dict, topic: str, group_id: str):
        self.partitions = dict()
        self.topic = topic
        self.group_id = group_id
        self.consumer = AIOKafkaConsumer(topic, bootstrap_servers=','.join(brokers),
                                         group_id=group_id)

    async def start(self):
        await self.consumer.start()

    def set_offset(self, offset):
        self.partitions = self.consumer.assignment()
        for partition in self.partitions:
            self.consumer.seek(partition=partition, offset=offset)

    async def fetch_message(self):
        kafka_record = await self.consumer.getone(self.partitions)
        return kafka_record