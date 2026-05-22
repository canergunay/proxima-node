# proxima-node

One-command VPN exit node setup for [Proxima](https://github.com/canergunay/proxima) — a proxy & VPN management platform.

Sets up a complete VPN exit node with Outline Shadowsocks, speed test server, and AdGuard Home on a fresh Debian/Ubuntu VPS.

## What Gets Installed

| Component | Port | Purpose |
|-----------|------|---------|
| **Outline SS** | 8388/tcp+udp | Shadowsocks proxy server (chacha20-ietf-poly1305) |
| **ssconf** | 8390/tcp | HTTPS server for SS config distribution |
| **Speed Test** | 8999/tcp | HTTPS speed test server for Proxima |
| **AdGuard Home** | 53, 3000 | DNS-level ad blocking |
| **UFW Firewall** | — | Hardened firewall with only required ports |

**AmneziaWG + Xray** are installed separately via the [AmneziaVPN](https://amnezia.org) client app (ports 80/udp, 443/tcp).

## Quick Start

```bash
# SSH into your fresh Debian 12 VPS as root, then:
curl -sSL https://raw.githubusercontent.com/canergunay/proxima-node/main/setup.sh | bash
```

Or clone and run:

```bash
git clone https://github.com/canergunay/proxima-node.git
cd proxima-node
bash setup.sh
```

## Requirements

- **OS:** Debian 12 or Ubuntu 22+ (fresh install recommended)
- **RAM:** 1 GB minimum
- **Disk:** 10 GB minimum
- **Access:** Root SSH access

## Setup Flow

```
1. Get a VPS (Debian 12)
2. SSH in as root
3. Run the setup script → Outline SS, ssconf, speedtest, AdGuard Home installed
4. Use AmneziaVPN client to add AWG + Xray to the server
5. Add credentials to your Proxima instance
```

## Components

### Outline Shadowsocks (port 8388)

Native [outline-ss-server](https://github.com/Jigsaw-Code/outline-ss-server) binary with:
- `chacha20-ietf-poly1305` cipher
- TLS ClientHello prefix for DPI resistance
- TCP + UDP listeners

### ssconf Server (port 8390)

Lightweight Python HTTPS server that serves the SS configuration as JSON. Proxima clients fetch this URL to auto-configure their Shadowsocks connection. Protected by a random token.

### Speed Test Server (port 8999)

HTTPS server for measuring tunnel throughput from Proxima:
- `HEAD /speedtest/ping` — latency measurement
- `GET /speedtest/download?size=N` — download test (max 50 MB)
- `POST /speedtest/upload` — upload test (max 100 MB)
- `GET /speedtest/health` — health check (no auth)

Protected by Bearer token authentication.

### AdGuard Home (port 53, 3000)

DNS-level ad and tracker blocking via Docker container. After installation, complete the setup wizard at `http://<server-ip>:3000`.

### System Hardening

- **sysctl:** IP forwarding, TCP BBR, network hardening
- **SSH:** Key-only auth (if keys detected), root login via key only
- **UFW:** Deny-all incoming, only required ports open

## Configuration

All generated secrets are saved to `/opt/proxima-node/config.env`:

```
SERVER_IP=<auto-detected>
NODE_ID=proxima-node-<hostname>
SS_PASSWORD=<random>
SS_PREFIX=FgMBAgABAAH8AwM=
SSCONF_TOKEN=<random>
SPEEDTEST_API_KEY=<random>
```

## Architecture

```
┌─────────────────────────────────────────────┐
│                  VPS Server                  │
│                                              │
│  ┌──────────────┐  ┌──────────────────────┐ │
│  │ AmneziaWG    │  │ Outline SS           │ │
│  │ (Docker)     │  │ (native binary)      │ │
│  │ :80/udp      │  │ :8388/tcp+udp        │ │
│  └──────────────┘  └──────────────────────┘ │
│  ┌──────────────┐  ┌──────────────────────┐ │
│  │ Xray VLESS   │  │ ssconf server        │ │
│  │ (Docker)     │  │ (Python/systemd)     │ │
│  │ :443/tcp     │  │ :8390/tcp            │ │
│  └──────────────┘  └──────────────────────┘ │
│  ┌──────────────┐  ┌──────────────────────┐ │
│  │ AdGuard Home │  │ Speed Test server    │ │
│  │ (Docker)     │  │ (Python/systemd)     │ │
│  │ :53, :3000   │  │ :8999/tcp            │ │
│  └──────────────┘  └──────────────────────┘ │
│                                              │
│  UFW Firewall ─ deny all except above ports  │
└─────────────────────────────────────────────┘
```

## Tested Providers

| Provider | Location | ERG Latency | Notes |
|----------|----------|-------------|-------|
| BlueVPS | Warsaw, PL | 31ms | NVMe-bKVM 1024, $6/mo |
| Hetzner | Germany | 43ms | Good but IPs throttled in Russia |
| Aeza | Finland | — | Cooperates with RKN, not recommended |

## License

MIT
