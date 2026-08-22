# -*- coding: utf-8 -*-
"""Pure helpers for TherandTV source failover.

This module deliberately has no Kodi imports so its validation and selection
logic can be unit-tested outside LibreELEC.
"""

from __future__ import annotations

import base64
import hashlib
import json
import time
import urllib.parse
import zlib


MAX_PAYLOAD_CHARS = 32768
MAX_DECOMPRESSED_BYTES = 65536
MAX_SOURCES = 32
SUPPORTED_ROUTES = {"fr", "split"}
SUPPORTED_TARGET_PREFIXES = ("plugin://", "http://", "https://")
SOURCE_FAMILY_ORDER = {"catchup": 0, "vavoo": 1, "other": 2}
CATCHUP_PREFIX = "plugin://plugin.video.catchuptvandmore/"
VAVOO_HOSTS = {"127.0.0.1", "localhost"}
VAVOO_PORT = 8899
DEFAULT_START_TIMEOUT_SECONDS = 12
CATCHUP_START_TIMEOUT_SECONDS = 25
VAVOO_START_TIMEOUT_SECONDS = 35


def _decode_compressed(payload):
    if not isinstance(payload, str) or not payload or len(payload) > MAX_PAYLOAD_CHARS:
        raise ValueError("payload failover absent ou trop volumineux")
    padding = "=" * (-len(payload) % 4)
    try:
        compressed = base64.urlsafe_b64decode((payload + padding).encode("ascii"))
    except Exception as exc:
        raise ValueError("payload failover base64 invalide") from exc

    inflater = zlib.decompressobj()
    try:
        raw = inflater.decompress(compressed, MAX_DECOMPRESSED_BYTES + 1)
        raw += inflater.flush(MAX_DECOMPRESSED_BYTES + 1 - len(raw))
    except Exception as exc:
        raise ValueError("payload failover compresse invalide") from exc
    if len(raw) > MAX_DECOMPRESSED_BYTES or inflater.unconsumed_tail:
        raise ValueError("payload failover decompresse trop volumineux")
    return raw


def source_family(source, target):
    declared = str(source.get("family") or "").strip().lower()
    if declared in SOURCE_FAMILY_ORDER:
        return declared
    if target.startswith(CATCHUP_PREFIX):
        return "catchup"
    try:
        parsed = urllib.parse.urlsplit(target)
        if (
            parsed.scheme in {"http", "https"}
            and parsed.hostname in VAVOO_HOSTS
            and parsed.port == VAVOO_PORT
        ):
            return "vavoo"
    except ValueError:
        pass
    return "other"


def startup_timeout_seconds(source):
    """Return the startup grace period appropriate for one source family."""
    family = str(source.get("family") or "").strip().lower()
    if family == "catchup":
        return CATCHUP_START_TIMEOUT_SECONDS
    if family == "vavoo":
        return VAVOO_START_TIMEOUT_SECONDS
    return DEFAULT_START_TIMEOUT_SECONDS


def decode_sources(payload):
    raw = _decode_compressed(payload)
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise ValueError("payload failover JSON invalide") from exc

    if not isinstance(data, dict) or data.get("v") != 1:
        raise ValueError("version de payload failover non supportee")
    raw_sources = data.get("sources")
    if not isinstance(raw_sources, list) or not raw_sources:
        raise ValueError("payload failover sans source")
    if len(raw_sources) > MAX_SOURCES:
        raise ValueError("payload failover contient trop de sources")

    normalized = []
    for position, source in enumerate(raw_sources):
        if not isinstance(source, dict):
            raise ValueError("source failover invalide")
        target = str(source.get("target") or "").strip()
        if not target.startswith(SUPPORTED_TARGET_PREFIXES):
            raise ValueError("cible failover non supportee")
        if target.startswith("plugin://plugin.video.therandtv/"):
            raise ValueError("boucle TherandTV refusee")
        route = str(source.get("route") or "split").strip().lower()
        if route not in SUPPORTED_ROUTES:
            raise ValueError("route failover invalide")
        try:
            priority = int(source.get("priority", 100))
        except (TypeError, ValueError):
            priority = 100
        family = source_family(source, target)
        normalized.append(
            (
                SOURCE_FAMILY_ORDER[family],
                priority,
                position,
                {
                    "type": str(source.get("type") or "unknown"),
                    "family": family,
                    "priority": priority,
                    "route": route,
                    "target": target,
                },
            )
        )

    normalized.sort(key=lambda item: (item[0], item[1], item[2]))
    return [item for _, _, _, item in normalized]


def source_key(source):
    target = str(source.get("target") or "")
    return hashlib.sha256(target.encode("utf-8")).hexdigest()


def prune_cooldowns(cooldowns, now=None):
    current = time.time() if now is None else float(now)
    expired = [key for key, until in cooldowns.items() if float(until) <= current]
    for key in expired:
        cooldowns.pop(key, None)


def choose_next(sources, after_index, cooldowns, now=None):
    """Choose the next source, preferring entries outside their cooldown.

    Cooldown is a preference rather than a hard lock: when every remaining
    source is cooled down, the next source is still retried so a channel can
    never become artificially unavailable for five minutes.
    """

    current = time.time() if now is None else float(now)
    prune_cooldowns(cooldowns, current)
    candidates = list(range(int(after_index) + 1, len(sources)))
    if not candidates:
        return None
    for index in candidates:
        if float(cooldowns.get(source_key(sources[index]), 0)) <= current:
            return index
    return candidates[0]


def mark_failed(source, cooldowns, seconds, now=None):
    current = time.time() if now is None else float(now)
    cooldowns[source_key(source)] = current + max(0.0, float(seconds))
