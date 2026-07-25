# Proxy Gateway

The Proxy Gateway provides a stable HTTP proxy endpoint at port 8080 for Docker containers and other services that cannot use DNS Mode transparent routing. It acts as a single, consistent proxy address that routes traffic through whichever VPN tunnel slot is currently selected.

---

## Overview

Proxima's DNS Mode works by intercepting DNS queries and marking resolved IPs for policy routing at the network level. This is transparent for devices on the LAN — they don't need any configuration. However, Docker containers running on bridge networks cannot benefit from this transparent routing because their traffic doesn't pass through the host's nftables rules.

The Proxy Gateway solves this by providing an HTTP proxy at `proxima:8080` that any container on the Docker network can use. When the upstream slot changes in the UI, all container traffic immediately routes through the new tunnel — no container restarts required.

---

## The Problem

### Why Containers Can't Use DNS Mode

DNS Mode relies on the following chain:

```
Client DNS query → dnsmasq (host network, port 53)
    → nftables nftset population
Client TCP connection → nftables mark → policy routing → tun0
    → tun2socks → AWG tunnel → Internet
```

This works for LAN devices because their traffic enters the host's network stack where nftables rules operate. Docker containers on bridge networks, however, have a different traffic path:

```
Container traffic → Docker bridge (docker0 / br-xxxx)
    → NAT (MASQUERADE) → host interface → Internet
```

The container's traffic is NATed by Docker before it reaches the host's nftables rules. The source IP becomes the Docker bridge gateway (e.g., 172.18.0.1), and the traffic path bypasses the nftset matching and fwmark routing entirely.

### Without Proxy Gateway

Without the Proxy Gateway, each container would need to be configured with a direct proxy connection to a specific slot:

```yaml
# This breaks when the slot changes or fails over
environment:
  - HTTP_PROXY=socks5h://awg-client-slot-6:1080
```

This approach has several problems:

- **Tight coupling** — The container config points to a specific tunnel container
- **No failover** — If the tunnel fails, the container loses connectivity until manually reconfigured
- **No centralized control** — Changing the upstream slot requires reconfiguring every container
- **Protocol mismatch** — Some apps don't support SOCKS5, only HTTP proxies

---

## How It Works

The Proxy Gateway runs as an HTTP proxy server inside the Proxima container on port 8080.

### Request Flow

```
Container (e.g., bazarr)
    │
    │  HTTP CONNECT / HTTP request
    ▼
Proxy Gateway (proxima:8080)
    │
    │  Forward via upstream slot's SOCKS5/HTTP proxy
    ▼
Tunnel container (e.g., awg-client-slot-6:1080)
    │
    │  Encrypted tunnel
    ▼
VPN exit → Internet
```

### Key Properties

| Property | Description |
|----------|-------------|
| **Listen address** | `0.0.0.0:8080` inside the Proxima container (host port configurable via `GATEWAY_HOST_PORT` in `.env`, default `8180`) |
| **Protocol** | HTTP proxy (CONNECT method for HTTPS, plain proxy for HTTP) |
| **Upstream** | Configurable slot — routes through that slot's SOCKS5 proxy |
| **Failover** | Follows the slot's failover — when the slot rotates configs, the proxy gateway routes through the new tunnel automatically |
| **Hot-swap** | Changing the upstream slot in the UI takes effect immediately for new connections |

### Stable Address

The critical advantage is that `proxima:8080` never changes. Regardless of which slot is active, which config is in use, or whether failover has occurred, containers always connect to the same address. The Proxy Gateway handles upstream routing internally.

```
Before failover:  container → proxima:8080 → slot-6 (config A) → VPN exit 1
After failover:   container → proxima:8080 → slot-6 (config B) → VPN exit 2
Slot change:      container → proxima:8080 → slot-7             → VPN exit 3
```

In all three cases, the container's proxy configuration remains `http://proxima:8080`.

---

## Configuration

### Settings Page

The Proxy Gateway is configured from the **Settings** page in the Proxima UI under the **Proxy Gateway** section.

| Setting | Description |
|---------|-------------|
| **Enabled** | Toggle the proxy gateway on or off |
| **Upstream slot** | Which slot to route container traffic through |
| **Status** | Current state: Running, Stopped, or Error |
| **Proxy address** | `http://proxima:8080` — displayed for easy copy |

### Selecting an Upstream Slot

Choose any active slot as the upstream. The dropdown shows all enabled slots with their current health status:

- **slot-6 (AWG)** — Healthy, IP: 89.105.208.130
- **slot-7 (AWG)** — Healthy, IP: 185.22.155.44
- **slot-1 (SS)** — Healthy, IP: 45.67.89.10

The selected slot determines which VPN tunnel all proxied container traffic uses. Changing the slot takes effect immediately — existing long-lived connections continue through the previous slot, but new connections use the updated slot.

### proxima-config.json

The proxy gateway configuration is stored in the main config file:

```json
{
  "settings": {
    "proxy_gateway": {
      "enabled": true,
      "upstream_slot": 6
    }
  }
}
```

---

## Configuring Containers

Containers need to be told to use the proxy gateway. There are two methods depending on the application.

### Method 1: Environment Variables

The most common approach. Add `HTTP_PROXY` and `HTTPS_PROXY` environment variables to the container's compose definition:

```yaml
services:
  my-app:
    image: my-app:latest
    environment:
      - HTTP_PROXY=http://proxima:8080
      - HTTPS_PROXY=http://proxima:8080
      - NO_PROXY=localhost,127.0.0.1,192.168.0.0/16,10.0.0.0/8,172.16.0.0/12
    networks:
      - proxy_net
```

Key points:

- Both `HTTP_PROXY` and `HTTPS_PROXY` should be set (some libraries check one, some check the other)
- `NO_PROXY` should include local/private ranges to avoid proxying internal traffic
- The container must be on the `proxy_net` Docker network to reach the Proxima container
- The protocol is `http://` even for `HTTPS_PROXY` — the proxy uses HTTP CONNECT for TLS tunneling

### Method 2: Application-Level Proxy Settings

Some applications have their own proxy configuration that overrides or ignores environment variables. These need to be configured within the application itself.

Refer to the application's documentation for the correct setting location. Common patterns:

- Configuration file (JSON, YAML, TOML)
- Web UI settings page
- API endpoint for runtime configuration

### Network Requirement

Containers using the proxy gateway must be able to reach the Proxima container. This means they need to be on the same Docker network:

```yaml
networks:
  proxy_net:
    external: true

services:
  my-app:
    networks:
      - proxy_net
```

The `proxy_net` network is created by Proxima's docker-compose and declared as external in other compose files.

---

## Example Configurations

### Bazarr

Bazarr (subtitle downloader for Sonarr/Radarr) respects the `HTTP_PROXY` environment variable:

```yaml
services:
  bazarr:
    image: lscr.io/linuxserver/bazarr:latest
    container_name: bazarr
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=Europe/Moscow
      - HTTP_PROXY=http://proxima:8080
      - HTTPS_PROXY=http://proxima:8080
      - NO_PROXY=localhost,127.0.0.1,192.168.0.0/16,sonarr,radarr
    networks:
      - proxy_net
      - media_net
```

Note that `sonarr` and `radarr` are in `NO_PROXY` because Bazarr communicates with them over the internal Docker network and those requests should not be proxied.

### Jellyfin

Jellyfin (media server) uses the environment variable for plugin downloads and metadata fetching:

```yaml
services:
  jellyfin:
    image: jellyfin/jellyfin:latest
    container_name: jellyfin
    environment:
      - HTTP_PROXY=http://proxima:8080
      - HTTPS_PROXY=http://proxima:8080
      - NO_PROXY=localhost,127.0.0.1,192.168.0.0/16
    networks:
      - proxy_net
```

Jellyfin needs proxy access primarily for:
- Downloading metadata from TMDB, TVDB
- Plugin repository access
- Subtitle downloads from OpenSubtitles

### LiteLLM

LiteLLM (LLM API gateway) routes API calls to OpenAI, Anthropic, and other providers through the proxy:

```yaml
services:
  litellm:
    image: ghcr.io/berriai/litellm:main-latest
    container_name: litellm
    environment:
      - HTTP_PROXY=http://proxima:8080
      - HTTPS_PROXY=http://proxima:8080
      - NO_PROXY=localhost,127.0.0.1,192.168.0.0/16
    networks:
      - proxy_net
```

This ensures that LLM API calls go through the VPN tunnel, which is necessary when AI services are blocked or rate-limited by region.

### Seerr (Overseerr/Jellyseerr)

Seerr is a special case. It does **not** respect the `HTTP_PROXY` environment variable. Instead, proxy settings must be configured in its settings file:

**Important:** The proxy configuration is under `network.proxy`, NOT at the top level.

```json
{
  "network": {
    "proxy": {
      "enabled": true,
      "hostname": "proxima",
      "port": 8080,
      "type": "http"
    }
  }
}
```

The settings file is typically at `/app/config/settings.json` inside the container. You can also configure this from the Seerr web UI under Settings > Network.

```yaml
services:
  seerr:
    image: fallenbagel/jellyseerr:latest
    container_name: seerr
    volumes:
      - ./seerr-config:/app/config
    networks:
      - proxy_net
```

---

## Security

### No Authentication

The Proxy Gateway does not require authentication. This is a deliberate design choice:

- The proxy is only accessible from the Docker bridge network and the local LAN
- It is not exposed to the internet (no port mapping to host in docker-compose)
- All consumers are trusted internal services
- Adding proxy authentication would require updating every container's proxy URL with credentials

### Network Isolation

The proxy listens on port 8080 inside the Proxima container. It is reachable only from:

1. **Docker bridge network** (`proxy_net`) — other containers on the same network
2. **Host network** — the server itself (via Docker's port mapping, if configured)
3. **LAN** — other devices on the local network (only if port 8080 is mapped to the host)

By default, port 8080 is mapped to the host so LAN devices can also use it as an explicit HTTP proxy. If you want to restrict access to Docker containers only, remove the host port mapping from docker-compose.

### No TLS

The proxy gateway uses plain HTTP. Since it operates entirely within the Docker network or LAN, TLS is unnecessary. The proxied connections themselves (HTTPS traffic from containers) remain encrypted end-to-end — the proxy uses the CONNECT method for TLS tunneling, meaning it never decrypts the container's HTTPS traffic.

---

## Limitations

### HTTP Proxy Only

The Proxy Gateway provides an HTTP proxy interface. It does not expose a SOCKS5 endpoint. Most containerized applications support HTTP proxies, but some tools (e.g., certain CLI utilities or custom applications) may require SOCKS5. For those cases, you can connect directly to the slot's SOCKS5 proxy (e.g., `awg-client-slot-6:1080`), though you lose the hot-swap and failover benefits.

### No Per-Container Slot Selection

All containers share the same upstream slot. You cannot route one container through slot-6 and another through slot-7 via the proxy gateway. If you need per-container slot selection, configure each container to connect directly to the specific slot's proxy endpoint.

### No Bandwidth Shaping

Container traffic through the proxy gateway is not subject to DNS Mode's per-group bandwidth shaping (tc/HTB). Bandwidth shaping operates at the nftables/tc level on the host network, and proxied traffic enters the tunnel through a different path. Container traffic is effectively unmetered relative to the per-group limits.

### HTTP_PROXY Not Universal

Some applications ignore the `HTTP_PROXY` environment variable entirely and require app-specific proxy configuration. Each application's documentation should be checked. Known examples:

| Application | Proxy Method |
|-------------|-------------|
| Most Python/Node.js apps | `HTTP_PROXY` env var |
| Seerr / Jellyseerr | `network.proxy` in settings.json |
| Java applications | `-Dhttp.proxyHost` / `-Dhttp.proxyPort` JVM flags |
| Go applications | `HTTP_PROXY` env var (standard library) |
| .NET applications | System.Net proxy settings or env var |

### Connection Persistence on Slot Change

When the upstream slot changes, existing TCP connections through the old slot continue until they complete or timeout. Only new connections use the updated slot. For most applications this is seamless, but long-lived connections (WebSockets, streaming downloads) may need to reconnect to use the new slot.

---

## Troubleshooting

### Container Can't Reach Proxy

1. Verify the container is on `proxy_net`: `docker network inspect proxy_net`
2. Check that the Proxima container is running: `docker ps | grep proxima`
3. Test connectivity from the container: `docker exec my-app curl -x http://proxima:8080 http://httpbin.org/ip`

### Proxy Returns Connection Errors

1. Check the upstream slot health on the Dashboard
2. Verify the slot's tunnel container is running: `docker ps | grep awg-client`
3. Check Proxima logs for proxy gateway errors: `docker logs proxima | grep proxy`

### Traffic Not Going Through VPN

1. Verify the proxy gateway upstream slot in Settings
2. Test the proxy exit IP: `docker exec my-app curl -x http://proxima:8080 http://httpbin.org/ip`
3. Compare the returned IP with the slot's expected exit IP on the Dashboard

### Application Ignoring Proxy

1. Check if the app supports `HTTP_PROXY` environment variable
2. Look for app-specific proxy settings in the application's config file or web UI
3. Some apps only read proxy settings at startup — restart the container after setting env vars
4. Verify env vars are set correctly: `docker exec my-app env | grep -i proxy`

---

## Architecture Comparison

Understanding when to use DNS Mode vs. Proxy Gateway:

| Aspect | DNS Mode (LAN devices) | Proxy Gateway (containers) |
|--------|----------------------|---------------------------|
| **Setup** | Transparent (set DNS + gateway) | Explicit (set HTTP_PROXY) |
| **Routing granularity** | Per-domain (via groups) | All-or-nothing per container |
| **Bandwidth shaping** | Per-group tc/HTB limits | Not available |
| **Failover** | Automatic, per-slot | Inherits from upstream slot |
| **Slot selection** | Per-group (different groups, different slots) | Single slot for all containers |
| **Protocol support** | All TCP (transparent) | HTTP/HTTPS only |
| **QUIC handling** | REJECT (forces TCP fallback) | N/A (HTTP proxy, no UDP) |

For LAN devices (desktops, phones, tablets), DNS Mode is always preferred. The Proxy Gateway exists specifically for the Docker container use case where DNS Mode is not possible.

> **See also:** [Architecture](/docs/architecture.md) for the overall system design, [ProximaVPN](/docs/proximavpn.md) for mobile device access
