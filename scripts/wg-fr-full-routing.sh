#!/bin/sh

# TherandTV French full routing example
#
# Copy scripts/therandtv-routing.conf.example to:
#   /storage/.config/therandtv-routing.conf
# and adapt it before using this script on LibreELEC.

CONFIG_FILE="${THERANDTV_ROUTING_CONFIG:-/storage/.config/therandtv-routing.conf}"

NORMAL_IF=""
NORMAL_GW=""
WG_FR_IF="wg0"
WG_CONNMAN_SERVICE=""
WG_ENDPOINT_IP=""
WG_FR_PEER=""

if [ ! -r "$CONFIG_FILE" ]; then
    logger "TherandTV routing config missing: $CONFIG_FILE"
    exit 1
fi

# shellcheck disable=SC1090
. "$CONFIG_FILE"

[ -n "$NORMAL_IF" ] || { logger "TherandTV NORMAL_IF is missing"; exit 1; }
[ -n "$NORMAL_GW" ] || { logger "TherandTV NORMAL_GW is missing"; exit 1; }
[ -n "$WG_FR_IF" ] || { logger "TherandTV WG_FR_IF is missing"; exit 1; }
[ -n "$WG_CONNMAN_SERVICE" ] || { logger "TherandTV WG_CONNMAN_SERVICE is missing"; exit 1; }
[ -n "$WG_ENDPOINT_IP" ] || { logger "TherandTV WG_ENDPOINT_IP is missing"; exit 1; }
[ -n "$WG_FR_PEER" ] || { logger "TherandTV WG_FR_PEER is missing"; exit 1; }

# Keep the public WireGuard endpoint reachable outside the tunnel.
ip route replace "$WG_ENDPOINT_IP/32" via "$NORMAL_GW" dev "$NORMAL_IF" || exit 1

# Reconnect the French tunnel only when needed.
if ! ip link show "$WG_FR_IF" >/dev/null 2>&1; then
    logger "TherandTV French tunnel absent; reconnecting $WG_CONNMAN_SERVICE"
    connmanctl connect "$WG_CONNMAN_SERVICE" >/dev/null 2>&1 || true

    COUNT=0
    while ! ip link show "$WG_FR_IF" >/dev/null 2>&1; do
        COUNT=$((COUNT + 1))
        if [ "$COUNT" -ge 20 ]; then
            logger "TherandTV French tunnel failed to appear"
            exit 1
        fi
        sleep 1
    done
fi

# Wait until the private peer inside the tunnel is reachable.
COUNT=0
while ! ping -c 1 -W 1 "$WG_FR_PEER" >/dev/null 2>&1; do
    COUNT=$((COUNT + 1))
    if [ "$COUNT" -ge 15 ]; then
        logger "TherandTV French tunnel present but peer unreachable"
        exit 1
    fi
    sleep 1
done

ip route replace "$WG_FR_PEER/32" dev "$WG_FR_IF" || exit 1

# Replace rather than delete first so a failure cannot intentionally leave Kodi
# without a default route between two commands.
ip route replace default dev "$WG_FR_IF" || exit 1

logger "TherandTV French full routing applied"
exit 0
