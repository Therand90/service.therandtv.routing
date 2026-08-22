[English](SECURITY.md) | [Français](SECURITY.fr.md)

# Security policy

## Reporting a vulnerability

Use GitHub private vulnerability reporting when it is enabled. Do not publish VPN credentials, WireGuard keys, private network topology, access tokens or exploit details in a public issue.

For ordinary routing or playback bugs, open a normal issue with the Kodi version, LibreELEC/Linux version, add-on versions and a redacted log excerpt.

## Privileged local behavior

This add-on executes two local shell scripts synchronously. Those scripts may change the host default route and interact with ConnMan/WireGuard. Treat the files under `/storage/.config/` as privileged local configuration and restrict who can modify them.

The repository intentionally contains only generic reference scripts and a documentation-only configuration example. Real endpoint addresses, VPN identifiers, private keys and local infrastructure values belong only in the local copy.

## Failover input validation

The pure `failover.py` helpers bound compressed and decompressed payload size, limit the source count, validate allowed route names and accept only Kodi plugin or HTTP(S) targets. Looping back into `plugin.video.therandtv` is rejected.

## Sensitive data

Never commit:

- WireGuard private keys or complete client configurations;
- VPN usernames, passwords or tokens;
- private playlist credentials or cookies;
- personal infrastructure details that are not intentionally public.

Redact these values from logs before sharing them.
