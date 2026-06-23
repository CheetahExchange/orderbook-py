#!/usr/bin/env python
# encoding: utf-8
import time
from functools import total_ordering

from sortedcontainers import SortedDict

# Snowflake epoch: Nov 04 2010 01:42:54 UTC in milliseconds
SNOWFLAKE_EPOCH: int = 1288834974657

# Default duration of the deduplication window in milliseconds (30 seconds)
TIME_WINDOW_DURATION: int = 30 * 1000


def extract_timestamp_from_id(order_id: int) -> int:
    """Extract the timestamp (in milliseconds since Snowflake epoch) from a Snowflake ID.

    Snowflake ID structure (64 bits):
    | 1 bit sign | 41 bits timestamp (ms since Snowflake epoch) | 10 bits node ID | 12 bits sequence |
    """
    return order_id >> 22


def current_time_since_snowflake_epoch() -> int:
    """Get current time in milliseconds relative to Snowflake epoch."""
    return int(time.time() * 1000) - SNOWFLAKE_EPOCH


class TimeWindowException(Exception):
    pass


@total_ordering
class TimeOrderIdKey(object):
    """Key for storing orders in the time-based window.
    Orders are sorted by timestamp first, then by order_id for uniqueness.
    """
    def __init__(self, timestamp: int, order_id: int):
        self.timestamp: int = timestamp
        self.order_id: int = order_id

    def __eq__(self, other):
        if not isinstance(other, TimeOrderIdKey):
            return NotImplemented
        return self.timestamp == other.timestamp and self.order_id == other.order_id

    def __lt__(self, other):
        if not isinstance(other, TimeOrderIdKey):
            return NotImplemented
        if self.timestamp != other.timestamp:
            return self.timestamp < other.timestamp
        return self.order_id < other.order_id

    def __hash__(self):
        return hash((self.timestamp, self.order_id))


class TimeWindowSnapshot(object):
    """Snapshot of TimeWindow state for serialization."""
    def __init__(self, min_time: int = 0, max_time: int = 0, duration: int = TIME_WINDOW_DURATION, epoch: int = SNOWFLAKE_EPOCH):
        self.min_time: int = min_time
        self.max_time: int = max_time
        self.duration: int = duration
        self.epoch: int = epoch

    def to_dict(self) -> dict:
        return {
            "min_time": self.min_time,
            "max_time": self.max_time,
            "duration": self.duration,
            "epoch": self.epoch,
        }

    @staticmethod
    def from_dict(d: dict):
        return TimeWindowSnapshot(
            min_time=int(d.get("min_time", 0)),
            max_time=int(d.get("max_time", 0)),
            duration=int(d.get("duration", TIME_WINDOW_DURATION)),
            epoch=int(d.get("epoch", SNOWFLAKE_EPOCH)),
        )


class TimeWindow(object):
    """Time-based sliding window for order deduplication.

    Keeps track of orders within a time duration (e.g., 30 seconds).
    Orders older than the window are automatically removed.

    Unlike ID-based windows which have limited capacity (e.g., 10000 IDs covering only ~2ms),
    a time-based window can tolerate much larger delays (30 seconds) making it suitable
    for Snowflake IDs where the ID range grows rapidly (4M IDs per millisecond).
    """

    def __init__(self, duration: int = TIME_WINDOW_DURATION):
        self.min_time: int = 0
        self.max_time: int = 0
        self.duration: int = duration
        self.orders: SortedDict = SortedDict()

    def put(self, order_id: int, now_time: int):
        """Add an order to the time window.

        Raises TimeWindowException if:
        - The order timestamp is older than min_time (expired)
        - The order already exists in the window (duplicate)
        """
        order_timestamp = extract_timestamp_from_id(order_id)

        # Slide window forward if needed
        if now_time > self.max_time:
            self.max_time = now_time
            new_min_time = self.max_time - self.duration
            if new_min_time > self.min_time:
                self._remove_expired_internal(new_min_time)
                self.min_time = new_min_time

        # Check if order is expired (older than window start)
        if order_timestamp < self.min_time:
            raise TimeWindowException(
                "expired order {}, orderTime={}, window [{},{})".format(
                    order_id, order_timestamp, self.min_time, self.max_time))

        # Check if order already exists
        key = TimeOrderIdKey(order_timestamp, order_id)
        if key in self.orders:
            raise TimeWindowException(
                "duplicate order {} at timestamp {}".format(order_id, order_timestamp))

        # Add order to window
        self.orders[key] = True

    def contains(self, order_id: int) -> bool:
        """Check if an order exists in the window."""
        order_timestamp = extract_timestamp_from_id(order_id)
        key = TimeOrderIdKey(order_timestamp, order_id)
        return key in self.orders

    def cleanup(self, now_time: int):
        """Remove expired orders based on current time.

        Should be called periodically to prevent memory leaks when there are no new orders.
        """
        if now_time > self.max_time:
            new_min_time = now_time - self.duration
            if new_min_time > self.min_time:
                self._remove_expired_internal(new_min_time)
                self.min_time = new_min_time
                self.max_time = now_time

    def size(self) -> int:
        """Return the number of orders in the window."""
        return len(self.orders)

    def snapshot(self) -> TimeWindowSnapshot:
        """Return a snapshot of the window state for serialization."""
        return TimeWindowSnapshot(
            min_time=self.min_time,
            max_time=self.max_time,
            duration=self.duration,
            epoch=SNOWFLAKE_EPOCH,
        )

    def restore(self, snapshot: TimeWindowSnapshot):
        """Restore the window from a snapshot.

        Orders are not restored from snapshot — they will be repopulated as orders come in.
        """
        self.min_time = snapshot.min_time
        self.max_time = snapshot.max_time
        self.duration = snapshot.duration
        self.orders.clear()

    def _remove_expired_internal(self, min_time: int):
        """Remove all orders with timestamp < min_time."""
        keys_to_remove = [k for k in self.orders if k.timestamp < min_time]
        for key in keys_to_remove:
            del self.orders[key]
