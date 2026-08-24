[English](README.md) | [Français](README.fr.md)

# TherandTV Routing

[![Tests](https://github.com/Therand90/service.therandtv.routing/actions/workflows/tests.yml/badge.svg)](https://github.com/Therand90/service.therandtv.routing/actions/workflows/tests.yml)
[![Repository policy checks](https://github.com/Therand90/service.therandtv.routing/actions/workflows/repository-policy.yml/badge.svg)](https://github.com/Therand90/service.therandtv.routing/actions/workflows/repository-policy.yml)

Companion Kodi service for [`plugin.video.therandtv`](https://github.com/Therand90/plugin.video.therandtv). It applies the route required by playback, supervises live-TV startup and moves to the next source when startup fails.

> [!IMPORTANT]
> This service is designed for Linux/LibreELEC-style systems where route changes are delegated to local shell scripts. It does not bundle a VPN configuration, credentials, WireGuard private keys or provider content.

## Responsibilities

- apply a temporary French/full-tunnel route when requested;
- restore the normal/split route for Belgian and ordinary Internet playback;
- acknowledge route activation before the plugin resolves playback;
- decode, validate and order live-TV failover candidates;
- supervise Kodi startup and try the next candidate when startup fails;
- keep failed candidates on a short cooldown to avoid immediate reuse;
- restore split routing at service startup and shutdown.

The service deliberately stops supervising a source once Kodi reports `onAVStarted`. Recovery of a stream that dies later is outside the current failover phase.

## Relationship with TherandTV

The video plugin and this service communicate locally through Kodi Home-window properties. The plugin writes the request data first and a unique request ID last. The service treats that request ID as the atomic hand-off marker and only writes the ready ID after route and source preparation is complete.

Install this service before installing `plugin.video.therandtv` when using ZIP packages manually. A future Therand Kodi repository can distribute both add-ons and resolve the dependency automatically.

## Routing model

The validated LibreELEC design uses two independent roles:

- a French egress WireGuard interface used only when a source requires a French public IP;
- an optional independent private tunnel used for private VPS services and never modified by the FR/normal switch.

In normal/split mode the regular LAN/Wi-Fi interface owns the default Internet route. The French tunnel may stay connected, but any default route injected through it is removed. In French/full mode the service executes the dedicated script that keeps the WireGuard endpoint reachable through the normal interface and then moves the default route to the French tunnel.

No personal network values are stored in this public repository. The reference scripts read their local values from:

```text
/storage/.config/therandtv-routing.conf
```

Start from the repository example:

```sh
cp scripts/therandtv-routing.conf.example /storage/.config/therandtv-routing.conf
```

Then edit the copy for the target machine. The example uses documentation-only addresses and must not be used unchanged.

## Runtime scripts

By default the Kodi service executes:

```text
/storage/.config/wg-fr-full-routing.sh
/storage/.config/wg-split-routing.sh
```

Reference implementations are provided in:

```text
scripts/wg-fr-full-routing.sh
scripts/wg-split-routing.sh
```

A typical LibreELEC installation copies the scripts and the configuration into `/storage/.config/`, makes the scripts executable and edits only the local configuration file:

```sh
cp scripts/wg-fr-full-routing.sh /storage/.config/wg-fr-full-routing.sh
cp scripts/wg-split-routing.sh /storage/.config/wg-split-routing.sh
cp scripts/therandtv-routing.conf.example /storage/.config/therandtv-routing.conf
chmod +x /storage/.config/wg-fr-full-routing.sh /storage/.config/wg-split-routing.sh
```

The repository copies are references for reconstruction and review. Updating this GitHub repository does not automatically replace files already copied to LibreELEC.

## Live-source failover

The service accepts a bounded compressed payload describing candidate sources. `failover.py` validates the payload size, decompressed size, source count, route values and target schemes before returning normalized candidates.

Current source families are ordered as:

1. Catch-up TV & More;
2. the local VAVOO proxy on loopback port `8899`;
3. other HTTP(S) or Kodi plugin targets.

The selected source receives a startup grace period appropriate to its family. The logical VAVOO proxy receives **50 seconds** so its own quality probes, media checks and internal variant failover can complete before the outer routing service moves to the next source. Generic sources remain at 12 seconds and Catch-up TV & More at 25 seconds. A logical VAVOO source is not put on a five-minute cooldown merely because its local proxy is still performing internal recovery when that outer timeout expires.

## Coexistence with `service.therand.autotrailer`

Kodi exposes one video player, so trailer playback emits the same `xbmc.Player` callbacks as live TV. The routing service ignores callbacks while the Therand trailer service explicitly owns the player through its Home-window ownership properties. A merely pending trailer does not suppress normal TherandTV observation.

This isolation changes neither the skin nor the trailer service; it only prevents unrelated trailer callbacks from validating or tearing down a TherandTV routing session.

## Security notes

The routing scripts change the operating system's default route and should be treated as privileged local configuration. Review them before copying them to a machine and keep `/storage/.config/therandtv-routing.conf` private.

Do not commit:

- WireGuard private keys;
- real VPN credentials;
- private service tokens;
- personal public endpoint addresses or internal topology details unless intentionally public.

The repository intentionally ships only a generic configuration example. For vulnerability reports, see [SECURITY.md](SECURITY.md).

## Development and validation

GitHub Actions run unit tests for the pure failover helpers, compile-check the Python files, parse the Kodi manifest and syntax-check the reference shell scripts. Workflows are pinned to full commit SHAs.

## Related project

- [TherandTV](https://github.com/Therand90/plugin.video.therandtv) — Kodi video gateway and failover client.

## License

This repository is distributed under the [MIT License](LICENSE).
