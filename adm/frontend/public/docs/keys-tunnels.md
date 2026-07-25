# Keys & Tunnel Management

Proxima manages VPN tunnel credentials for multiple protocols: **Shadowsocks (SS)**, **Outline (SS+Prefix)**, **AmneziaWG (AWG)**, and **VLESS+Reality (Xray)**. It also supports **Zapret** slots for DPI bypass without a tunnel. Each tunnel slot has a pool of credentials that Proxima rotates through during failover. This document covers how to add, manage, and maintain your VPN keys and configs.

---

## Overview

Proxima uses a slot-based architecture where each slot represents one VPN tunnel endpoint. Credentials (keys or configs) are stored in a **pool** per slot, and one credential is **active** at any time.

```
slot-1  (AWG)   pool: [awg-helsinki, awg-berlin, awg-amsterdam]      active: awg-helsinki
slot-2  (AWG)   pool: [awg-russia-1, awg-russia-2]                  active: awg-russia-1
slot-3  (SS)    pool: [key-finland-1, key-finland-2, key-sweden-1]   active: key-finland-1
slot-7  (Outline) pool: [outline-de-1, outline-fi-1]                active: outline-de-1
slot-9  (Xray)  pool: [vless-poland, vless-germany]                  active: vless-poland
```

When a health check fails, Proxima automatically rotates to the next credential in the pool and restarts the tunnel container.

---

## Shadowsocks Keys

Shadowsocks is a lightweight encrypted proxy protocol. Proxima uses [Shadowsocks-libev](https://github.com/shadowsocks/shadowsocks-libev) as the client implementation.

### SS URI Format

Shadowsocks keys use the standard `ss://` URI format:

```
ss://method:password@server:port
```

For example:

```
ss://chacha20-ietf-poly1305:MySecretPass@185.199.110.1:8388
ss://aes-256-gcm:AnotherPass@203.0.113.50:443
```

Some providers encode the method and password in base64:

```
ss://Y2hhY2hhMjAtaWV0Zi1wb2x5MTMwNTpNeVNlY3JldFBhc3M=@185.199.110.1:8388
```

Proxima accepts both formats and decodes them automatically.

### Adding SS Keys via the UI

1. Go to the **Keys** page
2. Open the **SS Keys** accordion section
3. Enter a descriptive name (e.g., "Finland-Helsinki-1")
4. Paste the full `ss://` URI into the URI field
5. Click **Add**

Proxima parses the URI on the backend and stores the server, port, method, and password internally. The URI is stored as-is and displayed on the list.

### Key Properties

| Property | Description |
|----------|-------------|
| `name` | Human-readable identifier (e.g., "Finland-Helsinki-1") |
| `server` | Server IP address or hostname |
| `port` | Server port number |
| `method` | Encryption method |
| `password` | Encryption key/password |

### Supported Encryption Methods

| Method | Security | Performance |
|--------|----------|-------------|
| `chacha20-ietf-poly1305` | High | Fast (recommended) |
| `aes-256-gcm` | High | Fast with AES-NI hardware |
| `aes-128-gcm` | High | Faster than 256 variant |
| `xchacha20-ietf-poly1305` | High | Extended nonce variant |

`chacha20-ietf-poly1305` is recommended for most use cases. It performs well on all hardware including ARM devices without AES-NI.

### When to Use SS Keys

Shadowsocks keys are used in DNS Mode: tun2socks routes traffic through the SS client's SOCKS5 proxy (same data path as AWG). Only TCP is forwarded; UDP-based protocols will not work through SS. AWG configs are preferred because they support full TCP + UDP routing.

---

## Outline (SS+Prefix) Keys

Outline keys use the same Shadowsocks protocol as plain SS keys, but with an added **TLS prefix** that makes the traffic look like a TLS ClientHello handshake to DPI systems. This is required for Shadowsocks to work in Russia, where plain chacha20-ietf-poly1305 streams are detected and blocked by Roskomnadzor.

### ssconf:// URL Format

Outline keys are provided as `ssconf://` URLs rather than `ss://` URIs. The ssconf URL points to an HTTPS endpoint that returns the full connection config as JSON:

```
ssconf://HOST:PORT/TOKEN#DisplayName
```

When Proxima adds the key, it fetches the HTTPS endpoint to retrieve the server IP, port, password, method, and prefix.

### What ssconf Returns

```json
{
  "server": "46.224.49.250",
  "server_port": 8388,
  "password": "...",
  "method": "chacha20-ietf-poly1305",
  "prefix": "FgMBAgABAAH8AwM="
}
```

The `prefix` field (`FgMBAgABAAH8AwM=` = 11 bytes of a TLS 1.3 ClientHello header) is prepended to every handshake by the `outline-ss-local` client. To DPI, the connection looks like HTTPS. Both client and server must use matching prefix bytes.

### Adding Outline Keys via the UI

1. Go to the **Keys** page
2. Open the **Outline (SS+Prefix)** accordion section
3. Enter a descriptive name (e.g., "ERG-DE-Outline")
4. Paste the full `ssconf://` URL into the URL field
5. Click **Add**

Proxima fetches the ssconf endpoint in the background to validate the URL and store the config.

### Key Sources

| Source | Type | Notes |
|--------|------|-------|
| Self-hosted server (ERG-DE, ERG-FI) | `ssconf://IP:8390/TOKEN` | Self-signed cert — verify=False used internally |
| VanyaVPN | `ssconf://ododep.ru/vanya/UUID` | Real cert, 172 locations, key rotation supported |

### Self-Hosted Outline Setup

To run your own Outline exit server on any VPS, see the full guide:

> **[Self-Hosted Outline Server](/docs/self-hosted-outline.md)** — Deploy outline-ss-server v1.9.2 + ssconf endpoint in under 10 minutes.

### When to Use Outline Keys

- **DNS Mode in Russia**: Plain SS is blocked; Outline prefix makes traffic look like TLS
- **Russian LTE**: AWG UDP is blocked on many LTE carriers; Outline TCP (port 8388) bypasses this
- **Alternative to AWG**: When AWG is unavailable or when a TCP-only exit is sufficient
- **Limitation**: TCP only (same as basic SS) — no UDP/QUIC support through SOCKS5

---

## AmneziaWG Configs

AmneziaWG is a modified version of WireGuard with anti-DPI obfuscation. It adds junk packets and header manipulation to prevent deep packet inspection from identifying and blocking WireGuard traffic. This is essential in countries like Russia and Turkey where plain WireGuard is actively blocked.

### Config Structure

AWG configs follow the standard WireGuard `.conf` format with optional AmneziaWG extension fields:

```ini
[Interface]
PrivateKey = gI6EdUSYvn8ugXOt8QQD6Yc+JyiZi6DPfSoKjB8mCW0=
Address = 10.8.1.2/32
DNS = 1.1.1.1

[Peer]
PublicKey = HIgo9xNzJMWLKASShiTqIybxR0V1tB1YBjpBJ5F3C3c=
PresharedKey = 2LpYeM75QOnOqyReaDSrt+cjFANBGEJxDMA+8HFmH08=
AllowedIPs = 0.0.0.0/0
Endpoint = 185.199.110.1:51820
PersistentKeepalive = 25

# AmneziaWG extensions (optional)
Jc = 5
Jmin = 40
Jmax = 70
S1 = 0
S2 = 0
H1 = 1
H2 = 2
H3 = 3
H4 = 4
```

### Adding AWG Configs via the UI

1. Go to the **Keys** page
2. Open the **AWG Configs** accordion section
3. Enter a descriptive name (e.g., "Helsinki-AWG-1")
4. Paste the full `.conf` file content into the text area
5. Click **Add**

### Config Sanitization

When Proxima saves an AWG config, it automatically **sanitizes** the content to prevent conflicts inside the Docker container:

| Directive | Action | Reason |
|-----------|--------|--------|
| `DNS = ...` | **Removed** | DNS is handled by the host, not the tunnel |
| `Table = ...` | **Removed** | Replaced with `Table = off` |
| `PostUp = ...` | **Removed** | Custom scripts could conflict with container setup |
| `PostDown = ...` | **Removed** | Same as above |

Proxima then injects:

```ini
Table = off
```

This prevents the AWG interface from modifying the container's routing table, which would conflict with the container's internal networking. The `Table = off` directive ensures AWG only creates the tunnel interface without touching routes.

### AWG Container Architecture

Each AWG slot runs a container with two processes:

```
awg-client-slot-N:
  ├── awg-quick up wg0      (AmneziaWG tunnel interface)
  └── gost -L socks5://:1080 (SOCKS5 proxy exposed on port 1080)
```

In DNS Mode, tun2socks in the dns-router container connects to the AWG container's SOCKS5 proxy to route intercepted traffic through the tunnel.

### When to Use AWG Configs

AWG is the **preferred tunnel type for DNS Mode** because:

- Supports full TCP + UDP traffic (SS only supports TCP via SOCKS5)
- Anti-DPI obfuscation resists blocking in Russia and Turkey
- WireGuard-based protocol provides excellent performance and low latency
- Each config represents a full VPN connection, not just a proxy credential

---

## VLESS+Reality (Xray) Tunnels

VLESS with Reality is a censorship-resistant protocol that camouflages VPN traffic as normal HTTPS connections to a legitimate website.

### Adding a VLESS Config

1. Go to the **Keys & Tunnels** page
2. Click **New Tunnel Config**
3. Select type **Xray**
4. Fill in the required fields:
   - **Server** -- Xray server IP address
   - **Port** -- Server port (typically 443)
   - **VLESS UUID** -- Client UUID for authentication
   - **Reality Public Key** -- Server's Reality public key
   - **Short ID** -- Reality short ID
   - **Server Name (SNI)** -- Domain to impersonate (e.g., `www.googletagmanager.com`)
   - **Flow** -- `xtls-rprx-vision` (default)
   - **Fingerprint** -- TLS fingerprint to mimic (default: `chrome`)
   - **Tag** -- Display label (e.g., "Poland", "Germany")
5. Assign to a slot pool on the Dashboard

### Config Structure

```json
{
  "name": "VLESS-PL",
  "type": "xray",
  "server": "193.200.16.140",
  "port": 443,
  "vless_uuid": "your-uuid-here",
  "public_key": "reality-public-key",
  "short_id": "abc123",
  "server_name": "www.googletagmanager.com",
  "flow": "xtls-rprx-vision",
  "fingerprint": "chrome",
  "tag": "Poland"
}
```

### Xray Container Architecture

Each Xray slot runs a container with two processes:

```
xray-client-slot-N:
  +-- xray run -c config.json   (VLESS+Reality tunnel)
  +-- gost -L socks5://:1080    (SOCKS5 proxy exposed on port 1080)
```

In DNS Mode, tun2socks in the dns-router container connects to the Xray container's SOCKS5 proxy to route intercepted traffic through the tunnel.

### When to Use VLESS+Reality

- **Highly censored networks** -- Reality makes the connection indistinguishable from real HTTPS to DPI
- **IP-blocked WireGuard** -- VLESS uses TCP port 443, bypassing UDP-based protocol blocks
- **Chained tunnels** -- VLESS slots can be chained through an AWG slot for double encapsulation (see [Tunnel Chaining](#tunnel-chaining) below)
- **Limitation** -- TCP only (same as SS/Outline), no native UDP/QUIC support through SOCKS5

---

## Zapret (DPI Bypass)

Zapret is a DPI bypass tool that manipulates packets to evade deep packet inspection without using a VPN tunnel. It runs `nfqws2` with configurable arguments.

Zapret slots are useful for accessing websites that are only blocked by DPI (not by IP), where the overhead of a full VPN tunnel is unnecessary.

DPI bypass arguments can be configured per-slot via the API or Dashboard.

---

## Tunnel Chaining

Slots can be chained so one tunnel routes through another. On the Dashboard, each slot card has a **Via** dropdown to select a parent slot.

Example: Route a VLESS slot through an AWG slot for double encryption:
- slot-9 (Xray/VLESS) -> via slot-6 (AWG) -> Internet

Set `via_slot` to `null` or empty to route directly to the internet (default).

Chaining is validated by the API -- circular chains are rejected.

> **See also:** [DNS Mode](/docs/dns-mode.md#tunnel-chaining-via_slot) for the technical details of how chaining works at the nftables/routing level

---

## Pool Management

Each slot maintains an ordered **pool** of keys or configs. The pool is the foundation of Proxima's failover system.

### How Pools Work

A pool is an ordered list of credentials assigned to a slot:

```
slot-6 pool:
  [0]  awg-helsinki     <-- active (index 0)
  [1]  awg-berlin
  [2]  awg-amsterdam
```

The active credential is always at a known index. During failover, Proxima rotates to the next entry:

```
Failover triggered:
  current index: 0 (awg-helsinki failed)
  next index:    1 (awg-berlin activated)
```

### Adding to a Pool

Keys and configs must first be created on the **Keys** page. Then they can be added to a slot's pool:

1. Go to the **Dashboard**
2. Find the target slot card
3. Click **Manage Pool** (or the pool icon)
4. Select keys/configs to add from the available list
5. Click **Add to Pool**

Only credentials matching the slot type can be added:
- SS slots: only Shadowsocks keys
- Outline slots: only Outline (SS+Prefix) keys
- AWG slots: only AmneziaWG configs
- Xray slots: only VLESS+Reality configs

### Removing from a Pool

1. Open the slot's pool management
2. Click the remove icon next to the entry you want to remove
3. Confirm the removal

You cannot remove the currently active entry unless there is at least one other entry in the pool. A slot requires at least one pool entry to function.

### Pool Order

The order of entries in the pool determines the failover rotation sequence. The pool follows a simple circular rotation:

```
next_index = (current_index + 1) % pool_length
```

If the pool has 3 entries and the current active is at index 2, the next failover activates index 0 (wrapping around).

---

## Activation

The **active** key or config is the credential currently being used by a slot's tunnel container.

### Manual Activation

You can manually activate any entry in a slot's pool:

1. Go to the **Dashboard**
2. Find the slot card
3. Click on the desired pool entry
4. Click **Activate**

### Activation Sequence

Whether triggered manually or by failover, every activation follows the same sequence:

```
1. Write new config to disk
   - SS: writes ss-slot-N.json (ss-local config file)
   - AWG: writes awg-slot-N.conf (WireGuard config file)

2. Restart the tunnel container
   - Docker SDK restarts ss-client-slot-N or awg-client-slot-N
   - Container picks up the new config on startup

3. Wait 10 seconds
   - Allows the tunnel to establish connection
   - AWG handshake + gost SOCKS5 proxy startup

4. Run IP check
   - Verifies the tunnel is working by checking the exit IP
   - Uses ipify.org or similar service through the tunnel

5. Update health state
   - Records the new exit IP
   - Updates last_ip_check timestamp
   - Resets or increments failover counter
```

The 10-second wait is critical. Without it, the IP check would run against a tunnel that has not yet completed its handshake, producing false failures.

### Health State After Activation

After activation, the health state for the slot is updated:

```json
{
  "last_ip_check": "2026-04-27T14:30:00Z",
  "last_ip_ok": true,
  "last_ip": "89.105.208.130",
  "active_key": "awg-helsinki",
  "failover_count": 0
}
```

The UI immediately reflects the new state, showing the exit IP and health status on the Dashboard.

---

## Key Health Check

The manual key health check tests all keys or configs in a slot's pool for reachability. This is different from the scheduled health check, which only tests the active credential.

### Running a Health Check

1. Go to the **Keys** page
2. Click **Health Check** (or the check icon on a specific key)
3. Proxima tests each key/config by:
   - Temporarily configuring a test connection
   - Sending a request through the tunnel
   - Measuring latency (round-trip time)

### Health Check Results

| Status | Meaning |
|--------|---------|
| **Reachable** | Connection succeeded, latency measured |
| **Unreachable** | Connection failed (timeout, refused, or DNS error) |
| **Slow** | Connection succeeded but latency exceeds threshold |

Results are displayed as a table:

```
Name              Server            Latency    Status
awg-helsinki       185.199.110.1     45ms       Reachable
awg-berlin         203.0.113.50     120ms      Reachable
awg-amsterdam      198.51.100.1     --         Unreachable
```

### When to Run Health Checks

- **Before deployment** -- verify all pool entries work before relying on them
- **After VPN provider maintenance** -- servers may have changed IPs or gone offline
- **Periodic auditing** -- remove dead entries to improve failover speed
- **After adding new keys** -- confirm the credentials are correct and the server is reachable

---

## Failover Rotation

Failover is Proxima's automatic recovery mechanism. When a scheduled health check detects that the active tunnel is down, Proxima rotates to the next pool entry.

### Failover Trigger

Failover is triggered when:

1. **IP check fails** -- the tunnel cannot reach the IP check service
2. **All critical domains fail** -- every critical domain in every group using this slot is unreachable

> **See also:** [Health & Failover](/docs/health-failover.md) for the complete failover algorithm and [Domain Management](/docs/domains.md) for critical domain configuration

### Rotation Logic

```python
# Simplified failover rotation
next_index = (current_index + 1) % len(pool)
activate(pool[next_index])
```

The rotation is circular. After the last pool entry, it wraps back to the first.

### Single-Entry Pool Limitation

If a pool contains only one entry, failover **cannot rotate** to a different credential. Proxima logs a warning:

```
WARNING [SLOT-6] Failover triggered but pool has only 1 entry — cannot rotate
```

The single entry is restarted (container restart), which may resolve transient issues, but there is no alternative credential to try.

### Failover Sequence

```
1. Health check detects failure
2. Log: "SLOT-6 failover triggered, rotating from awg-helsinki to awg-berlin"
3. Calculate next pool index
4. Write new config to disk
5. Restart tunnel container
6. Wait 10 seconds
7. Run IP check on new config
8. If success:
   - Update health state with new IP
   - Increment failover counter
   - Log success
9. If failure:
   - Rotate to next pool entry (step 3)
   - Continue until all entries exhausted or one succeeds
```

### Failover Counter

Each slot tracks a `failover_count` that increments with each rotation. This counter is visible on the Dashboard and helps identify unstable tunnels:

- **0** -- No failovers since last manual activation
- **1-2** -- Normal, occasional server issues
- **High count** -- Indicates persistent problems with the pool

The counter resets when you manually activate a credential.

### Bypass Mode

If **all** pool entries fail during failover rotation, Proxima enters **bypass mode** for the affected slot:

1. Removes dnsmasq nftset entries for the slot's groups
2. Flushes the nftables sets
3. Traffic for those groups goes **direct** (no VPN)
4. IP check continues every 2 minutes to detect recovery
5. When a pool entry recovers, normal routing is restored

Bypass mode ensures that a total VPN outage does not break internet access for the network.

---

## Slot Enable/Disable

Each slot can be individually enabled or disabled from the Dashboard.

### Disabling a Slot

1. Go to the **Dashboard**
2. Find the slot card
3. Click the **Enable/Disable** toggle

When disabled:

- The tunnel container is **stopped** (Docker stop)
- Health checks skip this slot
- Groups assigned to this slot have their domains removed from dnsmasq config, traffic goes direct

### Re-Enabling a Slot

When re-enabled:

1. The tunnel container is **started** with the current active config
2. After 10 seconds, an IP check is performed
4. Health state is updated
5. Groups assigned to this slot resume VPN routing

### Use Cases for Disabling

- **Maintenance** -- temporarily disable a slot while updating VPN configs
- **Troubleshooting** -- isolate a problem by disabling one slot at a time
- **Resource savings** -- disable unused slots to free CPU and memory
- **Planned outage** -- disable before a VPN provider maintenance window

---

## Config File Generation

When a key or config is activated, Proxima writes the appropriate config file for the tunnel container.

### Shadowsocks Config (ss-slot-N.json)

```json
{
  "server": "185.199.110.1",
  "server_port": 8388,
  "local_address": "0.0.0.0",
  "local_port": 1080,
  "password": "MySecretPass",
  "method": "chacha20-ietf-poly1305",
  "mode": "tcp_and_udp"
}
```

Written to `/config/ss-slot-N.json` (e.g., `/config/ss-slot-1.json`) and read by `ss-local` inside the container.

### AmneziaWG Config (awg-slot-N.conf)

```ini
[Interface]
PrivateKey = gI6EdUSYvn8ugXOt8QQD6Yc+JyiZi6DPfSoKjB8mCW0=
Address = 10.8.1.2/32
Table = off

[Peer]
PublicKey = HIgo9xNzJMWLKASShiTqIybxR0V1tB1YBjpBJ5F3C3c=
PresharedKey = 2LpYeM75QOnOqyReaDSrt+cjFANBGEJxDMA+8HFmH08=
AllowedIPs = 0.0.0.0/0
Endpoint = 185.199.110.1:51820
PersistentKeepalive = 25
Jc = 5
Jmin = 40
Jmax = 70
S1 = 0
S2 = 0
H1 = 1
H2 = 2
H3 = 3
H4 = 4
```

Written to `/config/awg-slot-N.conf`. Note the sanitized output: `DNS`, `PostUp`, and `PostDown` are removed, and `Table = off` is injected.

---

## VPN Provider Considerations

### SS vs Outline vs AWG vs VLESS: Which to Use?

| Factor | Shadowsocks (ss://) | Outline (ssconf://) | AmneziaWG | VLESS+Reality (Xray) |
|--------|---------------------|---------------------|-----------|----------------------|
| **Protocol** | SOCKS5 proxy | SOCKS5 proxy + TLS prefix | Full VPN tunnel | SOCKS5 proxy (Reality camouflage) |
| **Traffic types** | TCP only | TCP only | TCP + UDP | TCP only |
| **DPI resistance** | Low (blocked in Russia) | High (looks like TLS) | High (obfuscated WireGuard) | Very high (indistinguishable from real HTTPS) |
| **Performance** | Good | Good | Excellent (kernel-level) | Good |
| **DNS Mode support** | TCP only (no UDP/QUIC) | TCP only (no UDP/QUIC) | Full support | TCP only (no UDP/QUIC) |
| **Works on Russian LTE** | No | Yes (TCP 8388) | No (UDP blocked) | Yes (TCP 443) |
| **QUIC/HTTP3** | Not supported | Not supported | Supported (when enabled) | Not supported |
| **Tunnel chaining** | No | No | Yes (as parent) | Yes (as child via AWG) |

**Recommendation:** Use AWG configs for DNS Mode. Use Outline (ssconf://) as a fallback for Russian LTE or when AWG UDP is blocked. Use VLESS+Reality when maximum DPI resistance is needed -- it can be chained through an AWG slot for double encapsulation. Plain ss:// keys are rarely needed -- prefer Outline for DPI resistance.

### Health Check Differences

Proxima uses slightly different health check methods depending on the tunnel type:

- **SS slots:** Uses `socks5h://` proxy (DNS resolved inside tunnel). Exception: if the SS key has DNS issues, `socks5://` can be used for local DNS resolution
- **AWG slots:** Uses `socks5://` (local DNS resolution) to avoid VPN provider DNS hijacking where providers return incorrect IPs for DNS queries inside the tunnel

> **Note:** VPN DNS hijacking is a known issue where providers intercept DNS queries inside the tunnel and return incorrect results. Using local DNS resolution (`socks5://`) for AWG health checks avoids this problem.

---

## Best Practices

### Keep at Least 2 Entries Per Pool

A single-entry pool cannot failover. Always maintain at least 2 configs per active slot:

```
slot-6 pool:
  [0]  awg-helsinki       <-- primary
  [1]  awg-berlin         <-- failover backup
```

This ensures that if one server goes down, Proxima can automatically switch to the backup.

### Use Descriptive Names

Name your keys and configs with a clear pattern that includes location and sequence:

```
Good:
  Finland-Helsinki-1
  Germany-Berlin-2
  Netherlands-Amsterdam-1

Bad:
  config1
  test
  new_key
```

Descriptive names make the Dashboard and health check results immediately understandable.

### Run Health Checks Regularly

Before relying on a pool for production traffic:

1. Run a manual health check on all entries
2. Remove entries that are consistently unreachable
3. Verify that the remaining entries have acceptable latency
4. Ensure at least 2 entries remain for failover

### AWG Configs for DNS Mode

For DNS Mode deployments, always prefer AmneziaWG over Shadowsocks:

- AWG supports full traffic routing (TCP + UDP) through tun2socks
- AWG's anti-DPI obfuscation is more robust against censorship
- AWG provides better performance for sustained traffic (kernel WireGuard)
- SS can only handle TCP, missing UDP-based protocols

### Monitor Failover Counts

A high failover count on the Dashboard indicates pool instability. Investigate by:

1. Running a manual health check on all pool entries
2. Checking if the VPN provider has server issues
3. Reviewing logs for connection error patterns
4. Replacing consistently failing entries with fresh configs

### Rotate VPN Credentials Periodically

Even if credentials are working, periodic rotation improves security:

1. Obtain new credentials from your VPN provider
2. Add them to the pool
3. Activate the new credential
4. Remove the old one after confirming the new one works

> **See also:** [Domain Management](/docs/domains.md) for configuring which domains use which slots, [Health & Failover](/docs/health-failover.md) for monitoring and failover details

---

## Speed Test

The Speed Test page measures actual tunnel throughput (download and upload speed) and latency for each active slot against a dedicated speed test server. This lets you compare real-world performance across your VPN tunnels rather than relying on latency alone.

### How It Works

Each slot's SOCKS5 proxy is used to route speed test traffic:

```
Speed test client  -->  SOCKS5 proxy (slot port)  -->  AWG/SS tunnel  -->  Speed test server
```

Tests run sequentially per slot, sharing a single HTTP session:

1. **Latency** — 5 HEAD requests to `/speedtest/ping`. Highest sample is dropped; remaining are averaged. The first request also serves as a TCP/TLS warmup for the session.
2. **Download** — A single streaming GET of N MB from `/speedtest/download?size=N`. Speed is calculated as bytes received / elapsed time.
3. **Upload** — N MB of random data POSTed to `/speedtest/upload`. Speed is calculated from bytes sent / elapsed time.

All three phases share one `requests.Session`, keeping the TLS connection alive across latency, download, and upload. This avoids repeated TLS handshakes and DPI re-inspection overhead (see [DPI section](#direct-test-and-dpi-blocking) below).

### TTFB (Time to First Byte)

TTFB is the elapsed time from when the download request is sent until the first byte of the response body arrives. It reflects connection setup overhead, TLS negotiation, and server processing time. A high TTFB (e.g., 4+ seconds) indicates DPI interference or a slow tunnel. With session reuse, TTFB for subsequent requests on the same connection is typically 30–150ms.

### Result Badges

| Badge | Meaning |
|-------|---------|
| **Full** | Download + upload + latency all measured successfully |
| **Partial** | Latency only — download/upload were skipped or timed out |
| **Error** | Latency also failed — slot unreachable or server down |

### Hairpin Limitation (AWG-ERG-DE)

If a slot's AWG tunnel endpoint IP is the **same host** as the speed test server, download and upload tests are automatically skipped. This is because WireGuard routes traffic destined for the tunnel endpoint directly (bypassing the tunnel), creating a routing loop that prevents data from flowing through the proxy as expected.

The affected slot shows a **Partial** badge with a note that DL/UL were skipped. Latency is still measured because HEAD requests are small and complete before the routing loop stalls them.

Detection is automatic: `_slot_endpoint_matches_server()` in `backend/core/speed_test.py` compares the parsed server hostname against the AWG config's `endpoint` field.

### Direct Test and DPI Blocking

The Speed Test page also offers a **Direct** test (no proxy, baseline measurement from the server itself). On Moscow-based servers (ERG, OFC), direct download/upload to the Germany speed test server is blocked by Russian ISP deep packet inspection (Roskomnadzor). Large TCP data transfers to foreign IPs are dropped after the connection is established.

With session reuse, the latency warmup request establishes the TCP/TLS connection and TTFB drops to ~40ms — but subsequent download and upload requests still fail because the DPI drops large data transfers. This means the Direct card shows a **Partial** badge (latency measured, DL/UL timed out). This is expected behavior.

AWG/WireGuard tunnel traffic bypasses DPI entirely, so tunneled tests are not affected by this limitation.

### Per-Key Test Type: Global vs Public

Each slot/key can be configured with one of two test types in the Settings modal:

| Type | Behavior |
|------|----------|
| **Global** | Uses the global speed test server URL and API key from Settings. The URL field is shown as a disabled label — not editable. |
| **Public** | Uses a per-key URL pointing to a public CDN speed test endpoint (e.g., Selectel, Yandex). No API key — authentication is not required. |

The Public type is useful for slots routed through non-ERG-DE tunnels where a geographically closer or CDN-hosted server gives more accurate measurements. Switching a key from Public back to Global clears the stored URL.

### Speed Test Server Configuration

The global speed test server URL and API key are configured in **Settings → Speed Test Server**.

| Setting | Description |
|---------|-------------|
| **URL** | Base URL of the speed test server (e.g., `https://46.224.49.250:8999`) |
| **API Key** | Bearer token for authentication |
| **Download size** | Test file size in MB |
| **Upload size** | Upload payload size in MB |

The server uses a self-signed TLS certificate (ECDSA P-256). SSL verification is disabled on the client side.

#### Speed Test Server Requirements

The speed test server (`speedtest-server.py` on ERG-DE) must be configured with:

- **HTTP/1.1**: `protocol_version = "HTTP/1.1"` on the handler — required for keep-alive connections. Python's `BaseHTTPRequestHandler` defaults to HTTP/1.0 which closes after each response, forcing a new TLS handshake per request.
- **ECDSA P-256 certificate**: Faster TLS handshakes than RSA 2048. Critical for low-latency warmup pings.
- **Large chunk size**: 1MB chunks with a single flush per response reduces syscall overhead compared to many small flushes.

### History Chart

The Speed Test page includes a history chart showing download and upload speeds over time per slot, allowing you to track tunnel performance trends and spot degradation.

### Tunnel Config Lookup

Speed test internally looks up a slot's AWG endpoint via the `tunnel_configs` list in config:

```python
# slot.active = config name string, e.g. "ERG-DE"
for awg_cfg in config.get("tunnel_configs", []):
    if awg_cfg.get("name") == active_key:
        endpoint = awg_cfg.get("endpoint", "").rsplit(":", 1)[0]  # strip port if present
```

**Important**: The `endpoint` field stores the **bare IP address only** — no port. Even though the raw `.conf` file contains `Endpoint = 46.224.49.250:443`, only the IP portion is stored when the config is parsed. The `rsplit(":", 1)[0]` call in `_slot_endpoint_matches_server()` handles both formats safely for forward compatibility.

This is why `endpoint` in each AWG config entry must be populated correctly — it is used for both display (Keys page) and hairpin detection (Speed Test).

> **Note:** The config key was renamed from `awg_configs` to `tunnel_configs` when SS support was added. A one-time migration runs automatically on startup.

> **See also:** [UI Guide](/docs/ui-guide.md) for the Speed Test page controls, [Deployment](/docs/deployment.md) for speed test server setup on ERG-DE
