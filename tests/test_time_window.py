#!/usr/bin/env python
# encoding: utf-8
from unittest import TestCase

from utils.time_window import (
    TimeWindow, TimeWindowException, TimeWindowSnapshot,
    extract_timestamp_from_id, SNOWFLAKE_EPOCH, TIME_WINDOW_DURATION,
)

# Base relative timestamp for tests: Jan 1, 2020 relative to Snowflake epoch
# 1577836800000 - 1288834974657 = 289001825343
TEST_BASE_TIME = 289001825343


def make_snowflake_id(relative_timestamp_ms: int, node_id: int = 1, sequence: int = 1) -> int:
    timestamp_part = relative_timestamp_ms
    return (timestamp_part << 22) | ((node_id & 0x3FF) << 12) | (sequence & 0xFFF)


class TimeWindowTest(TestCase):
    def test_extract_timestamp(self):
        relative_timestamp = 411165025343
        order_id = make_snowflake_id(relative_timestamp, 1, 1)

        extracted = extract_timestamp_from_id(order_id)
        self.assertEqual(extracted, relative_timestamp)

    def test_put_and_contains(self):
        window = TimeWindow()
        now = TEST_BASE_TIME + 100000

        order_id = make_snowflake_id(now, 1, 1)

        # First put should succeed
        window.put(order_id, now)

        # Should be contained
        self.assertTrue(window.contains(order_id))

        # Second put with same ID should fail (duplicate)
        with self.assertRaises(TimeWindowException) as ctx:
            window.put(order_id, now)
        self.assertIn("duplicate", str(ctx.exception))

    def test_expired_order(self):
        window = TimeWindow()
        window.duration = 10000  # 10 seconds

        # First, advance the window by adding an order at t=TEST_BASE_TIME + 50000
        now = TEST_BASE_TIME + 50000
        order_id1 = make_snowflake_id(now, 1, 1)
        window.put(order_id1, now)

        # After this, min_time = now - 10000 = TEST_BASE_TIME + 40000

        # Try to add an expired order with timestamp TEST_BASE_TIME + 30000 (< min_time)
        old_time = TEST_BASE_TIME + 30000
        old_order_id = make_snowflake_id(old_time, 1, 2)

        with self.assertRaises(TimeWindowException) as ctx:
            window.put(old_order_id, now)
        self.assertIn("expired", str(ctx.exception))

    def test_window_sliding(self):
        window = TimeWindow()
        window.duration = 10000  # 10 seconds

        # Add order at t=TEST_BASE_TIME + 10000 with now_time=TEST_BASE_TIME + 10000
        # min_time becomes TEST_BASE_TIME + 0
        t1 = TEST_BASE_TIME + 10000
        id1 = make_snowflake_id(t1, 1, 1)
        window.put(id1, t1)
        self.assertTrue(window.contains(id1))

        # Advance window to t=TEST_BASE_TIME + 25000
        # min_time becomes TEST_BASE_TIME + 15000
        # Order at TEST_BASE_TIME + 10000 should be removed (10000 < 15000)
        t2 = TEST_BASE_TIME + 25000
        id2 = make_snowflake_id(t2, 1, 2)
        window.put(id2, t2)

        # First order should be removed (timestamp < min_time)
        self.assertFalse(window.contains(id1))
        self.assertTrue(window.contains(id2))

    def test_cleanup(self):
        window = TimeWindow()
        window.duration = 10000  # 10 seconds

        # Add order at TEST_BASE_TIME + 10000
        t1 = TEST_BASE_TIME + 10000
        id1 = make_snowflake_id(t1, 1, 1)
        window.put(id1, t1)

        # Cleanup at TEST_BASE_TIME + 25000 (15 seconds later, outside 10s window)
        window.cleanup(TEST_BASE_TIME + 25000)

        # First order should be removed
        self.assertFalse(window.contains(id1))

    def test_snapshot_and_restore(self):
        window = TimeWindow()
        window.duration = 10000

        t1 = TEST_BASE_TIME + 10000
        id1 = make_snowflake_id(t1, 1, 1)
        window.put(id1, t1)

        snap = window.snapshot()
        self.assertEqual(snap.min_time, TEST_BASE_TIME)
        self.assertEqual(snap.max_time, TEST_BASE_TIME + 10000)
        self.assertEqual(snap.duration, 10000)

        # Restore into a new window
        window2 = TimeWindow()
        window2.restore(snap)
        self.assertEqual(window2.min_time, TEST_BASE_TIME)
        self.assertEqual(window2.max_time, TEST_BASE_TIME + 10000)
        self.assertEqual(window2.duration, 10000)
        # Orders are cleared on restore
        self.assertEqual(window2.size(), 0)

    def test_size(self):
        window = TimeWindow()
        now = TEST_BASE_TIME + 100000

        id1 = make_snowflake_id(now, 1, 1)
        id2 = make_snowflake_id(now, 2, 2)
        window.put(id1, now)
        window.put(id2, now)
        self.assertEqual(window.size(), 2)
