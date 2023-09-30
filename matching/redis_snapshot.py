from matching.engine import Snapshot
from utils.redis import RedisClient

import json

TOPIC_SNAPSHOT_PREFIX: str = "matching_snapshot_"


class RedisSnapshotStore(object):
    def __init__(self, product_id: str, ip: str, port: int):
        self.product_id = product_id
        self.snapshot_key = "".join([TOPIC_SNAPSHOT_PREFIX, product_id])
        self.redis_client = RedisClient(ip=ip, port=port)

    async def store(self, snapshot: Snapshot):
        s = json.dumps(snapshot)
        await self.redis_client.redis.set(name=self.snapshot_key, value=s)

    async def get_latest(self):
        s = await self.redis_client.redis.get(name=self.snapshot_key)
        if s is not None:
            return json.loads(s)
        return None
