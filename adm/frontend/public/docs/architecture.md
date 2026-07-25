# Architecture

This document describes the system architecture of Proxima, including the slot system, group system, Docker containers, networks, and how the data plane works.

---

## System Overview

Proxima has two planes:

- **Management plane** — The Flask API + React frontend that handles configuration, health checks, failover, and user interaction
- **Data plane** — The actual traffic routing infrastructure (dnsmasq, nftables, tun2socks, tunnels) that operates independently

The data plane continues to function even if the management plane (Proxima container) crashes. Only the UI, health checks, failover, and proxy gateway are affected.

---

## Slot System

Proxima organizes VPN tunnels into numbered **slots**. Each slot represents one tunnel endpoint with its own health state, key pool, and failover cycle.

```
slot-5  →  DIRECT (no container, no port)
slot-6  →  awg-client-slot-6    (SOCKS5 port 1086)   [AmneziaWG]
slot-7  →  awg-client-slot-7    (SOCKS5 port 1087)   [AmneziaWG]
slot-8  →  outline-client-slot-8 (SOCKS5 port 1088)   [Shadowsocks/Outline]
slot-9  →  xray-client-slot-9   (SOCKS5 port 1089)   [VLESS+Reality]
```

Slots are dynamically created from the UI — there are no fixed slot numbers. Each slot has a `type` field that determines which container image runs. All container types expose SOCKS5 on port 1080 inside the container (mapped to the slot's configured `socks_port` on the host).

Each active slot has:

- A **tunnel client container** — AWG, Outline, Xray, or zapret
- A **key/config pool** — List of credentials for failover rotation
- An **active key/config** — Currently used credential
- **Health state** — Last IP, check timestamps, failover count
- **Optional via_slot** — Tunnel chaining parent (see below)

### Slot Types

| Type | Container | Protocol | Use Case |
|------|-----------|----------|----------|
| `awg` | `awg-client-*` | AmneziaWG | Obfuscated WireGuard tunnel |
| `outline` | `outline-client-*` | Shadowsocks (Outline) | TCP-only tunnel with optional prefix obfuscation |
| `xray` | `xray-client-*` | VLESS+Reality | TLS-camouflaged tunnel (mimics normal HTTPS) |
| `zapret` | `zapret-client-*` | zapret/nfqws2 | DPI bypass without VPN (packet manipulation) |
| `direct` | — | None | Bypass proxy, go direct |

### AmneziaWG Slots

AmneziaWG provides WireGuard with anti-DPI obfuscation headers. The AWG container runs:
- `awg-quick up` to establish the tunnel
- `microsocks` as a SOCKS5 proxy exposed on port 1080

In DNS Mode, tun2socks connects to the AWG SOCKS5 proxy to route intercepted traffic through the tunnel.

AWG config sanitization on write removes `DNS`, `Table`, `PostUp`, `PostDown` directives and injects `Table = off` to prevent routing table conflicts inside the container.

### VLESS+Reality (Xray) Slots

Xray provides VLESS protocol with Reality TLS camouflage. Traffic appears as normal HTTPS to DPI systems. The Xray container runs:
- `xray run` with a generated VLESS+Reality client config
- `microsocks` as a SOCKS5 proxy exposed on port 1080

Xray config fields: server, port, VLESS UUID, Reality public key, short ID, server name (SNI), flow (xtls-rprx-vision), fingerprint.

### Tunnel Chaining (via_slot)

A slot can optionally route through another slot instead of going directly to the internet. This is configured via the `via_slot` field.

```
slot-9 (Xray/VLESS) --via--> slot-6 (AWG) --> Internet
```

Use cases:
- **Double encryption** — VLESS inside AWG for maximum DPI resistance
- **Geo-routing** — Route through a specific country's AWG tunnel, then exit via VLESS in another country

The dns-router handles chaining by:
1. Topologically sorting slots (parents before children)
2. Routing the child container's traffic through the parent's TUN device
3. Adding nftables FORWARD rules and raw PREROUTING bypass for Docker traffic

Circular chains are detected and rejected by the API.

---

## Group System

Groups organize domains and map them to slots. Groups are fully dynamic — users create, rename, and delete them from the UI.

Each group has:

| Field | Description |
|-------|-------------|
| `id` | Machine-readable slug (auto-generated from label) |
| `label` | Display name, editable |
| `slot` | Which slot handles this group's traffic |
| `domains` | List of domains routed through this group |
| `critical_domains` | Subset of domains that trigger failover when unreachable |
| `bandwidth` | Min/max bandwidth limits (DNS Mode only) |
| `block_ipv6` | Whether to block AAAA responses for this group's domains |

Multiple groups can share the same slot:

```
MESSAGING group  →  slot-1  →  awg-client-slot-1  →  AWG tunnel
STREAMING group  →  slot-1  →  awg-client-slot-1  →  AWG tunnel (shared)
AI group         →  slot-2  →  awg-client-slot-2  →  AWG tunnel (different exit)
DIRECT group     →  slot-0  →  (direct, no proxy)
```

### Routing Behavior

Only domains in groups go through VPN; everything else goes direct (whitelist routing).

---

## Configuration: Single Source of Truth

All runtime state lives in `proxima-config.json`, mounted at `/config/proxima-config.json` inside the container.

```json
{
  "mode": "dns",
  "server_ip": "192.168.2.91",
  "slots": { ... },
  "groups": [ ... ],
  "keys": [ ... ],
  "tunnel_configs": [ ... ],
  "settings": { ... },
  "auth": { ... }
}
```

> **Note:** The config key was renamed from `awg_configs` to `tunnel_configs` when Shadowsocks support was added. A one-time migration runs automatically on startup for existing configs.

Key architectural rules:
- **Never hardcode groups or slots in Python** — everything comes from config
- **Thread-safe access** — Config load/save uses `RLock` for concurrent safety
- **Atomic writes** — Config is written atomically to prevent corruption
- **No separate state files** — Health state is in-memory, rebuilt on restart

> **See also:** The example config at `proxima-config.example.json` in the project root

---

## Docker Architecture

### Containers

| Container | Network Mode | Purpose |
|-----------|-------------|---------|
| `proxima` | Bridge (proxy_net + vpn_net) | Flask API + React frontend |
| `dnsmasq` | **Host** | DNS resolver with nftset support |
| `dns-router` | **Host** | nftables, tun2socks, gost, tc/HTB, SNI router |
| `awg-client-slot-*` | Bridge (vpn_net) | AmneziaWG tunnels |
| `outline-client-*` | Bridge (vpn_net) | Shadowsocks (Outline) tunnels |
| `xray-client-*` | Bridge (vpn_net) | VLESS+Reality (Xray) tunnels |
| `zapret-client-*` | Bridge (vpn_net) | DPI bypass (nfqws2 + microsocks) |

> Containers are created dynamically when slots are added via the API. Each slot runs exactly one container type. All tunnel containers expose SOCKS5 on port 1080 internally.

### Networks

```
proxy_net (external)    — Exposed to LAN: Flask API, proxy gateway
vpn_net (internal)      — Internal bridge: tunnel clients ↔ Proxima
host network            — dnsmasq and dns-router for port 53, nftables access
```

### Volumes

```
config/                 → /config           (proxima: read-write; clients: read-only)
config/dnsmasq/         → /config/dnsmasq   (dnsmasq: read-only)
config/dns-router/      → /config/dns-router (dns-router: read-only)
config/dnsmasq-logs/    → /var/log/dnsmasq  (dnsmasq: write, dns-router: read-only)
/var/run/docker.sock    → Docker API        (proxima needs container control)
```

The `dnsmasq-logs` volume is shared between dnsmasq and dns-router: dnsmasq writes query logs (`log-queries=extra`), and the DNS Arbiter inside dns-router reads them for per-device routing decisions.

The dns-router container runs several daemons: tun2socks (one per tunnel), the DNS Arbiter (arbiter.sh + arbiter.awk), and the SNI router (sni-router.py) for domain-accurate HTTPS routing via TPROXY on port 443.

### DNS Mode Container Flow

```
1. Client DNS query → dnsmasq (port 53, host network)
2. dnsmasq resolves → adds IP to nftables nftset + writes query log
3. DNS Arbiter (dns-router) reads log → updates per-device nft map for shared IPs
4. Client TCP connection → nftables marks packet (fwmark 0x1 + group mark)
5a. Port 443 → TPROXY → SNI router reads TLS SNI → SOCKS5 (port 108N) → tunnel → Internet
5b. Other ports → policy routing → tunN → tun2socks → SOCKS5 (port 108N) → tunnel → Internet
```

---

## Health System

### Health State (In-Memory)

Each slot maintains an in-memory health record:

```
{
  "last_ip_check": timestamp,
  "last_ip_ok": true/false,
  "last_ip": "exit IP address",
  "last_domain_check": timestamp,
  "last_domain_ok": true/false,
  "failover_count": number,
  "key_stats": { "key-name": { "success": N, "fail": N } }
}
```

Health state is the **single source of truth** for what the UI displays. It's rebuilt on container restart.

### Scheduler

Background daemon thread with independent timers. Health checks run **in parallel** across slots using a `ThreadPoolExecutor` (max 4 workers), so a slow or unresponsive slot does not block checks on other slots.

| Task | Default Interval | Scope | Purpose |
|------|-----------------|-------|---------|
| IP check | 30 min | Per-slot | Verify tunnel exits at expected IP |
| Domain check | 60 min | Per-slot | Verify critical domains are reachable |
| Tunnel health | 30 min | Global (DNS only) | Check dns-router, nftables, TUN devices, SOCKS5 ports |
| Bandwidth sampling | 60 sec | Global (DNS only) | Record per-tunnel RX/TX byte deltas to SQLite |
| iplist sync | 24 hours | Global | Update community domain database from iplist.opencck.org |

All scheduler state is available via `GET /api/scheduler/jobs` and visualized in the **Scheduler** page in the UI.

> **See also:** [Health & Failover](/docs/health-failover.md) for the complete failover algorithm

### Resource Management

Proxima automatically manages container lifecycle:

- **Startup**: Stops disabled slot containers.
- **Failover**: Rotates key pool, restarts tunnel container, verifies exit IP.

A shared **singleton Docker client** (`docker_utils.py`) is used across all modules that interact with the Docker API, avoiding repeated `docker.from_env()` connection overhead.

---

## VPN User System

Proxima includes a per-user authentication system for ProximaVPN peers:

- **VPN Users** — Accounts with username/password, peer limits, bandwidth quotas, speed limits, and assigned groups
- **Device Authentication** — When a user logs in via the ProximaVPN app, their device IP is added to nftables auth sets
- **Per-User Routing** — Users can have `routing_mode: "full"` (all groups) or `"selected"` (only assigned groups)
- **Three-tier nftset system** — `authenticated` (gate), `full_vpn` (all routing), `auth_{group_id}` (per-group)
- **Traffic accounting** — iptables PROXIMA_ACCT chain tracks per-user TX/RX bytes

> **See also:** [User Management](/docs/user-management.md) for the complete user system documentation

---

## Database

SQLite at `/config/proxima.db` records:

- **Key events** — Activation, success/fail, exit IP
- **Domain check results** — Domain, HTTP status, exit IP, timestamp

This data powers the Performances page charts showing key success rates over time.

---

## Logging

- **File:** `/config/proxima.log`
- **Rotation:** Daily, 7 days retention
- **Format:** `2026-04-15 01:39:00 INFO [SLOT-1] message`
- **Levels:** DEBUG, INFO, WARNING, ERROR
- All log calls include slot context: `[SLOT-1]`, `[SLOT-6]`, etc.
