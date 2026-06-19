# Server Types

Proxima manages two types of server nodes. Each type has a dedicated Ansible playbook and set of roles.

## VPN Exit Node

**Purpose:** Provides clean IP addresses for traffic routing. Proxima clients connect through these servers to bypass geo-blocks and censorship.

**Servers:** ERG-TR, ERG-DE, ERG-FI, ERG-PL

**Components:**
| Component | Service | Port | Description |
|-----------|---------|------|-------------|
| outline-ss-server | `outline-ss-server` | 8388/tcp+udp | Go-based SS server with multi-key and prefix support |
| ssconf | `proxima-ssconf` | 8390/tcp | HTTPS server distributing SS config to clients |
| speedtest | `proxima-speedtest` | 8999/tcp | HTTPS speed test (download/upload/latency) |
| proxima-agent | `proxima-agent` | 5051/tcp | Universal management agent (HTTPS + API key) |
| AdGuard Home | Docker `adguardhome` | 53, 3000 | DNS-level ad blocking (optional) |
| AmneziaWG | Docker `amnezia-wg` | 80/udp | WireGuard-based VPN (installed via AmneziaVPN app) |
| Xray VLESS | Docker `xray` | 443/tcp | VLESS proxy (installed via AmneziaVPN app) |

**Ansible setup:**
```bash
ansible-playbook playbooks/setup-vpn-exit.yml -l <hostname>
```

**Role chain:** `common` → `outline-ss` → `ssconf` → `speedtest` → `proxima-agent` → `adguard` (optional)

---

## DPI Bypass Node

**Purpose:** Routes traffic through a DPI (Deep Packet Inspection) bypass system. Used in countries that actively filter HTTPS traffic (e.g., Russia).

**Servers:** ERG-RU (Raspberry Pi 5 on LAN)

**Components:**
| Component | Service | Port | Description |
|-----------|---------|------|-------------|
| shadowsocks-libev | `shadowsocks-libev-server@config` | 8388/tcp+udp | C-based SS server (Debian native package) |
| zapret nfqws2 | `zapret-nfqws2` | — | DPI bypass via NFQUEUE packet modification |
| zapret watchdog | `zapret-watchdog.timer` | — | Periodic check that iptables rules are active |
| proxima-agent | `proxima-agent` | 5051/tcp | Universal management agent (HTTPS + API key) |

**Ansible setup:**
```bash
ansible-playbook playbooks/setup-dpi-bypass.yml -l <hostname>
```

**Role chain:** `common` → `ss-server` → `zapret` → `proxima-agent`

---

## Why Two SS Implementations?

| Aspect | outline-ss-server (VPN Exit) | shadowsocks-libev (DPI Bypass) |
|--------|------------------------------|-------------------------------|
| Language | Go (Jigsaw/Google) | C (community) |
| Multi-key | Yes (config.yml key list) | No (single key per instance) |
| Prefix | Built-in prefix support | Via external config |
| Performance | Higher throughput, multi-core | Lower overhead, suitable for Pi5 |
| Install | Download binary | `apt install` |
| Reason | Production exit server, needs multi-key for future scaling | Debian native, works with zapret iptables, lightweight |

This is an intentional design decision — they serve fundamentally different purposes.

---

## Server Ownership Model

Exit servers are **shared resources**. Any Proxima instance (ERG, OFC, future sites) can use any exit server. The inventory is global; key/slot assignments are per-Proxima-instance.

DPI bypass nodes are **site-specific**. ERG-RU only serves the ERG network.
