# User Management

Proxima supports per-user authentication for DNS Mode, allowing administrators to control which devices on the network get VPN routing and which ones go direct. This document covers the user system, device authentication, per-user routing modes, and security considerations.

---

## Overview

By default, DNS Mode routes **all** traffic from **all** devices on the network through the VPN. Per-user authentication changes this so that only devices belonging to authenticated users get VPN routing. Everyone else -- guests, IoT devices, work computers -- uses direct internet.

This feature is essential for shared networks where not every device should be routed through VPN.

---

## The Problem

### Without Per-User Auth

In standard DNS Mode, any device that uses the Proxima server as its DNS server and gateway gets VPN routing automatically:

```
Phone (guest)      ──┐
Laptop (user)      ──┤── DNS → dnsmasq → nftables mark → VPN
Smart TV           ──┤
Work PC            ──┤
IoT thermostat     ──┘
```

This creates several issues:

- **Guest devices** on the WiFi get routed through VPN unnecessarily
- **IoT devices** may break when routed through a foreign VPN exit
- **Work devices** should not have their traffic routed through a personal VPN
- **Bandwidth** is consumed by devices that do not need VPN access
- **Cross-site access breaks** -- if the gateway is set network-wide, traffic between LAN sites (e.g., ERG to OFC) goes through VPN and loses local routing

### With Per-User Auth

```
Phone (guest)      ── DNS → dnsmasq → no mark → DIRECT
Laptop (user)      ── DNS → dnsmasq → nftables mark → VPN    [authenticated]
Smart TV           ── DNS → dnsmasq → no mark → DIRECT
Work PC            ── DNS → dnsmasq → no mark → DIRECT
IoT thermostat     ── DNS → dnsmasq → no mark → DIRECT
```

Only the laptop, whose user has logged in to Proxima, gets VPN routing. Every other device goes direct, which is the safe default.

---

## Per-User Auth Concept

### Network Default: Direct

When per-user auth is enabled, the network default is **direct internet**. No device gets VPN routing unless its user has explicitly authenticated.

This is a deliberate security choice:

- New devices on the network work immediately (no config needed)
- Guests get normal internet without any action
- VPN routing is opt-in, not opt-out

### Authentication Flow

```
1. User connects device to network (WiFi/Ethernet)
2. Device gets IP via DHCP
3. User opens Proxima web UI in browser
4. User logs in with username + password
5. Backend records device IP → adds to nftables "authenticated" set
6. Device traffic now matches nftables rules → routed through VPN
7. On logout or session expiry → IP removed from "authenticated" set
8. Device returns to direct routing
```

### Session Lifecycle

```
           Login
             |
             v
    +-----------------+
    |  authenticated  |   Device IP in nftset
    |     session     |   Traffic → VPN
    +-----------------+
         |       |
    Refresh    Expire/Logout
         |       |
         v       v
    +--------+  +--------+
    | Extend |  | Remove |  Device IP removed from nftset
    | session|  | from   |  Traffic → DIRECT
    +--------+  | nftset |
                +--------+
```

Sessions are automatically refreshed when the user:

- Opens the Proxima web UI
- Switches back to the Proxima tab (visibility change event)
- Performs any authenticated API call

This prevents sessions from expiring while the user is actively using their device.

---

## User Roles

Proxima defines two user roles with different permission levels.

### Admin

| Permission | Access |
|------------|--------|
| Dashboard | Full access |
| Groups & Domains | Create, edit, delete |
| Keys & AWG Configs | Create, edit, delete |
| Settings | Full access including intervals, bandwidth, account |
| Users | Create, edit, delete users |
| Device Management | View and disconnect all devices |
| Health Checks | Trigger manual checks |
| Failover | Manual failover trigger |
| Logs | Full log viewer access |
| Performances | View and reset performance data |
| Per-User Auth | Enable/disable the feature |
| Community DB | Browse, import, sync |

### User

| Permission | Access |
|------------|--------|
| Dashboard | View-only (slot status, health indicators) |
| Groups & Domains | View-only |
| Device Management | View and manage own devices only |
| Settings | Change own password only |
| Health Checks | No access |
| Logs | No access |
| Performances | No access |
| User Management | No access |

The role distinction ensures that regular users cannot accidentally change VPN configuration or trigger failovers, while still being able to authenticate their devices and view the network status.

---

## User CRUD

Administrators manage users through the Users page in the web UI.

### Create User

| Field | Required | Description |
|-------|----------|-------------|
| Username | Yes | Unique identifier, used for login |
| Password | Yes | Minimum 8 characters, hashed with bcrypt |
| Role | Yes | `admin` or `user` |
| Enabled | Yes | Whether the user can log in (default: true) |
| Max Peers | No | Maximum number of WireGuard peers the user can own (default: unlimited) |
| Bandwidth Quota | No | Monthly bandwidth quota for the user (e.g., `50gb`) |
| Speed Download | No | Download speed limit (e.g., `50mbit`) |
| Speed Upload | No | Upload speed limit (e.g., `10mbit`) |
| Assigned Groups | No | Which domain groups apply to this user's traffic |
| Routing Mode | No | `full` (all traffic via VPN) or `selected` (only assigned group domains via VPN) |

Passwords are never stored in plaintext. Proxima uses bcrypt with a work factor of 12 for password hashing.

### Edit User

Administrators can modify any user account:

- **Change password** -- Sets a new bcrypt-hashed password
- **Change role** -- Promote user to admin or demote to user
- **Enable/disable** -- Temporarily block a user without deleting their account. Disabling a user:
  - Invalidates all active sessions
  - Removes all device IPs from the authenticated nftset
  - Device traffic immediately returns to direct routing

### Delete User

Deleting a user:

1. Invalidates all active sessions for that user
2. Removes all device IPs from the authenticated nftset
3. Disconnects all devices immediately (traffic goes direct)
4. Removes the user record from the configuration

**Safety rule**: You cannot delete your own admin account. This prevents accidentally locking yourself out of the system. At least one admin account must always exist.

### Password Requirements

- Minimum 8 characters
- No maximum length (bcrypt handles any length)
- No complexity requirements enforced (the admin is trusted to choose reasonable passwords)
- Passwords are hashed with bcrypt (cost factor 12) before storage

---

## Device Authentication

When a user logs in, their device is registered and tracked by IP address.

### Three-Tier nftset Architecture

Device authentication uses three tiers of nftables sets to control routing granularity:

| nftset | Purpose | Populated when |
|--------|---------|----------------|
| `authenticated` | Gate set — device is authenticated and allowed through per-user auth check | Any user logs in |
| `full_vpn` | Full routing — all traffic from this IP goes through VPN | User has `routing_mode: "full"` |
| `auth_{group_id}` | Per-group routing — only traffic matching this group's domains goes through VPN | User has `routing_mode: "selected"` with this group assigned |

A device with `routing_mode: "full"` gets added to both `authenticated` and `full_vpn`. A device with `routing_mode: "selected"` gets added to `authenticated` plus one `auth_{group_id}` set for each of their assigned groups. This allows nftables to make fine-grained routing decisions per user without needing per-user chains.

### Device Registration

On successful login, the backend:

1. Extracts the client IP from the HTTP request
2. Creates a device record linked to the user
3. Adds the IP to the appropriate nftsets based on the user's routing mode (`authenticated` + `full_vpn` or `authenticated` + per-group sets)
4. Returns a JWT session token to the client

### Device Identification

Devices are identified by a combination of attributes:

| Attribute | Source | Purpose |
|-----------|--------|---------|
| Username | Login credentials | Links device to user |
| DHCP hostname | DHCP lease table | Human-readable device name |
| IP address | HTTP request source | Used for nftables matching |
| Session token | JWT | Validates ongoing sessions |

**Why not MAC addresses?** Modern iOS and Android devices use MAC address randomization by default. A device's MAC address changes each time it connects to the network (or periodically while connected). This makes MAC-based identification unreliable. IP addresses, while also dynamic, are stable for the duration of a DHCP lease and are directly usable in nftables rules.

### Device List

Each user can see their own authenticated devices. Admins can see all devices across all users.

Device information displayed:

| Field | Description |
|-------|-------------|
| Device name | DHCP hostname (e.g., "iPhone-Can", "laptop-work") |
| IP address | Current IP on the network |
| User | Which user authenticated this device |
| Authenticated since | When the device was last authenticated |
| Last activity | When the session was last refreshed |
| Status | Active / Expired |

### Disconnecting Devices

Both users and admins can disconnect devices:

- **Users**: Can disconnect their own devices only
- **Admins**: Can disconnect any device belonging to any user

Disconnecting a device:

1. Removes the device IP from the nftables `authenticated` set
2. Invalidates the session token
3. Traffic from that IP immediately returns to direct routing
4. The user must log in again to re-authenticate the device

---

## Per-User Routing Modes

Admins can assign a routing mode to each user, controlling how their authenticated devices handle traffic.

### Full VPN

```
ALL traffic → VPN
```

- All traffic from the user's devices goes through VPN
- Recommended for **home networks** where broad VPN coverage is desired
- Ensures maximum privacy -- everything is tunneled

### Selected Domains

```
Group domains → VPN
ALL other traffic → DIRECT
```

- Only traffic to domains in assigned groups goes through VPN
- Everything else routes directly
- Recommended for **office networks** where minimal VPN usage is preferred
- Reduces VPN bandwidth consumption
- Lower risk of breaking internal services

### Routing Mode Comparison

| Aspect | Full VPN | Selected Domains |
|--------|----------|------------------|
| Default for new traffic | VPN | Direct |
| Domain list purpose | All traffic tunneled | Only listed domains use VPN |
| Bandwidth usage | Higher | Lower |
| Privacy | Higher | Lower |
| Risk of breakage | Higher (everything tunneled) | Lower (only selected domains) |
| Best for | Home use | Office use |

### How Routing Modes Interact with nftables

```
Per-User Routing:
  1. dnsmasq resolves domain → checks if domain is in a group
  2. If in group → add IP to group's nftset
  3. nftables: if src IP in "authenticated" AND dst IP in group nftset → mark → VPN
  4. If not in group → no nftset → no mark → DIRECT
```

---

## Enabling Per-User Auth

Per-user authentication is an opt-in feature controlled from the Users page.

### Toggle Behavior

| State | Effect |
|-------|--------|
| **Disabled** (default) | All LAN traffic gets VPN routing (original DNS Mode behavior). No user login required. |
| **Enabled** | Only authenticated device IPs get nftables marks. Unauthenticated devices go direct. |

### Enabling Per-User Auth

1. Navigate to the Users page
2. Toggle the "Per-User Authentication" switch
3. Confirm the action (warning dialog explains the impact)
4. Backend updates nftables rules to check the `authenticated` set
5. All currently unauthenticated devices immediately lose VPN routing

**Warning**: Enabling per-user auth when no users have authenticated devices means ALL traffic goes direct until someone logs in. Make sure at least one admin device is authenticated before enabling.

### Disabling Per-User Auth

1. Toggle the switch off
2. Backend removes the `authenticated` set check from nftables
3. All LAN traffic gets VPN routing again (original behavior)
4. Existing user sessions remain valid but have no functional effect

---

## Security Considerations

### IP-Based Authentication Limitations

Per-user auth relies on IP addresses for traffic identification. This has inherent limitations on a LAN:

| Risk | Description | Mitigation |
|------|-------------|------------|
| **IP spoofing** | A device could spoof an authenticated IP | Low risk on trusted LANs; ARP spoofing requires local access |
| **DHCP lease changes** | Device gets a new IP after lease expires | Session refresh re-registers the new IP |
| **Shared IPs** | NAT or proxy could share an IP | Rare on flat LANs; document if nested NAT exists |
| **Stale sessions** | Device disconnects, IP reassigned | Session expiry + periodic cleanup removes stale entries |

### Session Token Security

- **JWT tokens** are signed with a server-side secret
- **Token expiry** prevents indefinite access
- **Token refresh** on app interaction extends active sessions
- **Token invalidation** on logout/disconnect immediately revokes access
- **HTTPS recommended** -- tokens are transmitted in HTTP headers; HTTPS prevents interception

### Audit Logging

Proxima maintains audit logs for user authentication events:

| Event | Logged Data |
|-------|-------------|
| User login | Username, device IP, DHCP hostname, timestamp |
| User logout | Username, device IP, timestamp |
| Device disconnect | Admin username, target device IP, target user, timestamp |
| Session refresh | Username, device IP, timestamp |
| Auth toggle | Admin username, new state (enabled/disabled), timestamp |

Additionally, dnsmasq query logs provide a record of which DNS queries came from which IPs. Combined with the user-to-IP mapping, this creates a complete audit trail of which user accessed which domains.

### Log Retention

- **Authentication events**: Stored in Proxima's log file with 7-day rotation
- **DNS query logs**: dnsmasq logs with configurable retention
- **Recommended retention**: 90 days for compliance and troubleshooting
- Logs are stored on the Docker volume at `/config/proxima.log`

### Rate Limiting

The login endpoint (`/api/auth/login`) is rate-limited to prevent brute-force attacks. Repeated failed login attempts from the same IP address are throttled with increasing delays. This applies to both the Proxima web UI login and the ProximaVPN client app login.

### Best Practices

1. **Use strong passwords** -- At least 12 characters for admin accounts
2. **Limit admin accounts** -- Only create admin accounts for people who need full system access
3. **Review device list regularly** -- Disconnect devices that should no longer have VPN access
4. **Enable per-user auth on shared networks** -- Do not route guest traffic through VPN
5. **Use allowlist mode for office** -- Minimize the attack surface and bandwidth impact
6. **Monitor audit logs** -- Check for unexpected device registrations or login attempts
7. **Set up DHCP reservations** -- For critical devices, reserve their IPs in the router to prevent lease changes from disrupting sessions

---

## Peer Ownership

WireGuard peers (managed on the ProximaVPN page) can be linked to VPN users via the `owner` field. When a peer has an owner:

- The peer appears in the user's "My Peers" list in the ProximaVPN client app
- The user can manage (view config, regenerate QR, delete) their own peers
- Admin-imposed limits on `max_peers` are enforced -- users cannot create more peers than their quota allows
- Peers without an owner remain admin-managed and are not visible to regular users

Each peer also receives a `vless_uuid` field (auto-generated UUID v4) used by the sing-box config generator for VLESS protocol clients. This UUID is not related to WireGuard itself -- it serves as a unique identifier for the sing-box VLESS+Reality configuration endpoint.

---

## Monthly Usage Tracking

Proxima tracks per-user bandwidth consumption on a monthly basis. Usage data is aggregated from traffic counters associated with the user's authenticated device IPs. This data powers:

- **Usage display** -- Each user can see their own monthly consumption
- **Quota enforcement** -- When a user's `bandwidth_quota` is set, traffic is tracked against it
- **Admin overview** -- Admins can view usage across all users for capacity planning

Usage counters reset at the start of each calendar month.

---

## Onboarding Flow

The typical flow for adding a new VPN user to the system:

```
1. Admin creates a VPN user account (username, password, routing mode, groups)
2. Admin shares credentials with the user (out-of-band)
3. User installs the ProximaVPN client app on their device
4. User adds the Proxima server (hostname/IP + port) in the app
5. User logs in with their VPN user credentials
6. App registers the device → backend adds IP to nftsets
7. VPN routing is now active for the user's device
8. User can create WireGuard peers (up to max_peers) from the app
```

For LAN users (devices already on the home/office network), the onboarding is simpler -- they log in via the Proxima web UI in a browser, and their device IP is immediately authenticated for VPN routing.

---

## Implementation Phases

Per-user authentication is being implemented in three phases:

### Phase 1: User CRUD + IP Auth + nftset

- Admin can create, edit, and delete users
- Users log in and their device IP is added to the `authenticated` nftset
- Per-user auth toggle enables/disables the feature
- Basic device list with connect/disconnect

### Phase 2: Per-User Groups + Tracking

- Per-user routing mode assignment (full/selected)
- Per-user group assignment (which groups apply to which users)
- Per-user traffic tracking and reporting
- Device activity history

### Phase 3: Bandwidth Limits + Reporting

- Per-user bandwidth limits
- Usage reports and dashboards
- Bandwidth alerts and notifications
- Historical usage data with charts

---

## Summary

```
                    +------------------+
                    |   Proxima Web UI |
                    +--------+---------+
                             |
                       Login (user/pass)
                             |
                             v
                    +------------------+
                    |   Flask Backend  |
                    |                  |
                    |  - Validate creds|
                    |  - Create session|
                    |  - Record device |
                    +--------+---------+
                             |
                    Add IP to nftset
                             |
                             v
                    +------------------+
                    |    nftables      |
                    |                  |
                    |  "authenticated" |
                    |   set contains:  |
                    |  192.168.2.50    |
                    |  192.168.2.103   |
                    +--------+---------+
                             |
                    Packet arrives from 192.168.2.50
                             |
                             v
                    +------------------+
                    |  src IP in set?  |
                    |                  |
                    +---+----------+---+
                        |          |
                       Yes         No
                        |          |
                        v          v
                   Mark packet   DIRECT
                   fwmark 0x1    (no VPN)
                        |
                        v
                   Policy routing
                   → tun0 → VPN
```

> **See also:** [Architecture](/docs/architecture.md) for system design details, [Health & Failover](/docs/health-failover.md) for monitoring and failover
