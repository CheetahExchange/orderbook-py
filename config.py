#!/usr/bin/env python
# encoding: utf-8
import json
import os


class ProductConfig(object):
    def __init__(self, id: str, base_currency: str, quote_currency: str, base_scale: int, quote_scale: int):
        self.id: str = id
        self.base_currency: str = base_currency
        self.quote_currency: str = quote_currency
        self.base_scale: int = base_scale
        self.quote_scale: int = quote_scale


class RedisConfig(object):
    def __init__(self, ip: str, port: int):
        self.ip: str = ip
        self.port: int = port


class KafkaConfig(object):
    def __init__(self, brokers: list, group_id: str, message_timeout: int, session_timeout: int):
        self.brokers: list = brokers
        self.group_id: str = group_id
        self.message_timeout: int = message_timeout
        self.session_timeout: int = session_timeout


class LogConfig(object):
    def __init__(self, level: str):
        self.level: str = level


class Config(object):
    def __init__(self, product: ProductConfig, redis: RedisConfig, kafka: KafkaConfig, log: LogConfig):
        self.product: ProductConfig = product
        self.redis: RedisConfig = redis
        self.kafka: KafkaConfig = kafka
        self.log: LogConfig = log


_CONFIG_FILE_NAME = "config.json"


def read_config() -> Config:
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), _CONFIG_FILE_NAME)
    with open(config_path, "r") as f:
        config_dict = json.load(f)

    product = ProductConfig(
        id=config_dict["product"]["id"],
        base_currency=config_dict["product"]["base_currency"],
        quote_currency=config_dict["product"]["quote_currency"],
        base_scale=config_dict["product"]["base_scale"],
        quote_scale=config_dict["product"]["quote_scale"],
    )

    redis = RedisConfig(
        ip=config_dict["redis"]["ip"],
        port=config_dict["redis"]["port"],
    )

    kafka = KafkaConfig(
        brokers=config_dict["kafka"]["brokers"],
        group_id=config_dict["kafka"]["group_id"],
        message_timeout=config_dict["kafka"].get("message_timeout", 5),
        session_timeout=config_dict["kafka"].get("session_timeout", 10),
    )

    log = LogConfig(
        level=config_dict["log"].get("level", "INFO"),
    )

    return Config(product=product, redis=redis, kafka=kafka, log=log)
