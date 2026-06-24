# orderbook-py

An AsyncIO-based limit order book matching engine in Python, powered by Kafka and Redis.

## Features

- Price-time priority matching engine (FIFO)
- Order types: **Limit** and **Market**
- Time-in-force: **GTC** (Good-Till-Canceled), **IOC** (Immediate-or-Cancel), **GTX** (Good-Till-Crossing / Post-Only), **FOK** (Fill-or-Kill)
- Kafka-based order ingestion and log output
- Redis-based snapshot persistence and recovery
- Snowflake ID-aware time-window deduplication
- Periodic snapshot with commit-then-persist guarantee
- AsyncIO pipeline: fetcher, applier, committer, and snapshot tasks run concurrently

## Architecture

```
                     ┌──────────────┐
  Kafka (orders) ──►│  Fetcher     │──► order_chan ──┐
                     └──────────────┘                │
                                                     ▼
                                              ┌──────────────┐
                                              │  Applier     │◄── snapshot_req_chan
                                              │  (OrderBook) │
                                              └──────┬───────┘
                                                     │
                                               log_chan │
                                                     ▼
                                              ┌──────────────┐
  Kafka (logs)   ◄───┌───────────────────────│  Committer   │
                     │                        └──────┬───────┘
                     │                               │
                     │                 snapshot_approve │
                     │                               ▼
                     │                        ┌──────────────┐
  Redis (snapshot) ◄─│───────────────────────│  Snapshots   │
                     │                        └──────────────┘
                     │
                     │  ┌──────────────────┐
                     └──│ Window Cleanup   │ (periodic, every 10s)
                        └──────────────────┘
```

## Project Structure

```
orderbook-py/
├── main.py                    # Entry point
├── config.py                  # Configuration loader
├── config.json                # Configuration file
├── matching/
│   ├── engine.py              # Matching engine with async pipeline
│   ├── order_book.py          # Order book, depth, and matching logic
│   ├── log.py                 # Log types: OpenLog, DoneLog, MatchLog
│   ├── kafka_order.py         # Kafka order consumer
│   ├── kafka_log.py           # Kafka log producer
│   └── redis_snapshot.py      # Redis snapshot store
├── models/
│   ├── models.py              # Order and Product models
│   └── types.py               # Enums: OrderType, Side, TimeInForce, etc.
├── utils/
│   ├── kafka.py               # Kafka producer/consumer wrappers
│   ├── redis.py               # Async Redis client wrapper
│   ├── time_window.py         # Time-based sliding window for deduplication
│   ├── window.py              # ID-based bitmap window (legacy)
│   ├── bitmap.py              # BitMap utility
│   └── utils.py               # JSON encoder, decimal helpers
└── tests/
    ├── test_models.py
    ├── test_types.py
    ├── test_bitmap.py
    ├── test_utils.py
    └── test_time_window.py
```

## Prerequisites

- Python 3.11+
- Redis Server
- Apache Kafka

## Install

```bash
git clone https://github.com/CheetahExchange/orderbook-py
cd orderbook-py

pip install pipenv
pipenv install
```

## Configuration

Edit `config.json` to match your environment:

```json
{
  "product": {
    "id": "BTC-USD",
    "base_currency": "BTC",
    "quote_currency": "USD",
    "base_scale": 6,
    "quote_scale": 2
  },
  "redis": {
    "ip": "127.0.0.1",
    "port": 6379
  },
  "kafka": {
    "brokers": ["127.0.0.1:9092"],
    "group_id": "order-reader-BTC-USD-group",
    "message_timeout": 5,
    "session_timeout": 10
  },
  "log": {
    "level": "INFO"
  }
}
```

## Run

```bash
pipenv run python main.py
```

Sample output:

```
2023-10-08 17:54:32,809 - aiokafka.consumer.subscription_state - INFO - Updating subscribed topics to: frozenset({'matching_order_BTC-USD'})
2023-10-08 17:54:42,742 - root - INFO - fetch_order: {"id": 1, "created_at": 1695783003020967000, "product_id": "BTC-USD", "user_id": 1, "client_oid": "", "price": "10.00", "size": "1.00", "funds": "0.00", "type": "limit", "side": "sell", "time_in_force": "GTC", "status": "new"}
2023-10-08 17:54:42,743 - root - INFO - OpenLog: {"type": "open", "sequence": 1, "product_id": "BTC-USD", "time": 1696758882743372300, "order_id": 1, "user_id": 1, "remaining_size": "1.00", "price": "10.00", "side": "sell", "time_in_force": "GTC"}
2023-10-08 17:54:42,744 - root - INFO - MatchLog: {"type": "match", "sequence": 4, "product_id": "BTC-USD", "time": 1696758882743372300, "trade_seq": 1, "taker_order_id": 4, "maker_order_id": 1, "taker_user_id": 1, "maker_user_id": 1, "side": "sell", "price": "10.00", "size": "1.00", "taker_time_in_force": "GTC", "maker_time_in_force": "GTC"}
2023-10-08 17:54:42,744 - root - INFO - DoneLog: {"type": "done", "sequence": 5, "product_id": "BTC-USD", "time": 1696758882744372000, "order_id": 1, "user_id": 1, "remaining_size": "0.00", "price": "10.00", "reason": "filled", "side": "sell", "time_in_force": "GTC"}
```

## Test

### Unit Tests

```bash
pipenv run pytest tests/
```

### Place Order Test

Send a test order to the matching engine via Kafka:

```python
#!/usr/bin/env python
# encoding: utf-8

import logging
import json
from decimal import Decimal
from kafka import KafkaProducer

log_level = logging.DEBUG
logging.basicConfig(level=log_level)
log = logging.getLogger('kafka')
log.setLevel(log_level)


class Order:
    def __init__(self, _id, created_at, product_id, user_id, client_oid, price, size, funds, _type, side, time_in_force,
                 status):
        self.id = _id
        self.created_at = created_at
        self.product_id = product_id
        self.user_id = user_id
        self.client_oid = client_oid
        self.price = price
        self.size = size
        self.funds = funds
        self.type = _type
        self.side = side
        self.time_in_force = time_in_force
        self.status = status

producer = KafkaProducer(bootstrap_servers='127.0.0.1:9092')

order = Order(_id=43, created_at=1695783003020967000, product_id="BTC-USD", user_id=1, client_oid="",
              price=Decimal("20.00"), size=Decimal("3000.00"), funds=Decimal("0.00"), _type="limit",
              side="buy", time_in_force="GTC", status="new")

message = json.dumps(vars(order), default=str)
print(message)

producer.send('matching_order_BTC-USD', message.encode("utf8"))
producer.flush()
producer.close()
```

## License

[MIT](LICENSE)
