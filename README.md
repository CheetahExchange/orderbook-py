# orderbook-py

--------

### What is orderbook-py

**orderbook-py is a AsyncIO Python Matching Engine**


### Installing dependencies
* Install Python3.9 or higher
```
sudo apt-get update
sudo apt-get install python3-pip

sudo pip install pipenv
```

* Install Redis-server and [Kafka](https://kafka.apache.org/)

```
sudo apt-get install redis-server
```


### Deploy and Run

* update config.py with the correct parameters.

```
git clone https://github.com/CheetahExchange/orderbook-py
cd orderbook-py

pipenv lock
pipenv install
pipenv run python main.py
```


* the running log looks like this

```
2023-10-08 17:54:32,809 - aiokafka.consumer.subscription_state - INFO - Updating subscribed topics to: frozenset({'matching_order_BTC-USD'})
2023-10-08 17:54:32,831 - aiokafka.consumer.group_coordinator - INFO - Discovered coordinator 0 for group order-reader-BTC-USD-group
2023-10-08 17:54:32,831 - aiokafka.consumer.group_coordinator - INFO - Revoking previously assigned partitions set() for group order-reader-BTC-USD-group
2023-10-08 17:54:32,831 - aiokafka.consumer.group_coordinator - INFO - (Re-)joining group order-reader-BTC-USD-group
2023-10-08 17:54:42,234 - aiokafka.consumer.group_coordinator - INFO - Joined group 'order-reader-BTC-USD-group' (generation 30) with member_id aiokafka-0.8.1-5679bd07-ed5e-4d22-8260-38c19dcf4d7c
2023-10-08 17:54:42,234 - aiokafka.consumer.group_coordinator - INFO - Elected group leader -- performing partition assignments using roundrobin
2023-10-08 17:54:42,237 - aiokafka.consumer.group_coordinator - INFO - Successfully synced group order-reader-BTC-USD-group with generation 30
2023-10-08 17:54:42,237 - aiokafka.consumer.group_coordinator - INFO - Setting newly assigned partitions {TopicPartition(topic='matching_order_BTC-USD', partition=0)} for group order-reader-BTC-USD-group
2023-10-08 17:54:42,742 - root - INFO - fetch_order: {"id": 1, "created_at": 1695783003020967000, "product_id": "BTC-USD", "user_id": 1, "client_oid": "", "price": "10.00", "size": "1.00", "funds": "0.00", "type": "limit", "side": "sell", "time_in_force": "GTC", "status": "new"}
2023-10-08 17:54:42,742 - root - INFO - fetch_order: {"id": 2, "created_at": 1695783003020967000, "product_id": "BTC-USD", "user_id": 1, "client_oid": "", "price": "10.00", "size": "1.00", "funds": "0.00", "type": "limit", "side": "sell", "time_in_force": "GTC", "status": "new"}
2023-10-08 17:54:42,742 - root - INFO - fetch_order: {"id": 3, "created_at": 1695783003020967000, "product_id": "BTC-USD", "user_id": 1, "client_oid": "", "price": "10.00", "size": "1.00", "funds": "0.00", "type": "limit", "side": "sell", "time_in_force": "GTC", "status": "new"}
2023-10-08 17:54:42,742 - root - INFO - fetch_order: {"id": 4, "created_at": 1695783003020967000, "product_id": "BTC-USD", "user_id": 1, "client_oid": "", "price": "10.00", "size": "5.00", "funds": "0.00", "type": "limit", "side": "buy", "time_in_force": "GTC", "status": "new"}
2023-10-08 17:54:42,742 - root - INFO - fetch_order: {"id": 5, "created_at": 1695783003020967000, "product_id": "BTC-USD", "user_id": 1, "client_oid": "", "price": "10.00", "size": "2.00", "funds": "0.00", "type": "limit", "side": "sell", "time_in_force": "GTC", "status": "new"}
2023-10-08 17:54:42,743 - root - INFO - OpenLog: {"type": "open", "sequence": 1, "product_id": "BTC-USD", "time": 1696758882743372300, "order_id": 1, "user_id": 1, "remaining_size": "1.00", "price": "10.00", "side": "sell", "time_in_force": "GTC"}
2023-10-08 17:54:42,743 - root - INFO - OpenLog: {"type": "open", "sequence": 2, "product_id": "BTC-USD", "time": 1696758882743372300, "order_id": 2, "user_id": 1, "remaining_size": "1.00", "price": "10.00", "side": "sell", "time_in_force": "GTC"}
2023-10-08 17:54:42,743 - root - INFO - OpenLog: {"type": "open", "sequence": 3, "product_id": "BTC-USD", "time": 1696758882743372300, "order_id": 3, "user_id": 1, "remaining_size": "1.00", "price": "10.00", "side": "sell", "time_in_force": "GTC"}
2023-10-08 17:54:42,744 - root - INFO - MatchLog: {"type": "match", "sequence": 4, "product_id": "BTC-USD", "time": 1696758882743372300, "trade_seq": 1, "taker_order_id": 4, "maker_order_id": 1, "taker_user_id": 1, "maker_user_id": 1, "side": "sell", "price": "10.00", "size": "1.00", "taker_time_in_force": "GTC", "maker_time_in_force": "GTC"}
2023-10-08 17:54:42,744 - root - INFO - DoneLog: {"type": "done", "sequence": 5, "product_id": "BTC-USD", "time": 1696758882744372000, "order_id": 1, "user_id": 1, "remaining_size": "0.00", "price": "10.00", "reason": "filled", "side": "sell", "time_in_force": "GTC"}
2023-10-08 17:54:42,744 - root - INFO - MatchLog: {"type": "match", "sequence": 6, "product_id": "BTC-USD", "time": 1696758882744372000, "trade_seq": 2, "taker_order_id": 4, "maker_order_id": 2, "taker_user_id": 1, "maker_user_id": 1, "side": "sell", "price": "10.00", "size": "1.00", "taker_time_in_force": "GTC", "maker_time_in_force": "GTC"}
2023-10-08 17:54:42,744 - root - INFO - DoneLog: {"type": "done", "sequence": 7, "product_id": "BTC-USD", "time": 1696758882744372000, "order_id": 2, "user_id": 1, "remaining_size": "0.00", "price": "10.00", "reason": "filled", "side": "sell", "time_in_force": "GTC"}
2023-10-08 17:54:42,744 - root - INFO - MatchLog: {"type": "match", "sequence": 8, "product_id": "BTC-USD", "time": 1696758882744372000, "trade_seq": 3, "taker_order_id": 4, "maker_order_id": 3, "taker_user_id": 1, "maker_user_id": 1, "side": "sell", "price": "10.00", "size": "1.00", "taker_time_in_force": "GTC", "maker_time_in_force": "GTC"}
2023-10-08 17:54:42,744 - root - INFO - DoneLog: {"type": "done", "sequence": 9, "product_id": "BTC-USD", "time": 1696758882744372000, "order_id": 3, "user_id": 1, "remaining_size": "0.00", "price": "10.00", "reason": "filled", "side": "sell", "time_in_force": "GTC"}
2023-10-08 17:54:42,744 - root - INFO - OpenLog: {"type": "open", "sequence": 10, "product_id": "BTC-USD", "time": 1696758882744372000, "order_id": 4, "user_id": 1, "remaining_size": "2.00", "price": "10.00", "side": "buy", "time_in_force": "GTC"}
2023-10-08 17:54:42,745 - root - INFO - MatchLog: {"type": "match", "sequence": 11, "product_id": "BTC-USD", "time": 1696758882745374100, "trade_seq": 4, "taker_order_id": 5, "maker_order_id": 4, "taker_user_id": 1, "maker_user_id": 1, "side": "buy", "price": "10.00", "size": "2.00", "taker_time_in_force": "GTC", "maker_time_in_force": "GTC"}
2023-10-08 17:54:42,745 - root - INFO - DoneLog: {"type": "done", "sequence": 12, "product_id": "BTC-USD", "time": 1696758882745374100, "order_id": 4, "user_id": 1, "remaining_size": "0.00", "price": "10.00", "reason": "filled", "side": "buy", "time_in_force": "GTC"}
2023-10-08 17:54:42,745 - root - INFO - DoneLog: {"type": "done", "sequence": 13, "product_id": "BTC-USD", "time": 1696758882745374100, "order_id": 5, "user_id": 1, "remaining_size": "0.00", "price": "10.00", "reason": "filled", "side": "sell", "time_in_force": "GTC"}

```



### How to Test

* place order test

```python
#!/usr/bin/env python
# encoding: utf-8

import logging
from kafka import KafkaProducer
from decimal import Decimal
import json

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
