from __future__ import annotations

import base64
import json
import unittest
import zlib

from failover import (
    choose_next,
    decode_sources,
    mark_failed,
    source_key,
    startup_timeout_seconds,
)


def payload(sources):
    raw = json.dumps({"v": 1, "sources": sources}, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(zlib.compress(raw, 9)).decode("ascii").rstrip("=")


class FailoverTests(unittest.TestCase):
    def test_decode_applies_catchup_vavoo_other_policy(self):
        sources = decode_sources(
            payload(
                [
                    {"type": "hls", "priority": 50, "route": "split", "target": "https://example.test/live.m3u8"},
                    {"type": "http", "priority": 56, "route": "split", "target": "http://127.0.0.1:8899/stream/a"},
                    {"type": "therandtv", "priority": 10, "route": "fr", "target": "plugin://plugin.video.catchuptvandmore/live"},
                ]
            )
        )
        self.assertEqual([10, 56, 50], [source["priority"] for source in sources])
        self.assertEqual(["catchup", "vavoo", "other"], [source["family"] for source in sources])
        self.assertEqual(["fr", "split", "split"], [source["route"] for source in sources])

    def test_decode_preserves_numeric_priority_inside_family(self):
        sources = decode_sources(
            payload(
                [
                    {"type": "http", "priority": 52, "route": "split", "target": "http://127.0.0.1:8899/stream/b"},
                    {"type": "hls", "priority": 55, "route": "split", "target": "https://example.test/b.m3u8"},
                    {"type": "http", "priority": 51, "route": "split", "target": "http://127.0.0.1:8899/stream/a"},
                    {"type": "hls", "priority": 50, "route": "split", "target": "https://example.test/a.m3u8"},
                ]
            )
        )
        self.assertEqual([51, 52, 50, 55], [source["priority"] for source in sources])

    def test_decode_rejects_recursive_therandtv_target(self):
        with self.assertRaises(ValueError):
            decode_sources(
                payload(
                    [
                        {"type": "kodi_plugin", "priority": 10, "route": "split", "target": "plugin://plugin.video.therandtv/?action=play"}
                    ]
                )
            )

    def test_catchup_gets_longer_startup_timeout(self):
        self.assertEqual(25, startup_timeout_seconds({"family": "catchup"}))

    def test_vavoo_gets_proxy_recovery_grace(self):
        self.assertEqual(35, startup_timeout_seconds({"family": "vavoo"}))

    def test_other_keeps_fast_startup_timeout(self):
        self.assertEqual(12, startup_timeout_seconds({"family": "other"}))

    def test_cooldown_prefers_next_healthy_candidate(self):
        sources = [
            {"target": "https://example.test/a"},
            {"target": "https://example.test/b"},
            {"target": "https://example.test/c"},
        ]
        cooldowns = {source_key(sources[1]): 200.0}
        self.assertEqual(2, choose_next(sources, 0, cooldowns, now=100.0))

    def test_all_cooled_sources_are_not_hard_locked(self):
        sources = [
            {"target": "https://example.test/a"},
            {"target": "https://example.test/b"},
        ]
        cooldowns = {source_key(sources[1]): 200.0}
        self.assertEqual(1, choose_next(sources, 0, cooldowns, now=100.0))

    def test_mark_failed_sets_expiry(self):
        source = {"target": "https://example.test/a"}
        cooldowns = {}
        mark_failed(source, cooldowns, 300, now=100.0)
        self.assertEqual(400.0, cooldowns[source_key(source)])


if __name__ == "__main__":
    unittest.main()
