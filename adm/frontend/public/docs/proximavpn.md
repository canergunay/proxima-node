# ProximaVPN

ProximaVPN is a WireGuard server integrated into Proxima that allows remote devices — especially mobile phones on LTE/5G networks — to connect to the home or office network and use DNS Mode VPN routing as if they were on the local network.

---

## Overview

When you're away from your home or office WiFi, your phone connects directly to the internet through the mobile carrier. In countries with active DPI (deep packet inspection), this means blocked services remain inaccessible on mobile data. ProximaVPN solves this by establishing a WireGuard tunnel from your phone to the Proxima host, where traffic enters the DNS Mode data plane and gets routed through VPN tunnels just like any other device on the network.

ProximaVPN is managed entirely from the Proxima web UI — peer creation, QR code generation, config export, and LAN access control are all available from the **ProximaVPN** page.

---

## Architecture

ProximaVPN uses a two-hop architecture:

```
Phone (LTE/5G)
    │
    │  WireGuard tunnel (domestic traffic)
    ▼
ERG / OFC server (Proxima host)
    │
    │  DNS Mode data plane (dnsmasq → nftables → tun2socks → AWG)
    ▼
VPN exit node (foreign server)
    │
    ▼
Internet (unblocked)
```

### Why This Works

The key insight is that the WireGuard hop from your phone to the Proxima host is **domestic traffic** — both endpoints are within the same country. Deep packet inspection systems in Russia and Turkey focus on blocking VPN tunnels that cross international borders. Domestic WireGuard connections are used by many legitimate services (corporate VPNs, smart home systems, gaming) and are not typically inspected or blocked.

Once the traffic reaches the Proxima host, it enters the same DNS Mode data plane that handles all local network traffic:

1. DNS queries go to dnsmasq, which populates nftables sets with resolved IPs
2. nftables marks matching packets with the appropriate fwmark
3. Policy routing sends marked packets to the tun0 interface
4. tun2socks forwards traffic through gost SOCKS5 to the AWG tunnel
5. Traffic exits through the VPN server in another country

This means ProximaVPN peers get the exact same routing rules, domain groups, bandwidth shaping, and failover protection as devices connected directly to the LAN.

### Network Path Detail

```
Phone (10.14.14.2)
    │
    │  WireGuard (UDP 5555) ─── domestic, not inspected by DPI
    ▼
ERG wg1 interface (10.14.14.1)
    │
    │  FORWARD (wg1 → tun0)
    ▼
nftables mark matching ─── same rules as LAN devices
    │
    │  fwmark 0x1 → policy routing → tun0
    ▼
tun2socks (198.18.0.1) → gost SOCKS5 → AWG tunnel
    │
    ▼
VPN exit (e.g., 89.105.208.130)
```

---

## WireGuard Server Setup

ProximaVPN uses a standard WireGuard interface (`wg1`) on the Proxima host, separate from the AWG tunnels used for VPN exit.

### Interface Naming Convention

Both ERG and OFC deployments use the same interface layout:

| Interface | Purpose | Port | Managed by |
|-----------|---------|------|------------|
| `wg1` | **ProximaVPN** server — peers connect here | 5555/UDP | Proxima (`vpn_server` config) |
| `wg0` | Backup WireGuard tunnel (not Proxima-managed) | 51820/UDP | Manual / systemd |

**Important:** ProximaVPN is always `wg1`, never `proximavpn` or any other name. The backend reads the interface name from `vpn_server.interface` in `proxima-config.json` (default: `wg1`). The `wg0` interface is a separate, non-Proxima backup connection and should not be modified by Proxima.

### Interface Configuration

| Parameter | Default | Notes |
|-----------|---------|-------|
| Interface name | `wg1` | Same on both ERG and OFC — never rename |
| Subnet | `10.14.14.0/24` (ERG) / `10.15.15.0/24` (OFC) | Configurable from Settings |
| Listen port | `5555/UDP` | Configurable from Settings |
| Server IP | First address in subnet | Assigned to wg1 |

### Server Keys

The WireGuard server key pair is generated during initial setup:

```
/etc/wireguard/wg1-server.key    # Private key (chmod 600)
/etc/wireguard/wg1-server.pub    # Public key
```

### wg1.conf Structure

The `wg1.conf` file is managed by Proxima. It contains the server interface definition and all peer entries:

```ini
[Interface]
PrivateKey = <server-private-key>
Address = 10.14.14.1/24
ListenPort = 5555
MTU = 1280
PostUp = iptables -A FORWARD -i wg1 -o tun0 -j ACCEPT; iptables -A FORWARD -i tun0 -o wg1 -j ACCEPT; iptables -A FORWARD -i wg1 -o tun1 -j ACCEPT; iptables -A FORWARD -i tun1 -o wg1 -j ACCEPT; iptables -A FORWARD -i wg1 -o tun2 -j ACCEPT; iptables -A FORWARD -i tun2 -o wg1 -j ACCEPT; iptables -A FORWARD -i wg1 -o tun3 -j ACCEPT; iptables -A FORWARD -i tun3 -o wg1 -j ACCEPT; iptables -A FORWARD -i wg1 -o tun4 -j ACCEPT; iptables -A FORWARD -i tun4 -o wg1 -j ACCEPT; iptables -A FORWARD -i wg1 -o enp3s0 -j ACCEPT; iptables -t nat -A POSTROUTING -s 10.14.14.0/24 -o enp3s0 -j MASQUERADE; iptables -t nat -A PREROUTING -i wg1 -p udp --dport 53 -j REDIRECT --to-port 53
PostDown = iptables -D FORWARD -i wg1 -o tun0 -j ACCEPT; iptables -D FORWARD -i tun0 -o wg1 -j ACCEPT; iptables -D FORWARD -i wg1 -o tun1 -j ACCEPT; iptables -D FORWARD -i tun1 -o wg1 -j ACCEPT; iptables -D FORWARD -i wg1 -o tun2 -j ACCEPT; iptables -D FORWARD -i tun2 -o wg1 -j ACCEPT; iptables -D FORWARD -i wg1 -o tun3 -j ACCEPT; iptables -D FORWARD -i tun3 -o wg1 -j ACCEPT; iptables -D FORWARD -i wg1 -o tun4 -j ACCEPT; iptables -D FORWARD -i tun4 -o wg1 -j ACCEPT; iptables -D FORWARD -i wg1 -o enp3s0 -j ACCEPT; iptables -t nat -D POSTROUTING -s 10.14.14.0/24 -o enp3s0 -j MASQUERADE; iptables -t nat -D PREROUTING -i wg1 -p udp --dport 53 -j REDIRECT --to-port 53

[Peer]
# Phone - Can
PublicKey = <peer-public-key>
AllowedIPs = 10.14.14.2/32
```

**Key configuration details:**

- **MTU = 1280**: Required for LTE connections. Mobile carriers often add encapsulation overhead, and the WireGuard tunnel adds its own. Without this, large packets get silently dropped, causing TLS handshake failures and slow page loads.
- **DNS REDIRECT rule**: `iptables -t nat -A PREROUTING -i wg1 -p udp --dport 53 -j REDIRECT --to-port 53` ensures DNS queries from WG peers reach the local dnsmasq, even if the client config specifies a different DNS. Uses REDIRECT (not DNAT) because the destination is the same host.
- **Multi-tunnel FORWARD rules**: All tun interfaces (tun0–tun4) need FORWARD rules for WG peers. Without rules for each tun interface, per-group routing to non-default tunnels will silently fail for VPN peers.

### Router Port Forward

The WireGuard port must be forwarded from the router to the Proxima host:

| Router | Configuration |
|--------|---------------|
| **Keenetic** (ERG) | Network Rules > Port Forwarding > UDP 5555 to 192.168.2.91:5555 |
| **MikroTik** (OFC) | IP > Firewall > NAT > dstnat UDP 5555 to 192.168.77.121:5555 |

The router's public IP (or a DDNS hostname) is used as the endpoint in peer configs.

### Autostart

Enable the WireGuard interface to start on boot:

```bash
systemctl enable wg-quick@wg1
systemctl start wg-quick@wg1
```

To verify the interface is running:

```bash
wg show wg1
```

---

## Peer Management

Peers are managed from the **ProximaVPN** page in the Proxima web UI.

### Adding a Peer

1. Navigate to the ProximaVPN page
2. Click **Add Peer**
3. Enter a name for the device (e.g., "Phone - Can", "Tablet - Guest")
4. Proxima auto-generates:
   - A WireGuard key pair (private + public key)
   - The next available IP from the subnet (e.g., 10.14.14.2, 10.14.14.3, ...)
5. Choose whether to enable LAN access for this peer
6. Click **Save**

### Peer Properties

Each peer has the following properties:

| Property | Description |
|----------|-------------|
| **Name** | Human-readable label for the device |
| **Public key** | WireGuard public key (shown in server config) |
| **Private key** | WireGuard private key (included in client config, never stored on server after generation) |
| **Assigned IP** | Static IP from the ProximaVPN subnet |
| **LAN access** | Whether the peer can reach local network services |
| **Owner** | Optional link to a VPN user account (see [User Management](/docs/user-management.md)) |
| **VLESS UUID** | Auto-generated UUID v4 for sing-box VLESS protocol (see [sing-box Config](#sing-box-config) below) |
| **Created** | Timestamp of peer creation |
| **Last handshake** | Last WireGuard handshake time (from `wg show`) |

### QR Code Generation

Each peer gets two QR codes for easy mobile setup:

- **AmneziaVPN QR** — Formatted for the AmneziaVPN app (recommended, has split tunneling)
- **WireGuard QR** — Standard WireGuard format, compatible with the official WireGuard app

Scan the QR code with the respective app to import the configuration instantly.

### Config Export

For manual import or desktop clients, the full WireGuard config text is available:

```ini
[Interface]
PrivateKey = <peer-private-key>
Address = 10.14.14.2/32
DNS = 192.168.2.91

[Peer]
PublicKey = <server-public-key>
Endpoint = <public-ip>:5555
AllowedIPs = 1.0.0.0/8, 2.0.0.0/7, 4.0.0.0/6, ..., 10.14.14.0/24, 192.168.2.0/24, 192.168.1.0/24
PersistentKeepalive = 25
```

The `AllowedIPs` field uses split-tunnel routing — RFC1918 private ranges (10/8, 172.16/12, 192.168/16) are excluded so traffic to local network devices goes directly, bypassing the tunnel. The VPN subnet and configured LAN subnets are re-added explicitly so peers can still reach other VPN clients and server-side LAN resources.

The config can be copied to clipboard or downloaded as a `.conf` file.

> **After any backend update** that changes AllowedIPs generation, existing QR codes are stale. Regenerate configs via the QR icon in the ProximaVPN table.

### Peer Ownership

Peers can be linked to VPN user accounts through the `owner` field. This enables a self-service model:

- **Admin-created peers** -- No owner set. Managed exclusively by admins from the Proxima web UI.
- **User-owned peers** -- Owner set to a VPN user. The user can view, configure, and delete their own peers from the ProximaVPN client app.

When a user has a `max_peers` limit set on their account, peer creation is enforced -- they cannot create more peers than their quota allows. Peers without an owner do not count against any user's quota.

### Removing a Peer

Removing a peer from the UI deletes its entry from `wg1.conf` and reloads the WireGuard interface. The peer's assigned IP becomes available for reuse.

---

## sing-box Config

Each peer gets a `vless_uuid` field -- an auto-generated UUID v4 that serves as the user ID for sing-box VLESS+Reality protocol. This UUID is not related to WireGuard itself; it is used by the sing-box config generator to produce client configurations for VLESS protocol clients.

### Config Generation Endpoint

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/vpn/peers/<id>/singbox` | Returns a sing-box compatible JSON config for VLESS+Reality |

The generated config includes the peer's `vless_uuid` as the VLESS user ID along with the server's Reality public key and other connection parameters. This allows peers to connect using sing-box based clients as an alternative to WireGuard.

### Profile Endpoint

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/vpn/peers/<id>/profile` | Returns the WireGuard client config (text format) |
| `GET` | `/api/vpn/peers/<id>/profile?format=qr` | Returns the config as a QR code image |

The profile endpoint provides a direct URL for downloading the WireGuard config or displaying a scannable QR code. This is used by both the Proxima web UI and the ProximaVPN client app.

---

## User System Integration

ProximaVPN integrates with the [VPN user system](/docs/user-management.md) to support multi-user peer management. When per-user auth is enabled:

- **Admins** can create peers for any user or without an owner
- **Users** can create and manage their own peers (up to their `max_peers` limit)
- User routing mode (`full` or `selected`) and assigned groups determine how the peer's traffic is routed
- Disabling or deleting a user does not remove their owned peers, but the peers lose their owner association

### ProximaVPN Client App

The ProximaVPN client app supports connecting to multiple Proxima servers. Users:

1. Add a server by entering the Proxima hostname/IP and port
2. Log in with their VPN user credentials
3. See their owned peers across all connected servers
4. Create new peers, view configs, scan QR codes, and delete peers
5. Download sing-box configs for VLESS+Reality connections

This multi-server support allows a single user to manage peers across both ERG and OFC (or any other Proxima deployment) from one app.

---

## Peer Limits

Each peer can have per-group access control and bandwidth limits configured from the Proxima UI.

### Configuration

Click the gear icon (⚙) on any peer in the ProximaVPN page to open the **Peer Limits Drawer**.

**Structure:**

```json
{
  "limits": {
    "enabled": true,
    "bandwidth": { "download": "50mbit", "upload": "10mbit" },
    "groups": {
      "youtube": { "access": true, "bandwidth": { "download": "20mbit" } },
      "casino": { "access": false },
      "ai": { "access": true }
    }
  }
}
```

**Rules:**
- `limits` absent or `null` = no restrictions (backward compatible)
- `limits.enabled = false` = unrestricted even if groups are configured
- Groups NOT listed in `limits.groups` = `access: true` (allowed by default — limits are restrictions)
- Bandwidth values follow the pattern `^\d+[kmg]?bit$` (e.g., `50mbit`, `1gbit`)

### Compare Matrix

The **Compare** button in the ProximaVPN header switches to a matrix view showing all peers × groups:

- Rows = domain groups, columns = peers
- Cells show access status (✓ allowed / ✗ blocked) and bandwidth limits
- Click any cell to open the limits drawer for that peer
- Useful for reviewing access policies across multiple peers at once

### Enforcement (Planned)

Currently, peer limits are stored in configuration only and displayed in the UI. Enforcement via nftables rules and tc/HTB bandwidth shaping on the `wg1` interface is planned for Phase 2:

- **Access blocking**: `nft add rule ... ip saddr <peer_ip> ip daddr @group_<id> drop`
- **Bandwidth shaping**: tc/HTB classes per peer IP on wg1
- **Scale**: up to 253 peers × 15 groups = ~3800 rules — well within nftables performance limits

### API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `PUT` | `/api/vpn/peers/<name>` | Update peer properties including `limits` |

Send `{ "limits": null }` to remove all limits, or `{ "limits": { "enabled": true, "groups": { ... } } }` to set them. Bandwidth values are validated server-side against the pattern.

---

## LAN Access Toggle

Each peer has an independent **LAN Access** toggle that controls whether the device can reach local network services.

### When Enabled

- Peer can access LAN resources: NAS, printers, media servers, home automation
- Peer can access the Proxima web UI directly
- `AllowedIPs` in the peer config includes all configured LAN subnets
- FORWARD rules permit traffic from wg1 to the LAN interface (e.g., enp3s0)
- Masquerade NAT translates the WG subnet source to the server's LAN IP

### When Disabled

- Peer can **only** use VPN routing through DNS Mode
- No access to LAN resources or the Proxima web UI via LAN IP
- FORWARD DROP rules are created for each configured LAN subnet, blocking the peer's IP at the server
- Note: `AllowedIPs` in the peer config still includes LAN subnets (for split-tunnel routing), but the server-side DROP rules make those routes unreachable. Server enforcement is authoritative.
- Useful for guest devices or untrusted peers that should only get VPN access

### LAN Subnets Configuration

By default, Proxima derives a single `/24` subnet from the server's LAN IP. However, many home and office networks span multiple subnets (e.g., the server is on `192.168.2.0/24` but a parent router network at `192.168.1.0/24` also hosts devices). The `lan_subnets` setting allows you to explicitly list all LAN subnets that should be controlled by the LAN Access toggle.

**Configuration in `proxima-config.json`:**

```json
{
  "lan_subnets": ["192.168.2.0/24", "192.168.1.0/24"]
}
```

**Behavior:**

- When `lan_subnets` is set, LAN access rules (DROP when disabled) are applied to **every listed subnet**
- When `lan_subnets` is not set, a single `/24` is derived from the server's `server_ip` setting (legacy behavior)
- Adding or removing subnets in Settings triggers an async re-apply of all peer LAN access rules
- Old rules from previously configured subnets are cleaned up automatically
- Each subnet is validated as a valid CIDR notation (e.g., `192.168.2.0/24`)

**UI:** The LAN Subnets setting is available in Settings > Network as a chip-based editor (same interaction pattern as Local Domains).

### Implementation

The LAN access control works at two levels:

1. **Client-side** (`AllowedIPs` in peer config) — determines what traffic the client sends through the tunnel
2. **Server-side** (nftables/iptables FORWARD rules) — enforces access policy regardless of client config

Server-side enforcement is the authoritative control. Even if a client modifies their `AllowedIPs`, the server's FORWARD rules prevent unauthorized LAN access. When LAN access is disabled for a peer, a DROP rule is created for **each** configured LAN subnet, ensuring no subnet is accidentally left accessible.

---

## Client Setup

### Recommended: AmneziaVPN App

AmneziaVPN is the recommended client for Android and iOS.

1. Install AmneziaVPN from your app store
2. Open the ProximaVPN page in Proxima UI
3. Scan the **AmneziaVPN QR code** with the app
4. Connect — no additional split tunneling configuration needed

### Alternative: Official WireGuard App

The standard WireGuard app also works:

1. Install WireGuard from your app store
2. Scan the **WireGuard QR code** or import the `.conf` file
3. Connect

### DNS Configuration

The client config sets DNS to the Proxima server IP (e.g., `192.168.2.91`). This is critical for DNS Mode integration — DNS queries must go through dnsmasq so that resolved IPs are added to nftables sets for proper routing.

If you change DNS to a public resolver (e.g., 8.8.8.8), domain-based routing will not work because dnsmasq won't see the queries and nftables sets won't be populated.

### Split Tunneling

ProximaVPN generates split-tunnel `AllowedIPs` automatically — you don't need to configure this in the app. The generated config:

- **Routes internet traffic through the tunnel** — all public IPs go via the Proxima host and into DNS Mode
- **Bypasses the tunnel for local network traffic** — RFC1918 ranges (10/8, 172.16/12, 192.168/16) are excluded, so devices on your current WiFi/LAN are accessible directly regardless of which network you're on
- **Re-includes the VPN subnet** (e.g., 10.14.14.0/24) so you can reach other ProximaVPN peers
- **Re-includes configured LAN subnets** (e.g., 192.168.2.0/24) so you can reach server-side resources

This means: whether you're at home, at the office, or at a coffee shop, you can always reach local devices without the tunnel getting in the way.

For app-level exclusions (banking apps, VoIP), configure those inside the AmneziaVPN or WireGuard app per your preference.

---

## nftables Integration

ProximaVPN peers are treated as first-class network participants in DNS Mode. The dns-router container handles the integration automatically.

### Configuration

In `proxima-config.json`, the WireGuard server interface is declared:

```json
{
  "settings": {
    "vpn_server_interfaces": ["wg1"]
  }
}
```

This tells dns-router to create FORWARD rules for the WireGuard interface.

### FORWARD Rules

The dns-router entrypoint script generates these rules for each interface in `vpn_server_interfaces`. With multi-tunnel routing, rules are created for all active tun interfaces:

```
# Allow WG peers to reach all VPN tunnels (tun0–tun4 for up to 5 slots)
nft add rule inet filter forward iifname "wg1" oifname "tun0" accept
nft add rule inet filter forward iifname "tun0" oifname "wg1" accept
nft add rule inet filter forward iifname "wg1" oifname "tun1" accept
nft add rule inet filter forward iifname "tun1" oifname "wg1" accept
nft add rule inet filter forward iifname "wg1" oifname "tun2" accept
nft add rule inet filter forward iifname "tun2" oifname "wg1" accept
nft add rule inet filter forward iifname "wg1" oifname "tun3" accept
nft add rule inet filter forward iifname "tun3" oifname "wg1" accept
nft add rule inet filter forward iifname "wg1" oifname "tun4" accept
nft add rule inet filter forward iifname "tun4" oifname "wg1" accept

# Allow WG peers to reach LAN (when LAN access enabled)
nft add rule inet filter forward iifname "wg1" oifname "enp3s0" accept
```

> **Important:** Rules must cover all active tun interfaces, not just tun0. If a domain group routes to slot-3 (tun2) or slot-4 (tun3) and the wg1↔tunN FORWARD rule is missing, ProximaVPN peers silently fail to access those groups while LAN devices work fine.

### Masquerade

For non-proxied traffic (domains not in any group), WG peers need masquerade NAT to reach the internet through the server's LAN connection:

```
nft add rule ip nat postrouting ip saddr 10.14.14.0/24 oifname "enp3s0" masquerade
```

This translates the WG peer's source address (10.14.14.x) to the server's LAN IP so the traffic can route through the default gateway.

### Packet Flow for WG Peers

```
1. Phone sends packet to youtube.com IP
2. Arrives at wg1 on server (10.14.14.1)
3. nftables prerouting: ct mark restore → check nftset membership
4. If IP is in an nftset → mark packet (fwmark)
5. Policy routing: fwmark → tun0 → tun2socks → AWG → VPN exit
6. If IP is NOT in any nftset → forward via default route → direct internet
```

---

## QUIC Handling

QUIC (HTTP/3) runs over UDP port 443 and presents a challenge for the DNS Mode data plane. Since gost's UDP ASSOCIATE through AWG is unreliable (UDP packets are silently lost), Proxima blocks QUIC to force clients to fall back to TCP (HTTP/2 or HTTP/1.1).

### The Problem on Mobile

Originally, QUIC was blocked using the `DROP` action in nftables:

```
nft add rule inet filter forward udp dport 443 drop
```

This worked fine for desktop browsers, which quickly detect QUIC failure and switch to TCP. However, mobile apps (especially the YouTube app) are less tolerant:

- `DROP` silently discards packets with no response
- The app waits for a timeout before retrying on TCP
- This caused noticeable 3-5 second delays when loading videos

### The Fix: REJECT Instead of DROP

Changing to `REJECT` sends an ICMP "port unreachable" response:

```
nft add rule inet filter forward udp dport 443 reject
```

The ICMP response tells the client immediately that UDP 443 is not available, triggering an instant TCP fallback. This reduced the perceived delay from seconds to near-zero.

### Impact

| Action | Desktop browser | Mobile app |
|--------|----------------|------------|
| `DROP` | Fast fallback (built-in timeout) | Slow (3-5s timeout) |
| `REJECT` | Instant fallback | Instant fallback |

The `REJECT` approach is used for all DNS Mode traffic, not just ProximaVPN peers.

---

## Use Cases

### Access Blocked Services on Mobile Data

The primary use case. When connected to LTE/5G, your phone uses ProximaVPN to reach the home server, where DNS Mode routes traffic through VPN tunnels. YouTube, Telegram, Instagram, and other blocked services work just like they do on home WiFi.

### Bypass Carrier-Level DPI

Mobile carriers often apply their own DPI in addition to country-level blocking. Since ProximaVPN is a domestic WireGuard tunnel to your own server, it bypasses carrier-level inspection entirely. The carrier sees encrypted WireGuard traffic to a domestic IP — indistinguishable from any corporate VPN.

### Remote LAN Access

With the LAN Access toggle enabled, ProximaVPN gives you access to home network services from anywhere:

- NAS file access (Synology, TrueNAS)
- Media streaming (Jellyfin, Plex)
- Home automation dashboards
- Proxima web UI for management
- Printers and other network devices

### Consistent DNS Mode on All Devices

ProximaVPN ensures your phone gets the same DNS Mode routing as your desktop, laptop, and other LAN devices. The same domain groups, the same VPN tunnels, the same failover protection — regardless of whether you're on WiFi or mobile data.

---

## Troubleshooting

### Peer Can't Connect

1. Verify the WireGuard interface is running: `wg show wg1`
2. Check the router port forward: UDP 5555 must reach the server
3. Verify the public IP or DDNS hostname in the peer's Endpoint field
4. Check the server's firewall: `ufw allow 5555/udp`

### Connected But No Internet

1. Verify DNS is set to the Proxima server IP in the peer config
2. Check that dnsmasq is running: `docker ps | grep dnsmasq`
3. Check FORWARD rules for all tun interfaces: `nft list ruleset | grep wg1`
4. Verify masquerade NAT: `nft list table ip nat`
5. Check the DNS REDIRECT rule exists: `iptables -t nat -L PREROUTING | grep wg1`

### LTE Connections Fail (TLS Handshake Timeout)

If WiFi works but LTE doesn't, the likely cause is MTU issues:

1. Verify `MTU = 1280` is set in `wg1.conf` `[Interface]` section
2. LTE carriers add encapsulation overhead, and without reduced MTU, large packets (especially TLS handshakes) get silently dropped
3. After changing MTU: `systemctl restart wg-quick@wg1`

### Slow Performance

1. Check the AWG tunnel health on the Dashboard
2. Verify QUIC is being rejected (not dropped): check dns-router nftables rules
3. Check bandwidth shaping limits in Group settings
4. Try disabling split tunneling temporarily to rule out client-side issues
5. Note: LTE connections inherently add 30-500ms of jitter -- this is carrier-side and cannot be optimized

### Handshake But No Traffic

1. Check the `iif tun0 lookup main` rule: `ip rule show`
2. This rule must exist with lower priority than the fwmark rule
3. Without it, return packets from tun0 get re-marked and loop
4. With multi-tunnel setup, also check `iif tun1` and `iif tun2` rules

> **See also:** [Architecture](/docs/architecture.md) for the DNS Mode data plane details, [Health & Failover](/docs/health-failover.md) for tunnel monitoring
