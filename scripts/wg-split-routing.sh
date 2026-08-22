#!/bin/sh

# TherandTV split / normal routing example
#
# Copy scripts/therandtv-routing.conf.example to:
#   /storage/.config/therandtv-routing.conf
# and adapt it before using this script on LibreELEC.

CONFIG_FILE="${THERANDTV_ROUTING_CONFIG:-/storage/.config/therandtv-routing.conf}"

NORMAL_IF=""
NORMAL_GW=""
WG_FR_IF="wg0"
WG_ENDPOINT_IP=""
WG_FR_PEER=""
WG_VPS_IF="wg-vps"
WG_VPS_HOST=""

if [ ! -r "$CONFIG_FILE" ]; then
    logger "TherandTV routing config missing: $CONFIG_FILE"
    exit 1
fi

# shellcheck disable=SC1090
. "$CONFIG_FILE"

[ -n "$NORMAL_IF" ] || { logger "TherandTV NORMAL_IF is missing"; exit 1; }
[ -n "$NORMAL_GW" ] || { logger "TherandTV NORMAL_GW is missing"; exit 1; }
[ -n "$WG_FR_IF" ] || { logger "TherandTV WG_FR_IF is missing"; exit 1; }

# Keep the French WireGuard endpoint outside the tunnel when configured.
if [ -n "$WG_ENDPOINT_IP" ]; then
    ip route replace "$WG_ENDPOINT_IP/32" via "$NORMAL_GW" dev "$NORMAL_IF" 2>/dev/null || true
fi

# ConnMan may inject a default route through the connected French tunnel.
# Split mode keeps that tunnel available but never allows it to own Internet.
if ip link show "$WG_FR_IF" >/dev/null 2>&1; then
    while ip route del default dev "$WG_FR_IF" 2>/dev/null; do
        :
    done

    if [ -n "$WG_FR_PEER" ]; then
        ip route replace "$WG_FR_PEER/32" dev "$WG_FR_IF" 2>/dev/null || true
    fi
fi

ip route replace default via "$NORMAL_GW" dev "$NORMAL_IF" || exit 1

# ConnMan can race with the commands above, so remove any re-injected French
# default route once more and reassert the normal route.
if ip link show "$WG_FR_IF" >/dev/null 2>&1; then
    while ip route del default dev "$WG_FR_IF" 2>/dev/null; do
        :
    done
fi

ip route replace default via "$NORMAL_GW" dev "$NORMAL_IF" || exit 1

# An optional independent private tunnel can keep one private host route without
# taking part in the French/normal Internet switch.
if [ -n "$WG_VPS_HOST" ] && ip link show "$WG_VPS_IF" >/dev/null 2>&1; then
    ip route replace "$WG_VPS_HOST/32" dev "$WG_VPS_IF" 2>/dev/null || true
fi

logger "TherandTV split routing applied"
exit 0
