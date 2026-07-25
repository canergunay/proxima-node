# Introduction

Proxima is a self-hosted proxy and VPN management application for Linux servers. It provides domain-based traffic routing, automatic health checks, failover, and bandwidth shaping through an intuitive web interface.

---

## What Problem Does Proxima Solve?

In regions where internet censorship and deep packet inspection (DPI) are active, accessing certain websites and services requires routing traffic through VPN tunnels. Proxima automates this process:

- **Selective routing** — Only specified domains go through VPN; everything else stays direct
- **Automatic failover** — If a VPN server goes down, Proxima switches to the next one in the pool
- **Multiple tunnels** — Different services can use different VPN servers simultaneously
- **Transparent operation** — Devices on the network don't need any special configuration beyond DNS/gateway settings
- **Bandwidth control** — Per-group traffic shaping prevents one service from consuming all VPN bandwidth

---

## Key Features

| Feature | Description |
|---------|-------------|
| **Domain-based routing** | Group domains and route each group through a specific VPN tunnel |
| **Health monitoring** | Periodic IP and domain checks verify tunnel connectivity |
| **Automatic failover** | Failed tunnels rotate to the next config in the pool |
| **Bandwidth shaping** | Per-group min/max bandwidth limits via tc/HTB |
| **Community domain DB** | Curated database of ~2000 domains, auto-synced from filter lists |
| **Per-user auth** | Only authenticated devices get VPN routing (DNS Mode) |
| **ProximaVPN** | WireGuard hop for mobile devices on restricted networks |
| **Proxy gateway** | HTTP proxy endpoint for Docker containers |
| **Multi-protocol** | Supports AmneziaWG (AWG), Shadowsocks (SS), and VLESS+Reality (Xray) tunnels |
| **DPI bypass** | AmneziaWG provides WireGuard with anti-DPI obfuscation; VLESS+Reality mimics normal TLS traffic |
| **Tunnel chaining** | Route a slot through another slot (e.g., VLESS via AWG) for multi-hop censorship bypass |
| **SNI-based HTTPS routing** | TPROXY intercepts port 443, reads TLS SNI for domain-accurate routing — resolves shared-IP conflicts |
| **Split-tunnel VPN** | ProximaVPN generates RFC1918-excluding AllowedIPs — local devices reachable regardless of current network |

---

## Routing Mode

### DNS Mode

All-traffic transparent proxying via dnsmasq, nftables, and tun2socks.

- dnsmasq resolves DNS and populates nftables sets with resolved IPs
- nftables marks matching packets for policy routing
- tun2socks routes marked traffic through VPN tunnel via TUN interface
- **SNI router** intercepts port 443 via TPROXY, reads TLS ClientHello to route by exact domain (not just IP) — solves shared-IP services like YouTube vs Gemini
- Works for **all** TCP traffic — browsers, native apps, CLI tools
- Includes per-group bandwidth shaping and QUIC blocking
- Supports per-user authentication (only opted-in devices get VPN)

> **See also:** [DNS Mode Deep Dive](/docs/dns-mode.md)

---

## Architecture Overview

Proxima runs as a set of Docker containers:

```
proxima            — Flask API + React frontend (management plane)
dnsmasq            — DNS resolver with nftset support (DNS Mode)
dns-router         — nftables + tun2socks + gost + SNI router (DNS Mode)
awg-client-*       — AmneziaWG tunnel clients
outline-client-*   — Shadowsocks (Outline) tunnel clients
xray-client-*      — VLESS+Reality (Xray) tunnel clients
```

All runtime configuration lives in a single `proxima-config.json` file. The web UI provides full management of slots, groups, domains, keys, and settings.

> **See also:** [Architecture](/docs/architecture.md) for the complete system design

---

## Tech Stack

### Backend
- Python 3.12, Flask (threaded)
- Docker SDK for container management
- SQLite for performance tracking
- JWT authentication with bcrypt password hashing

### Frontend
- React 18 + TypeScript + Vite
- MUI v6 (Material UI) with dark theme
- i18next for internationalization (English, Turkish, Russian)
- Recharts for performance visualization

### Infrastructure
- Docker + Docker Compose
- [Shadowsocks-libev](https://github.com/shadowsocks/shadowsocks-libev) for SS tunnels (via Outline client)
- [AmneziaWG](https://github.com/amnezia-vpn/amneziawg-linux-kernel-module) for obfuscated WireGuard tunnels
- [Xray-core](https://github.com/XTLS/Xray-core) for VLESS+Reality tunnels (TLS camouflage)
- [tun2socks](https://github.com/xjasonlyu/tun2socks) for transparent TUN-based proxying
- [gost](https://github.com/ginuerzh/gost) for SOCKS5 proxy with UDP support
- [dnsmasq](https://thekelleys.org.uk/dnsmasq/doc.html) 2.90+ for DNS with nftset support

---

## Target Use Cases

Proxima is designed for users in countries with active internet censorship (currently deployed in Turkey and Russia):

1. **Home network** — Route YouTube, Telegram, AI services through VPN while local traffic stays direct
2. **Office network** — Selective VPN for specific services, transparent to all devices
3. **Mobile access** — ProximaVPN WireGuard hop for phones on LTE/5G (bypasses carrier DPI)
4. **Docker workloads** — Proxy gateway for containers that need VPN access

---

## Quick Navigation

- [Architecture](/docs/architecture.md) — System design and component details
- [Installation & Setup](/docs/installation.md) — Get Proxima running
- [Domain Management](/docs/domains.md) — Managing groups and domains
- [Health & Failover](/docs/health-failover.md) — How monitoring and failover work
- [API Reference](/docs/api-reference.md) — Complete REST API documentation
- [Troubleshooting](/docs/troubleshooting.md) — Common issues and solutions
