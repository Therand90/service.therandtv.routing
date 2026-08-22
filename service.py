# -*- coding: utf-8 -*-
"""TherandTV routing and source-failover service.

Communication with the video addon uses properties on Kodi's Home window.
The legacy FR wrapper remains supported.  Playlist live-TV entries can also
submit an ordered source payload; the service chooses the first candidate,
applies the requested route, watches Kodi startup events and tries the next
source when startup fails.
"""

import os
import subprocess
import time

import xbmc
import xbmcaddon
import xbmcgui

from failover import choose_next, decode_sources, mark_failed, startup_timeout_seconds


ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo("id")
HOME = xbmcgui.Window(10000)

FR_SCRIPT = "/storage/.config/wg-fr-full-routing.sh"
SPLIT_SCRIPT = "/storage/.config/wg-split-routing.sh"
LEGACY_START_TIMEOUT_SECONDS = 25
FAILOVER_COOLDOWN_SECONDS = 300

FAILOVER_SESSION = None
COOLDOWNS = {}


def log(message, level=xbmc.LOGINFO):
    xbmc.log(f"[{ADDON_ID}] {message}", level)


def run_script(path):
    """Execute one routing script synchronously and report success."""
    if not os.path.isfile(path):
        log(f"Routing script not found: {path}", xbmc.LOGERROR)
        return False

    try:
        completed = subprocess.run(
            ["/bin/sh", path],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except Exception as exc:
        log(f"Could not execute {path}: {exc}", xbmc.LOGERROR)
        return False

    if completed.returncode != 0:
        log(
            f"Script failed ({completed.returncode}): {path}; stderr={completed.stderr.strip()}",
            xbmc.LOGERROR,
        )
        return False

    log(f"Routing script completed: {path}")
    return True


def clear_legacy_properties():
    for name in (
        "therandtv.routing.request",
        "therandtv.routing.request_id",
        "therandtv.routing.ready_id",
        "therandtv.routing.active",
        "therandtv.routing.playback_started",
    ):
        HOME.clearProperty(name)


def clear_play_response():
    for name in (
        "therandtv.play.ready_id",
        "therandtv.play.target",
        "therandtv.play.selected_index",
        "therandtv.play.selected_priority",
        "therandtv.play.error_id",
        "therandtv.play.error",
    ):
        HOME.clearProperty(name)


def clear_play_request():
    for name in (
        "therandtv.play.request_id",
        "therandtv.play.channel",
        "therandtv.play.payload",
    ):
        HOME.clearProperty(name)
    clear_play_response()


def apply_route(route, reason):
    """Apply one route without destroying an active failover request."""
    HOME.clearProperty("therandtv.routing.playback_started")
    if route == "fr":
        log(f"Applying FR routing: {reason}")
        if not run_script(FR_SCRIPT):
            return False
        HOME.setProperty("therandtv.routing.active", "fr")
        return True

    log(f"Applying split routing: {reason}")
    if not run_script(SPLIT_SCRIPT):
        return False
    HOME.clearProperty("therandtv.routing.active")
    return True


def restore_split(reason):
    log(f"Restoring split routing: {reason}")
    run_script(SPLIT_SCRIPT)
    clear_legacy_properties()


def set_play_error(request_id, message):
    HOME.setProperty("therandtv.play.error", str(message))
    HOME.setProperty("therandtv.play.error_id", request_id)


def set_play_ready(request_id, session, source):
    HOME.setProperty("therandtv.play.target", source["target"])
    HOME.setProperty("therandtv.play.selected_index", str(session["index"]))
    HOME.setProperty("therandtv.play.selected_priority", str(source["priority"]))
    # ready_id is written last so the plugin never observes a half-filled reply.
    HOME.setProperty("therandtv.play.ready_id", request_id)


def prepare_next_source(session, after_index, reason):
    """Select the next usable source and apply its route."""
    index = int(after_index)
    while True:
        next_index = choose_next(session["sources"], index, COOLDOWNS)
        if next_index is None:
            return None
        source = session["sources"][next_index]
        route_reason = (
            f"failover {session['channel']} source {next_index + 1}/"
            f"{len(session['sources'])} ({reason})"
        )
        if apply_route(source["route"], route_reason):
            session["index"] = next_index
            session["attempt_started"] = time.monotonic()
            session["retry_requested"] = None
            timeout_seconds = startup_timeout_seconds(source)
            log(
                f"Failover {session['channel']}: prepared source "
                f"{next_index + 1}/{len(session['sources'])}, "
                f"priority={source['priority']}, type={source['type']}, "
                f"family={source['family']}, route={source['route']}, timeout={timeout_seconds}s"
            )
            return source

        log(
            f"Failover {session['channel']}: route activation failed for "
            f"source {next_index + 1}",
            xbmc.LOGWARNING,
        )
        mark_failed(source, COOLDOWNS, FAILOVER_COOLDOWN_SECONDS)
        index = next_index


def begin_failover_request(request_id, channel, payload):
    global FAILOVER_SESSION

    clear_play_response()
    try:
        sources = decode_sources(payload)
    except Exception as exc:
        log(f"Invalid failover payload for {channel}: {exc}", xbmc.LOGERROR)
        restore_split("invalid failover payload")
        set_play_error(request_id, str(exc))
        FAILOVER_SESSION = None
        return

    session = {
        "id": request_id,
        "channel": channel or "unknown",
        "sources": sources,
        "index": -1,
        "attempt_started": None,
        "retry_requested": None,
    }
    source = prepare_next_source(session, -1, "initial request")
    if source is None:
        restore_split("no failover source available")
        set_play_error(request_id, "Aucune source disponible")
        FAILOVER_SESSION = None
        return

    FAILOVER_SESSION = session
    set_play_ready(request_id, session, source)


def request_retry(reason):
    if FAILOVER_SESSION is None:
        return False
    if FAILOVER_SESSION.get("retry_requested") is None:
        FAILOVER_SESSION["retry_requested"] = str(reason)
        log(
            f"Failover {FAILOVER_SESSION['channel']}: retry requested ({reason})",
            xbmc.LOGWARNING,
        )
    return True


def exhaust_failover(reason):
    global FAILOVER_SESSION
    channel = FAILOVER_SESSION.get("channel", "unknown") if FAILOVER_SESSION else "unknown"
    log(f"Failover {channel}: all sources failed ({reason})", xbmc.LOGERROR)
    FAILOVER_SESSION = None
    clear_play_request()
    restore_split("all failover sources failed")
    xbmcgui.Dialog().notification(
        "TherandTV",
        f"Aucune source disponible pour {channel}",
        xbmcgui.NOTIFICATION_ERROR,
        6000,
    )


def advance_failover(player, reason):
    """Mark the current attempt failed and start the next candidate."""
    global FAILOVER_SESSION
    session = FAILOVER_SESSION
    if session is None:
        return

    current_index = int(session.get("index", -1))
    if 0 <= current_index < len(session["sources"]):
        current = session["sources"][current_index]

        # A logical VAVOO group already owns technical variant health, retries
        # and quarantine. An outer startup timeout can simply mean the proxy is
        # still recovering a .b/.c/.s variant, so do not blacklist the whole
        # logical group for five minutes in that case.
        if current.get("family") == "vavoo" and str(reason).strip().lower() == "startup timeout":
            log(
                f"Failover {session['channel']}: source {current_index + 1} "
                "VAVOO startup timeout; keeping logical group eligible",
                xbmc.LOGWARNING,
            )
        else:
            mark_failed(current, COOLDOWNS, FAILOVER_COOLDOWN_SECONDS)
            log(
                f"Failover {session['channel']}: source {current_index + 1} "
                f"failed; cooldown {FAILOVER_COOLDOWN_SECONDS}s",
                xbmc.LOGWARNING,
            )

    source = prepare_next_source(session, current_index, reason)
    if source is None:
        exhaust_failover(reason)
        return

    # Player callbacks can request retries.  Actual playback is started from the
    # service loop rather than recursively from a callback.
    xbmc.sleep(250)
    item = xbmcgui.ListItem(path=source["target"])
    item.setProperty("IsPlayable", "true")
    log(
        f"Failover {session['channel']}: opening fallback source "
        f"{session['index'] + 1}/{len(session['sources'])}"
    )
    player.play(source["target"], item)


class RoutingPlayer(xbmc.Player):
    """Observe TherandTV playback without reacting to our trailer player."""

    @staticmethod
    def _trailer_owns_player():
        """Return True while service.therand.autotrailer owns Kodi playback.

        Kodi exposes a single video player.  The trailer service therefore
        produces the same player callbacks as live TV.  Those callbacks are
        unrelated to TherandTV routing and must not validate a failover attempt
        or restore the WireGuard route.

        Pending is deliberately not checked: during the trailer delay no
        trailer owns the player yet, so normal TherandTV playback must continue
        to be observed.
        """
        for prop in (
            "ServiceTherand.Trailer.Owner",
            "ServiceTherand.Trailer.Active",
            "ServiceTherand.Trailer.Stopping",
        ):
            value = HOME.getProperty(prop).strip().lower()
            if value not in ("", "0", "false", "no", "off"):
                return True
        return False

    def _restore_if_active(self, reason):
        if HOME.getProperty("therandtv.routing.active") == "fr":
            restore_split(reason)

    def onAVStarted(self):
        global FAILOVER_SESSION

        if self._trailer_owns_player():
            log("Ignoring AVStarted from Therand trailer")
            return

        HOME.setProperty("therandtv.routing.playback_started", "1")
        if FAILOVER_SESSION is not None:
            session = FAILOVER_SESSION
            index = int(session.get("index", -1))
            source = session["sources"][index] if 0 <= index < len(session["sources"]) else {}
            log(
                f"Failover {session['channel']}: playback started with "
                f"source {index + 1}/{len(session['sources'])}, "
                f"priority={source.get('priority')}, type={source.get('type')}"
            )
            # Phase 1 deliberately stops supervising after successful startup.
            # A stream that dies later is not auto-reopened yet.
            FAILOVER_SESSION = None
            clear_play_request()
        elif HOME.getProperty("therandtv.routing.active") == "fr":
            log("French playback started")

    def onPlayBackStopped(self):
        if self._trailer_owns_player():
            log("Ignoring PlaybackStopped from Therand trailer")
            return

        if FAILOVER_SESSION is not None:
            log("Playback stopped while failover startup is pending; waiting for error/timeout")
            return
        self._restore_if_active("playback stopped")

    def onPlayBackEnded(self):
        if self._trailer_owns_player():
            log("Ignoring PlaybackEnded from Therand trailer")
            return

        if FAILOVER_SESSION is not None:
            request_retry("playback ended before AV start")
            return
        self._restore_if_active("playback ended")

    def onPlayBackError(self):
        if self._trailer_owns_player():
            log("Ignoring PlaybackError from Therand trailer")
            return

        if request_retry("playback error"):
            return
        self._restore_if_active("playback error")


class RoutingMonitor(xbmc.Monitor):
    pass


def main():
    global FAILOVER_SESSION

    monitor = RoutingMonitor()
    player = RoutingPlayer()

    # Never allow stale full-tunnel or failover state to survive a Kodi restart.
    FAILOVER_SESSION = None
    clear_play_request()
    restore_split("service startup")

    legacy_active_since = None
    handled_route_request_id = None
    handled_play_request_id = None

    while not monitor.abortRequested():
        # Legacy request used by TherandTV replay and directory-wrapped live items.
        request = HOME.getProperty("therandtv.routing.request")
        request_id = HOME.getProperty("therandtv.routing.request_id")
        if request == "fr" and request_id and request_id != handled_route_request_id:
            handled_route_request_id = request_id
            HOME.clearProperty("therandtv.routing.playback_started")
            if apply_route("fr", f"legacy request {request_id}"):
                HOME.setProperty("therandtv.routing.ready_id", request_id)
                legacy_active_since = time.monotonic()
                log(f"French route ready for request {request_id}")
            else:
                restore_split("FR route activation failed")

        # New channel request.  The plugin writes payload/channel first and the
        # request id last, making request_id the atomic hand-off marker.
        play_request_id = HOME.getProperty("therandtv.play.request_id")
        if play_request_id and play_request_id != handled_play_request_id:
            handled_play_request_id = play_request_id
            channel = HOME.getProperty("therandtv.play.channel")
            payload = HOME.getProperty("therandtv.play.payload")
            begin_failover_request(play_request_id, channel, payload)

        if FAILOVER_SESSION is not None:
            retry_reason = FAILOVER_SESSION.get("retry_requested")
            attempt_started = FAILOVER_SESSION.get("attempt_started")
            if retry_reason:
                advance_failover(player, retry_reason)
            elif attempt_started is not None:
                index = int(FAILOVER_SESSION.get("index", -1))
                source = (
                    FAILOVER_SESSION["sources"][index]
                    if 0 <= index < len(FAILOVER_SESSION["sources"])
                    else {}
                )
                timeout_seconds = startup_timeout_seconds(source)
                if time.monotonic() - attempt_started >= timeout_seconds:
                    advance_failover(player, "startup timeout")

        active = HOME.getProperty("therandtv.routing.active") == "fr"
        started = HOME.getProperty("therandtv.routing.playback_started") == "1"
        if (
            FAILOVER_SESSION is None
            and active
            and not started
            and legacy_active_since is not None
            and time.monotonic() - legacy_active_since >= LEGACY_START_TIMEOUT_SECONDS
        ):
            restore_split("legacy playback startup timeout")
            legacy_active_since = None

        if not active:
            legacy_active_since = None

        if monitor.waitForAbort(0.25):
            break

    FAILOVER_SESSION = None
    clear_play_request()
    restore_split("service shutdown")


if __name__ == "__main__":
    main()
