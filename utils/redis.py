from redis import asyncio as aioredis


class RedisClient(object):
    def __init__(self, ip: str = "127.0.0.1", port: int = 6379):
        url = "redis://{}:{}".format(ip, port)
        self.redis = aioredis.from_url(url=url)
