# DNS Mode Deep Dive

DNS Mode is Proxima's routing mode. It transparently routes **all TCP traffic** through VPN tunnels -- including native apps, CLI tools, mobile apps, and any other software that makes network connections.

This document explains the full data plane architecture, every component involved, and the hard-won lessons learned from production deployments.

---

## Overview

DNS Mode works by intercepting DNS queries, recording the resolved IP addresses into nftables sets, and then using policy routing to send matching TCP traffic through a TUN interface that forwards it through a SOCKS5 proxy into a VPN tunnel (AmneziaWG, Outline/SS, or Xray/VLESS).

The key property of DNS Mode is **independence from the management plane**. The data plane (dnsmasq, nftables, tun2socks, gost, AWG/Outline/Xray) operates as a standalone pipeline. If the Proxima Flask application crashes, all existing traffic routing continues uninterrupted. Only health checks, failover, the web UI, and the proxy gateway are affected.

Devices on the network need only two settings to use DNS Mode:
1. **DNS server** set to the Proxima server's IP
2. **Default gateway** set to the Proxima server's IP

---

## Data Plane Architecture

The complete packet flow from a client device to the internet:

```
                            DNS RESOLUTION
                            ==============
Client device                dnsmasq (port 53)              nftables
  |                              |                              |
  |-- DNS query: youtube.com --> |                              |
  |                              |-- resolves to 142.250.x.x   |
  |                              |-- nftset=/.../proxied -----> |
  |                              |   (adds IP to nftset)        |
  | <--- DNS response ---------- |                              |

                    TCP CONNECTION (port 443 — HTTPS)
                    =================================
Client device           nftables prerouting          SNI router (port 4430)
  |                              |                          |
  |-- TCP SYN to 142.250.x.x -> |                          |
  |                    match @proxied set                    |
  |                    meta mark set 0x1                     |
  |                    group mark set (first-match-wins)     |
  |                    tcp dport 443 → TPROXY to :4430       |
  |                              |------------------------> |
  |                              |          reads TLS ClientHello SNI
  |                              |          looks up domain → group → SOCKS5 port
  |                              |          SOCKS5 CONNECT to original dest IP
  |                              |                          |-- via AWG tunnel --> Internet

                    TCP CONNECTION (non-443 — HTTP, etc.)
                    =====================================
Client device           nftables prerouting       Policy routing
  |                              |                       |
  |-- TCP SYN to 142.250.x.x -> |                       |
  |                    match @proxied set                 |
  |                    meta mark set 0x1                  |
  |                    ct mark set meta mark              |
  |                              |-- fwmark 0x1/0x1 ---> |
  |                              |                  lookup table 100
  |                              |                  default dev tun0
  |                              |                       |
                                                         v
                       tun2socks (tun0)           gost (SOCKS5)
                              |                       |
                              |-- TCP via SOCKS5 ---> |
                              |                       |-- via AWG tunnel --> Internet
                              |                       |

                          RETURN PATH
                          ===========
Internet --> AWG tunnel --> gost --> tun2socks (tun0)
  --> ip rule: iif tun0 lookup main (CRITICAL)
  --> main table routes to LAN interface
  --> postrouting: restore ct mark to meta mark
  --> tc/HTB shapes bandwidth per group
  --> response delivered to client
```

Port 443 (HTTPS) traffic is intercepted by the **SNI router** via TPROXY, which reads the TLS Server Name Indication to determine the exact domain and routes through the correct SOCKS5 proxy. Non-443 traffic follows the traditional fwmark/tun2socks path. See the [SNI Router](#10-sni-router-tproxy) section below for details.

---

## Component Deep Dive

### 1. dnsmasq

dnsmasq runs on the **host network** (not Docker bridge) at port 53. It serves as the DNS resolver for all devices on the LAN and is the entry point of the DNS Mode pipeline.

**Key responsibilities:**
- Resolve DNS queries for all clients
- Populate nftables sets with resolved IP addresses via `nftset` directives
- Block AAAA responses for proxied domains (IPv6 bypass prevention)
- Forward non-proxied queries to upstream DNS

**Configuration files** (auto-generated by Proxima, never edited manually):

| File | Purpose |
|------|---------|
| `/config/dnsmasq/proxima-domains.conf` | nftset entries for proxied domains |
| `/config/dnsmasq/proxima-upstream.conf` | Upstream DNS server setting |
| `/config/dnsmasq/proxima-local.conf` | Local domain overrides (hairpin NAT fix) |

**Query logging** (for DNS Arbiter):

dnsmasq is configured with `log-queries=extra` to include source IP addresses in query log lines. The log is written to `/var/log/dnsmasq/dnsmasq.log` (shared volume with dns-router) and is used by the arbiter for per-device routing decisions. Log rotation is handled by dns-router (truncate at 10MB, keep 1 rotated copy).

**Example `proxima-domains.conf` (whitelist mode):**

```
# Auto-generated by Proxima -- do not edit manually

# Group: Messaging -> slot-1 (15 domains)
nftset=/telegram.org/4#inet#proxima#proxied,4#inet#proxima#group_messaging
address=/telegram.org/::
nftset=/t.me/4#inet#proxima#proxied,4#inet#proxima#group_messaging
address=/t.me/::
nftset=/web.telegram.org/4#inet#proxima#proxied,4#inet#proxima#group_messaging
address=/web.telegram.org/::

# Group: Streaming -> slot-1 (42 domains)
nftset=/youtube.com/4#inet#proxima#proxied,4#inet#proxima#group_streaming
address=/youtube.com/::
nftset=/googlevideo.com/4#inet#proxima#proxied,4#inet#proxima#group_streaming
address=/googlevideo.com/::
```

**nftset format breakdown:**
```
nftset=/<domain>/4#inet#proxima#proxied,4#inet#proxima#group_<id>
        |         | |     |       |       |                  |
        domain    | |     |       |       second set         group-specific set
                  | |     table   set name (global proxied)
                  | address family (inet = ip + ip6)
                  IPv4 only (4)
```

**Critical rules:**
- **One line per domain** -- never join multiple domains into one nftset line. Long lines exceed dnsmasq's internal buffer and silently fail.
- **Cache is enabled** (`cache-size=1000`) -- safe because DNS TTL values (typically 60-300s) are much shorter than the nftset timeout (3600s). IPs remain in nftsets long after the cache entry expires.
- **DoH canary domain**: `address=/use-application-dns.net/` returns an empty response, which tells browsers (Firefox, Chrome) to disable DNS-over-HTTPS. Without this, browsers bypass dnsmasq entirely and the pipeline breaks.
- **Reload requires restart** -- dnsmasq does NOT re-read `conf-dir` files on SIGHUP (only `/etc/resolv.conf`). Proxima restarts the dnsmasq container when config changes.

**Upstream DNS configuration:**

| Deployment | Upstream | Notes |
|------------|----------|-------|
| ERG (home) | `127.0.0.1#5353` | AdGuard Home (moved from port 53 to 5353) |
| OFC (office) | `192.168.77.1` | MikroTik router |

---

### 2. nftables

The dns-router container runs on the **host network** and manages the `inet proxima` nftables table. This table contains dynamic sets populated by dnsmasq and prerouting/postrouting chains for packet marking.

**Generated nftables config (`proxima.nft`) -- whitelist mode:**

```nft
table inet proxima {
    # Dynamic sets -- populated by dnsmasq nftset directives
    set proxied {
        type ipv4_addr
        flags timeout
        timeout 3600s
    }

    set group_messaging {
        type ipv4_addr
        flags timeout
        timeout 3600s
    }

    set group_streaming {
        type ipv4_addr
        flags timeout
        timeout 3600s
    }

    # Static sets -- IP/CIDR ranges from config (e.g., Telegram CIDRs)
    set static_proxied {
        type ipv4_addr
        flags interval
        elements = { 149.154.160.0/20, 91.108.4.0/22 }
    }

    chain proxima_prerouting {
        type filter hook prerouting priority mangle; policy accept;

        # Only process traffic from LAN (and VPN server interfaces like wg1)
        iif != "enp3s0" accept

        # Skip private/local addresses
        ip daddr 192.168.0.0/16 accept
        ip daddr 10.0.0.0/8 accept
        ip daddr 172.16.0.0/12 accept
        ip daddr 127.0.0.0/8 accept

        # Restore conntrack marks for established VPN connections
        # Prevents arbiter from rerouting packets mid-session when
        # background DNS queries update device_routes for shared IPs
        ct state established,related ct mark & 0x1 == 0x1 meta mark set ct mark accept

        # Mark proxied traffic (base VPN mark)
        ip daddr @proxied meta mark set meta mark or 0x1
        ip daddr @static_proxied meta mark set meta mark or 0x1

        # DNS Arbiter: per-device routing for conflicting IPs
        # Overrides group marks when arbiter has a specific (src, dst) entry
        meta mark & 0x1 == 0x1 meta mark set ip saddr . ip daddr map @device_routes

        # Per-group marks: FIRST-MATCH-WINS
        # Only set group mark if no group mark already set (prevents compound marks).
        # Groups with non-default slots are listed first for priority.
        ip daddr @group_youtube meta mark & 0xf0 == 0x00 meta mark set meta mark or 0x10
        ip daddr @group_arr meta mark & 0xf0 == 0x00 meta mark set meta mark or 0x20
        ip daddr @group_messaging meta mark & 0xf0 == 0x00 meta mark set meta mark or 0x30
        ip daddr @group_ai meta mark & 0xf0 == 0x00 meta mark set meta mark or 0x40

        # SNI router: TPROXY intercept for domain-accurate HTTPS routing
        meta mark & 0x1 == 0x1 tcp dport 443 meta mark set meta mark | 0x200 tproxy ip to 127.0.0.1:4430 accept

        # Save marks to conntrack for bandwidth classification
        meta mark & 0x1 == 0x1 ct mark set meta mark
    }

    # Restore conntrack marks on responses going to LAN/VPN clients
    chain proxima_postrouting {
        type filter hook postrouting priority mangle; policy accept;
        oif "enp3s0" ct mark & 0x1 == 0x1 meta mark set ct mark
    }
}
```

**Set types:**

| Set | Type | Flags | Source |
|-----|------|-------|--------|
| `proxied` | `ipv4_addr` | `timeout` (3600s) | dnsmasq nftset (dynamic) |
| `group_<id>` | `ipv4_addr` | `timeout` (3600s) | dnsmasq nftset (dynamic) |
| `static_proxied` | `ipv4_addr` | `interval` | Config IP/CIDRs (static) |
| `authenticated` | `ipv4_addr` | `timeout` | Per-user auth device IPs |
| `device_routes` | `ipv4_addr . ipv4_addr : mark` | `timeout` (600s) | DNS Arbiter per-device routing map |

**Mark encoding:**

The mark is a 32-bit integer with a layered structure:
- **Bit 0** (`0x1`): VPN routing flag -- packet should go through VPN
- **Bits 4-7** (`0xF0`): Group identifier -- 0x10 = group 1, 0x20 = group 2, etc.
- **Bit 9** (`0x200`): TPROXY flag -- packet is being intercepted by the SNI router

Example marks: `0x11` = VPN + group 1, `0x21` = VPN + group 2, `0x211` = VPN + group 1 + TPROXY. This is why fwmark matching **must** use a mask: `0x1/0x1` (check only bit 0), not `0x1` (exact match would miss 0x11, 0x21, 0x211, etc.).

**First-match-wins:** Group marks use a first-match-wins pattern (`meta mark & 0xf0 == 0x00`) to prevent compound marks when an IP is in multiple group sets. Groups with non-default tunnel slots are listed first in nftables rules for priority.

---

### 3. Policy Routing

Policy routing directs marked packets to the TUN interface. These rules are set up by the dns-router entrypoint script.

```bash
# Route marked traffic through tun0
ip rule add fwmark 0x1/0x1 lookup 100
ip route add default dev tun0 table 100

# CRITICAL: Prevent routing loop for return traffic from tun0
ip rule add iif tun0 lookup main priority 32764
```

**Why `iif tun0 lookup main` is critical:**

Without this rule, the following loop occurs:
1. Client sends packet to 142.250.x.x -- nftables marks it 0x1
2. fwmark rule routes it to tun0 -- tun2socks sends it through gost/AWG
3. Response comes back through AWG -- arrives on tun0
4. Postrouting chain: `meta mark set ct mark` restores the 0x1 mark
5. fwmark rule matches again -- sends response back to tun0 (LOOP)

The `iif tun0 lookup main` rule (at priority 32764, before the fwmark rule) intercepts packets arriving FROM tun0 and routes them via the main routing table instead, which delivers them to the LAN interface and ultimately to the client.

**Key properties:**
- ip rules **persist across nftables reloads** -- no need to re-apply them
- fwmark **must use mask** (`0x1/0x1`) because group marks use higher bits
- Multiple tunnels use separate routing tables (100, 101, 102...) with per-mark rules

**POSTROUTING masquerade:**

```nft
ip saddr 192.168.0.0/16 ip daddr != 192.168.0.0/16 masquerade
```

This rule in `ip nat POSTROUTING` SNATs packets from LAN clients (e.g., phone at 192.168.2.146) going to tun0. The source address becomes 198.18.0.1 (the tun0 IP). When the response comes back, conntrack de-SNATs it back to the original client IP. The `iif tun0 lookup main` rule ensures these de-SNATted packets are routed via the main table to the LAN.

---

### 4. tun2socks

[tun2socks](https://github.com/xjasonlyu/tun2socks) creates a TUN network interface that captures IP packets and forwards them through a SOCKS5 proxy. It replaced redsocks in the Proxima architecture because:

- **TUN-based** -- operates at the network layer, not the transport layer
- **Handles TCP and UDP** -- redsocks was TCP-only
- **No iptables REDIRECT needed** -- uses policy routing instead of DNAT

**Configuration:**

```bash
tun2socks -device tun0 \
          -proxy socks5://127.0.0.1:1081 \
          -loglevel warning
```

| Parameter | Value | Notes |
|-----------|-------|-------|
| `-device` | `tun0` | TUN interface name |
| `-proxy` | `socks5://127.0.0.1:1081` | gost SOCKS5 proxy (slot-1 default tunnel) |
| `-loglevel` | `warning` | Uses logrus levels -- `warn` is NOT valid, must use `warning` |

**Network setup:**
```bash
ip addr add 198.18.0.1/15 dev tun0
ip link set tun0 up
```

The 198.18.0.0/15 range is reserved for network benchmark testing (RFC 2544) and is safe to use for TUN interfaces.

**Container requirements:**
- `/dev/net/tun` device must be mapped into the container
- `NET_ADMIN` capability required
- Host network mode (for nftables and routing table access)

**Multi-tunnel support:**

When multiple slots are enabled, dns-router starts one tun2socks instance per tunnel:

```
tun0 -> socks5://127.0.0.1:1081 (slot-1, default)  -> table 100
tun1 -> socks5://127.0.0.1:1082 (slot-2)            -> table 101
tun2 -> socks5://127.0.0.1:1083 (slot-3)            -> table 102
```

Per-group marks route traffic to specific tunnels via separate ip rules:

```bash
ip rule add fwmark 0x1/0x1 lookup 100    # default tunnel (all VPN)
ip rule add fwmark 0x20/0xf0 lookup 101  # group 2 -> slot-7
```

### Tunnel Chaining (via_slot)

Slots can be chained so that one slot's traffic routes through another slot's tunnel. This is configured via the `via_slot` field in the slot config.

#### How It Works

When slot B has `via_slot: "slot-A"`:

1. **Topological sort** -- `dns_router.py` sorts slots so parents are processed before children
2. **Container IP resolution** -- The child slot's container IP on `vpn_net` is resolved via Docker API
3. **tunnels.json metadata** -- The child slot entry includes `via_slot`, `via_table` (parent's routing table), `via_device` (parent's TUN), and `container_ip`
4. **Routing** -- The entrypoint/reload script adds `ip route` rules so the child container's traffic goes through the parent's TUN device
5. **nftables FORWARD** -- Bidirectional ACCEPT rules are added for traffic between the child container IP and TUN devices
6. **raw PREROUTING bypass** -- NOTRACK rules bypass Docker's conntrack for chained traffic

#### Example Chain

```
slot-9 (Xray/VLESS, container IP 172.20.0.5)
  --via--> slot-6 (AWG, tun0, table 100)
    --> Internet

Traffic flow:
  xray-client-slot-9 -> ip route via tun0 -> tun2socks (slot-6) -> AWG tunnel -> Internet
```

#### Circular Chain Detection

The API validates `via_slot` assignments and rejects circular chains (A->B->A or A->B->C->A).

---

### 5. gost

[gost](https://github.com/ginuerzh/gost) is a SOCKS5 proxy that provides the bridge between tun2socks and the AWG tunnel. It replaced microsocks because:

- **Full SOCKS5 support** -- including UDP ASSOCIATE (needed for QUIC attempt)
- **TCP + UDP** -- microsocks was TCP-only

gost runs inside the AWG client container and listens on port 1080 (internal) or a mapped port (e.g., 1081 for slot-1). It forwards all traffic through the AWG WireGuard interface to exit at the VPN server.

---

### 6. QUIC Blocking

QUIC uses UDP port 443. While tun2socks can capture UDP traffic and gost supports UDP ASSOCIATE, the end-to-end UDP path through AWG is unreliable -- UDP packets are silently lost.

**Solution: REJECT UDP port 443 for proxied traffic**

```bash
# In dns-router entrypoint -- inserted LAST so it ends up at position 1 of the FORWARD chain
iptables -I FORWARD 1 -m mark --mark 0x1/0x1 -p udp --dport 443 -j REJECT --reject-with icmp-port-unreachable
```

- **Mark condition** (`-m mark --mark 0x1/0x1`): only blocks QUIC for traffic already marked as proxied (bit 0 set). Direct internet traffic is unaffected.
- **REJECT** (not DROP): sends ICMP Port Unreachable back to the client immediately. Browsers/apps fall back to TCP (HTTP/2 over TLS) without waiting for a UDP timeout.
- **INSERT at position 1** (`-I FORWARD 1`): ensures the rule sits at the top of the FORWARD chain, before any ACCEPT rules.
- DROP would cause a timeout before fallback -- much slower user experience.

**Critical ordering requirement:**

The QUIC REJECT rule must be added **after** all FORWARD ACCEPT rules. The dns-router entrypoint uses `iptables -I FORWARD` (insert at top) for LAN→tun ACCEPT rules. If REJECT is inserted first and ACCEPT rules follow, each subsequent `-I FORWARD` pushes REJECT further down the chain. The `enp5s0 → tunN ACCEPT` rule then matches proxied QUIC before REJECT, and QUIC enters tun2socks where gost UDP ASSOCIATE silently fails (10-second timeout per request). Adding REJECT last ensures it ends up at position 1.

---

### 7. IPv6 Blocking

The nftsets use `ipv4_addr` type -- they cannot hold IPv6 addresses. If a domain resolves to both A (IPv4) and AAAA (IPv6) records, the client may prefer IPv6 and bypass the VPN entirely.

**Per-group IPv6 blocking:**

When `block_ipv6` is `true` (the default) for a group, dnsmasq emits:

```
address=/youtube.com/::
```

This tells dnsmasq to return `::` (unspecified address) for any AAAA query for `youtube.com` and all its subdomains. The client receives no usable IPv6 address and falls back to IPv4, which is then intercepted by nftables.

**Warning: NEVER use global IPv6 blocking**

```
# DO NOT DO THIS
address=/#/::
```

A global `address=/#/::` directive blocks AAAA for ALL domains. This breaks services that require IPv6 (YouTube live streams, ChatGPT, Claude, and many CDNs). Always use per-group, per-domain IPv6 blocking.

---

### 8. Bandwidth Shaping

DNS Mode includes per-group bandwidth shaping using tc (traffic control) with HTB (Hierarchical Token Bucket) qdiscs on the LAN interface.

**HTB class hierarchy:**

```
1:1 (root, 1gbit)
 |
 +-- 1:2 (VPN umbrella, e.g. 50mbit)
 |    |
 |    +-- 1:10 (Messaging group, rate 5mbit, ceil 20mbit)
 |    |       \-- SFQ qdisc (fair queuing)
 |    |
 |    +-- 1:20 (Streaming group, rate 30mbit, ceil 50mbit)
 |    |       \-- SFQ qdisc (fair queuing)
 |    |
 |    +-- 1:fe (unclassified VPN traffic, rate 1mbit, ceil 50mbit)
 |           \-- SFQ qdisc (fair queuing)
 |
 +-- 1:ff (non-VPN traffic, 1gbit -- unlimited)
```

**Generated tc script (`tc-rules.sh`):**

```bash
#!/bin/sh
LAN_IF=$(ip route | awk '/default/ {print $5; exit}')

tc qdisc del dev $LAN_IF root 2>/dev/null || true

tc qdisc add dev $LAN_IF root handle 1: htb default ff
tc class add dev $LAN_IF parent 1: classid 1:1 htb rate 1gbit

# VPN umbrella (total: 50mbit)
tc class add dev $LAN_IF parent 1:1 classid 1:2 htb rate 50mbit ceil 50mbit

# Messaging (mark 0x10)
tc class add dev $LAN_IF parent 1:2 classid 1:10 htb rate 5mbit ceil 20mbit
tc qdisc add dev $LAN_IF parent 1:10 handle 10: sfq perturb 10
tc filter add dev $LAN_IF parent 1: prio 1 handle 0x10/0xf0 fw classid 1:10

# Streaming (mark 0x20)
tc class add dev $LAN_IF parent 1:2 classid 1:20 htb rate 30mbit ceil 50mbit
tc qdisc add dev $LAN_IF parent 1:20 handle 20: sfq perturb 10
tc filter add dev $LAN_IF parent 1: prio 1 handle 0x20/0xf0 fw classid 1:20

# Unclassified VPN traffic
tc class add dev $LAN_IF parent 1:2 classid 1:fe htb rate 1mbit ceil 50mbit
tc qdisc add dev $LAN_IF parent 1:fe handle fe: sfq perturb 10
tc filter add dev $LAN_IF parent 1: prio 2 handle 0x1/0x1 fw classid 1:fe

# Non-VPN traffic (default -- unlimited)
tc class add dev $LAN_IF parent 1:1 classid 1:ff htb rate 1gbit ceil 1gbit
```

**How classification works:**

1. Return packets from tun0 arrive at postrouting chain
2. `ct mark` is restored to `meta mark` (conntrack saved the original mark)
3. tc filters match the mark's group bits (`0xF0` mask) to assign a class
4. SFQ qdisc ensures fairness within each class

**Important constraints:**
- tc classids must NOT collide with root (`1:1`) or umbrella (`1:2`) -- use `1:10`, `1:20`, etc.
- The mark value is used directly as the classid (mark `0x10` -> class `1:10`)
- Non-proxied traffic (mark=0) gets no filter match and falls into default class `1:ff` (unlimited)

---

### 9. Bypass Mode

When ALL VPN tunnel configurations in the pool fail health checks, Proxima activates **bypass mode** to prevent internet outages.

**Bypass activation sequence:**

1. All pool configs fail IP check
2. Proxima writes bypass dnsmasq config (removes all nftset entries)
3. Proxima flushes all nftables sets (clears cached IPs)
4. dnsmasq is restarted with the bypass config
5. DNS queries resolve normally but IPs are no longer added to nftsets
6. Since nftsets are empty, no packets match, no packets get marked
7. All traffic goes direct -- internet works without VPN

**Bypass recovery sequence:**

1. IP check runs every 2 minutes during bypass mode
2. When a config succeeds the IP check:
   - Pool rotates to the working config
   - Full dnsmasq config is regenerated with nftset entries
   - dnsmasq is restarted
   - nftables rules are reloaded
   - DNS queries start populating nftsets again
   - Traffic gradually shifts back to VPN as DNS cache refreshes

**Important:** The `authenticated` nftset is NEVER flushed during bypass. Per-user device registrations are preserved across bypass/recovery cycles.

---

### 10. SNI Router (TPROXY)

The SNI router solves a fundamental limitation of IP-based routing: services that share anycast IP addresses (e.g., YouTube and Gemini both resolve to the same Google IPs) cannot be distinguished by nftables alone. The SNI router intercepts HTTPS traffic via TPROXY, reads the TLS Server Name Indication (SNI) from the ClientHello, and routes each connection through the correct SOCKS5 proxy based on the domain.

**Why IP-level routing is insufficient for port 443:**

The DNS Arbiter handles most shared-IP cases by tracking which device queried which domain. However, it operates on "last DNS query wins" logic -- a background DNS prefetch (e.g., for YouTube) can overwrite a device_routes entry for a shared IP, breaking an active Gemini session. The SNI router provides definitive domain identification at the TCP level, making it immune to DNS timing issues.

**Architecture:**

```
Client → nftables prerouting → TPROXY (tcp dport 443) → sni-router.py (:4430)
                                                              |
                                                   reads TLS ClientHello
                                                   extracts SNI hostname
                                                   looks up domain-groups.map
                                                   selects SOCKS5 port (per group)
                                                              |
                                                   SOCKS5 CONNECT → tunnel → Internet
```

**How TPROXY works:**

Unlike DNAT/REDIRECT, TPROXY preserves the original destination IP address. The nftables rule:

```nft
meta mark & 0x1 == 0x1 tcp dport 443 meta mark set meta mark | 0x200 tproxy ip to 127.0.0.1:4430 accept
```

This rule:
1. Matches only VPN-marked traffic (`0x1` bit set) destined for port 443
2. Sets the TPROXY mark (`0x200`) on the packet
3. Redirects the packet to `127.0.0.1:4430` (sni-router) via TPROXY
4. The `accept` at the end prevents the packet from hitting the subsequent `ct mark set` or falling into the fwmark/tun path

The sni-router socket is created with `IP_TRANSPARENT`, so `getsockname()` on the accepted connection returns the **original** destination IP (e.g., `142.250.x.x:443`), not `127.0.0.1:4430`.

**sni-router.py** (`/sni-router.py` in the dns-router container, ~260 lines Python):

- Listens on port 4430 with `IP_TRANSPARENT` socket option
- On each connection: peeks at the first bytes (`MSG_PEEK`), parses the TLS ClientHello to extract the SNI hostname
- Looks up the hostname in `domain-groups.map` (tries exact match, then progressively strips subdomains)
- Maps the domain's group mark to a SOCKS5 port via `tunnels.json`
- Opens a SOCKS5 CONNECT through `127.0.0.1:<port>` to the original destination IP:443
- Bidirectional tunnel between client and remote (one thread per direction)
- Reloads config on SIGHUP (sent by `reload.sh`) or on file mtime change (every 100 connections)
- Dependencies: Python 3 stdlib only -- no external packages

**Configuration files consumed:**

| File | Purpose |
|------|---------|
| `/config/dns-router/domain-groups.map` | Domain to group mark mapping |
| `/config/dns-router/tunnels.json` | Group mark to SOCKS5 port mapping |

**TPROXY routing requirements:**

TPROXY needs a special routing table so the kernel can deliver packets with non-local destination IPs to a local socket:

```bash
ip rule add fwmark 0x200/0x200 lookup 200 priority 50
ip route add local 0.0.0.0/0 dev lo table 200
```

The `local 0.0.0.0/0` route in table 200 tells the kernel to treat ALL destinations as local for TPROXY-marked packets, allowing them to be delivered to the listening socket.

**UFW compatibility:**

TPROXY'd packets arrive at the INPUT chain with their original non-local destination IP. The host's UFW `INPUT DROP` policy blocks them. The fix is an iptables rule that accepts TPROXY-marked packets:

```bash
iptables -I INPUT -m mark --mark 0x200/0x200 -p tcp -j ACCEPT
```

**Conntrack restore rule:**

The prerouting chain includes a conntrack restore rule that fires before any marking logic:

```nft
ct state established,related ct mark & 0x1 == 0x1 meta mark set ct mark accept
```

This rule protects established connections from being rerouted mid-session. Without it, if a background DNS query for YouTube updates the arbiter's device_routes map for a shared Google IP, an active Gemini session on that same IP could suddenly get rerouted to the YouTube tunnel. The conntrack restore ensures that once a connection is established through a specific tunnel, it stays there for its entire lifetime.

**Non-443 traffic:**

Traffic to ports other than 443 is unaffected by the SNI router. It follows the traditional path: nftables mark -> fwmark -> tun2socks -> gost -> tunnel. The DNS Arbiter remains valuable for non-HTTPS services and as a fallback.

**Lifecycle:**

- Started by `entrypoint.sh` as a background process
- PID file at `/var/run/sni-router.pid`
- Keepalive loop in entrypoint auto-restarts if it dies
- `reload.sh` sends SIGHUP for config reload

---

## Per-User Authentication

DNS Mode can optionally require per-user authentication. When `per_user_auth` is enabled:

1. Network default is **direct** (no VPN) -- safe for guests
2. User opens the Proxima PWA and logs in
3. Backend adds the device's IP to the `authenticated` nftset
4. Only traffic from authenticated IPs is processed by the VPN marking rules
5. All other traffic passes through nftables without marking

```nft
# Per-user auth rule in prerouting chain
ip saddr != @authenticated accept
```

This line appears before any marking rules. If the source IP is not in the `authenticated` set, the packet is accepted without any marks -- it goes direct.

---

## DNS Arbiter (Per-Device Shared IP Routing)

### The Problem

Google services like YouTube and Gemini share the same anycast IP addresses (e.g., 216.58.198.174). Since nftables operates on IP addresses, it cannot route YouTube traffic through a Russian tunnel (slot-7) and Gemini traffic through an Estonian tunnel (slot-6) when both resolve to the same IP. The first-match-wins nftset rules pick one group for the IP, and the other service gets misrouted.

### The Solution

The DNS Arbiter is a lightweight daemon running inside the dns-router container that monitors dnsmasq query logs and maintains a per-device nftables map. It uses "last DNS query wins" logic: when a device queries `youtube.com` and gets IP 216.58.x.x, the arbiter records that this device's traffic to that IP should use YouTube's mark. When the same or a different device queries `gemini.google.com` and gets the same IP, the arbiter records a separate entry.

### Architecture

```
dnsmasq --> query.log --> [arbiter.sh + arbiter.awk] --> nft device_routes map
                                                              |
                  nftables prerouting chain:
                  1. ct state established → restore ct mark (skip re-marking)
                  2. @proxied / @static_proxied --> VPN bit (0x01)
                  3. device_routes map --> per-device mark (arbiter)
                  4. @group_X --> first-match-wins mark (fallback)
                  5. tcp dport 443 → TPROXY to sni-router (:4430)
                  6. ct mark set meta mark
```

### Components

**domain-groups.map** (`/config/dns-router/domain-groups.map`):

Generated by the Proxima backend. Maps domains to their group marks:

```
# domain mark_hex group_id
youtube.com 0x41 youtube
gemini.google.com 0x11 ai
claude.ai 0x11 ai
youtubei.googleapis.com 0x41 youtube
```

Marks include the VPN bit (`mark_int | 0x01`) because the nft map uses `set` (replaces the full mark) rather than `or`.

**Cross-group subdomain handling:**

When a subdomain belongs to a different group than its parent domain (e.g., `youtubei.googleapis.com` in YouTube, while `googleapis.com` is in AI), the subdomain is **always emitted to the map explicitly**. This ensures the SNI router can exact-match it to the correct group, rather than falling back to the parent suffix lookup which would return the wrong group.

Example: without the explicit entry, `sni-router.py` would look up `youtubei.googleapis.com`, fail to find it, strip to `googleapis.com`, find it in the AI group, and route YouTube API traffic through the AI tunnel — wrong group, wrong exit. The explicit map entry makes the exact match succeed immediately.

**arbiter.awk**: AWK state machine that parses dnsmasq log lines:
- Tracks `query[A]` lines for source IP (which device queried which domain)
- Tracks `reply`/`cached` lines for A record responses (domain resolved to which IP)
- Follows CNAME chains back to the original queried domain
- When an IP is claimed by a different group than what's currently in the map, updates the nft `device_routes` map entry

**arbiter.sh**: Shell wrapper that:
- Waits for the dnsmasq log file to appear (up to 60s)
- Runs `tail -F log | awk` pipeline
- Manages PID file at `/var/run/arbiter.pid`
- Handles cleanup on TERM/INT/HUP signals

**nft device_routes map**:

```nft
map device_routes {
    type ipv4_addr . ipv4_addr : mark
    flags timeout
    timeout 600s
}
```

Entries are keyed by `(source_ip, destination_ip)` and contain the full mark value. Entries expire after 10 minutes and are refreshed by ongoing DNS queries.

### Graceful Degradation

If the arbiter crashes or is not running:
- The `device_routes` map is empty (or entries expire naturally)
- Traffic falls back to the first-match-wins group nftset behavior
- The dns-router keepalive loop auto-restarts the arbiter within 60 seconds

### Reload Handling

When Proxima config changes:
1. `domain-groups.map` is regenerated
2. `reload.sh` runs -- nftables reload clears the `device_routes` map
3. Arbiter is killed (keepalive loop restarts it with new map)
4. DNS queries naturally repopulate the map

---

## Key Lessons Learned

These are hard-won insights from production debugging sessions:

### First-match-wins for group marks
When an IP appears in multiple group nftsets (e.g., doubleclick.net resolved IPs in both `group_youtube` and `group_ai`), naive OR-based marking produces compound marks (e.g., `0x51 = 0x10 | 0x40 | 0x01`) that don't match any per-group routing rule. The fix: each group marking rule checks `meta mark & 0xf0 == 0x00` before setting the group mark, so only the first matching group takes effect. Groups with non-default tunnel slots are listed first in the nftables rules to ensure they win priority. After changing nftables mark rules, always flush conntrack (`conntrack -F` on the host) to clear stale compound marks from existing connections.

### Static CIDRs go to static_proxied only
CIDRs from iplist or custom config should only populate `static_proxied` (sets the `0x01` VPN bit). Do NOT create per-group static CIDR sets (`static_group_*`) -- overlapping CIDRs across groups (especially Google/CDN ranges) cause the same compound mark problem described above. Per-group identification relies exclusively on DNS-based dynamic nftsets.

### One nftset line per domain
Attempting to combine multiple domains in a single nftset directive (e.g., `nftset=/a.com/b.com/c.com/...`) exceeds dnsmasq's internal line buffer. The line is silently truncated and domains are lost. Always emit one `nftset=` line per domain.

### iptables-nft rules persist on host
Because dns-router uses host networking, any iptables rules it creates persist on the host even after the container restarts. The entrypoint script must explicitly clean up old rules (especially REDIRECT rules from the redsocks era) before applying new ones.

### VPN DNS hijacking
When using `socks5h://` (DNS resolved inside the tunnel), some VPN providers hijack DNS and return incorrect IP addresses. For AWG health checks, use `socks5://` (DNS resolved locally) to get accurate results. Keep `socks5h://` for Shadowsocks slots where local DNS may not resolve blocked domains.

### POSTROUTING masquerade and iif tun0 interaction
The masquerade rule `ip saddr 192.168.0.0/16 ip daddr != 192.168.0.0/16 masquerade` SNATs phone/device packets going through tun0 (changing source from 192.168.x.x to 198.18.0.1). When responses come back, conntrack de-SNATs them (restoring the original client IP). The `iif tun0 lookup main` rule ensures these de-SNATted packets are routed via the main routing table to the LAN interface, not back into tun0.

### fwmark must use mask
`ip rule add fwmark 0x1 lookup 100` would only match packets with mark exactly `0x1`. But group marks produce values like `0x11`, `0x21`, `0x31`. Using `fwmark 0x1/0x1` checks only bit 0, matching all of these correctly.

### ip rules persist across nftables reloads
Policy routing rules (`ip rule`) and routes (`ip route`) are separate from nftables. Reloading or flushing nftables does not affect them. This is desirable -- the routing infrastructure remains stable while nftables rules can be updated dynamically.

### tun2socks loglevel
tun2socks uses logrus, which has specific level names. Use `warning` -- NOT `warn`. Using `warn` results in an invalid level error and the process may not start correctly.

### tun2socks binary naming
The tun2socks release zip extracts as `tun2socks-linux-amd64`. It must be renamed to `tun2socks` in the container's PATH for the entrypoint script to find it.

### QUIC REJECT must be added last in FORWARD chain
The dns-router entrypoint adds LAN→tun FORWARD ACCEPT rules using `iptables -I FORWARD` (insert at position 1 each time). If the QUIC REJECT rule is inserted first and ACCEPT rules follow, each `-I FORWARD` pushes REJECT further down. The ACCEPT rule for LAN→tun traffic then matches before REJECT, and proxied QUIC enters tun2socks where gost UDP ASSOCIATE silently fails with a 10-second timeout. Always add the QUIC REJECT as the very last iptables rule so it ends up at position 1 of the FORWARD chain.

### AWG tunnel requires MSS clamping in container
`awg-quick` adds MSS clamping only when a `PostUp=` line is present in the .conf file. User VPN configs typically don't include it. Without clamping, TCP SYN packets advertise MSS=1460 (based on LAN MTU=1500), but the AWG tunnel MTU is ~1420. Large TCP segments with DF=1 are silently dropped when they exceed tunnel MTU, triggering PMTUD -- which takes several seconds per connection. Symptoms: first page load of some sites takes 20+ seconds. QUIC hides the problem (adaptive MTU); blocking QUIC reveals it. Fix: add `iptables -t mangle -A POSTROUTING -p tcp --tcp-flags SYN,RST SYN -o "$IFACE" -j TCPMSS --clamp-mss-to-pmtu` in awg-client entrypoint after `awg-quick up`.

### TPROXY packets are blocked by UFW INPUT DROP
TPROXY delivers packets to a local socket while preserving the original destination IP. Since the destination IP is non-local (e.g., `142.250.x.x`), the host's UFW INPUT policy (`DROP`) rejects them. The fix is `iptables -I INPUT -m mark --mark 0x200/0x200 -p tcp -j ACCEPT`, which allows TPROXY-marked packets through INPUT. This rule is managed by dns-router's entrypoint and reload scripts.

### Conntrack restore prevents mid-session rerouting
Established TCP connections must not be rerouted when the arbiter updates device_routes. The `ct state established,related ct mark & 0x1 == 0x1 meta mark set ct mark accept` rule in prerouting restores the original mark from conntrack and accepts immediately, bypassing all subsequent marking rules including arbiter lookups and group marks. Without this, a background YouTube DNS prefetch can overwrite a shared IP entry in device_routes, breaking an active Gemini session on the same IP.

### Docker containers cannot use DNS Mode
Traffic from Docker containers on the bridge network does not traverse dns-router's nftables chains (it takes a different path through the Docker FORWARD chain). Containers that need VPN access should use the Proxima proxy gateway (`proxima:8080`) with explicit `HTTP_PROXY` environment variables.

---

## Related Documentation

- [Architecture](/docs/architecture.md) -- System architecture overview
- [Introduction](/docs/introduction.md) -- Project overview and features
- [Installation](/docs/installation.md) -- Setup guide
