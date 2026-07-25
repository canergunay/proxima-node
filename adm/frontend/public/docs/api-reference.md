# API Reference

Complete REST API documentation for Proxima. All endpoints are served by the Flask backend, typically at `http://SERVER_IP:5000`.

---

## Table of Contents

- [General](#general)
- [Authentication](#authentication)
- [Status](#status)
- [Slots](#slots)
- [Groups](#groups)
- [Domains](#domains)
- [Keys](#keys)
- [AWG Configs](#awg-configs)
- [Tunnel Configs](#tunnel-configs)
- [Settings](#settings)
- [Performances](#performances)
- [Users](#users)
- [Devices](#devices)
- [VPN Server](#vpn-server)
- [VPN Users](#vpn-users)
- [Mode](#mode)
- [Proxy Gateway](#proxy-gateway)
- [IPList](#iplist)
- [Network Trace](#network-trace)
- [Operations](#operations)
- [Scheduler](#scheduler)
- [Tunnel Health](#tunnel-health)
- [Bandwidth](#bandwidth)
- [Logs](#logs)

---

## General

### Response Format

All API responses follow a consistent JSON structure:

**Success:**
```json
{
  "ok": true,
  "data": { ... }
}
```

**Error:**
```json
{
  "ok": false,
  "error": "Description of the error"
}
```

### Authentication

Most API endpoints require JWT authentication. Include the token in the `Authorization` header:

```
Authorization: Bearer <jwt_token>
```

**Exceptions that do NOT require authentication:**
- `POST /api/auth/setup` (first-run account creation)
- `POST /api/auth/login`
- `GET /api/auth/me` (returns auth status without requiring a token)
- Static files and documentation pages

### Content Type

All request and response bodies use `application/json` unless otherwise noted.

### Long-Running Operations

Many endpoints (IP checks, restarts, domain checks, traces) start background operations and return immediately with an `op_id`. Poll `GET /api/operations` to track progress.

```json
{
  "ok": true,
  "data": {
    "op_id": "abc123",
    "message": "IP check started for slot-6"
  }
}
```

---

## Authentication

### POST /api/auth/setup

Create the initial admin account. Only works when no user account exists (first run).

**Request:**
```json
{
  "username": "admin",
  "password": "mypassword"
}
```

**Validation:**
- Username must be at least 2 characters
- Password must be at least 4 characters

**Response (201):**
```json
{
  "ok": true,
  "data": {
    "token": "eyJhbGciOiJIUzI1NiIs...",
    "role": "admin"
  }
}
```

**Errors:**
- `400` — Username or password too short
- `409` — Admin account already exists

---

### POST /api/auth/login

Authenticate and receive a JWT token.

**Request:**
```json
{
  "username": "admin",
  "password": "mypassword"
}
```

**Response (200):**
```json
{
  "ok": true,
  "data": {
    "token": "eyJhbGciOiJIUzI1NiIs...",
    "role": "admin"
  }
}
```

On successful login, the user's IP is registered as an authenticated device (for per-user auth in DNS Mode).

**Errors:**
- `400` — Auth not configured (use setup first)
- `401` — Invalid credentials or account disabled

---

### POST /api/auth/logout

Log out and remove device IP from the authenticated nftset.

**Response (200):**
```json
{
  "ok": true,
  "data": {
    "message": "Logged out"
  }
}
```

---

### GET /api/auth/me

Get current authentication status and user info. Works without a token to check if setup is needed.

**Response (unauthenticated, no setup):**
```json
{
  "ok": true,
  "data": {
    "auth_configured": false
  }
}
```

**Response (authenticated):**
```json
{
  "ok": true,
  "data": {
    "auth_configured": true,
    "username": "admin",
    "role": "admin"
  }
}
```

**Errors:**
- `401` — Auth is configured but no valid token provided

---

### POST /api/auth/refresh-device

Refresh the calling device's IP in the authenticated nftset. Called by the PWA on browser visibility change events to keep device auth alive.

**Response (200):**
```json
{
  "ok": true,
  "data": {
    "ip": "192.168.2.100"
  }
}
```

**Errors:**
- `401` — Not authenticated
- `404` — User not found in database

---

### PUT /api/auth/password

Change the current user's password.

**Request:**
```json
{
  "current_password": "oldpass",
  "new_password": "newpass"
}
```

**Response (200):**
```json
{
  "ok": true,
  "data": {
    "message": "Password changed"
  }
}
```

**Errors:**
- `400` — New password too short (minimum 4 characters)
- `401` — Current password incorrect or not authenticated

---

## Status

### GET /api/status

Get a comprehensive summary of the entire system: all slots, health state, mode, deployment info, DNS Mode status, proxy gateway status, and bypass state.

**Response (200):**
```json
{
  "ok": true,
  "data": {
    "server_ip": "192.168.2.91",
    "mode": "dns",
    "setup_complete": true,
    "deployment": "ERG",
    "dns_mode": {
      "active": true,
      "containers": {
        "dnsmasq": "running",
        "dns-router": "running"
      }
    },
    "proxy_gateway": {
      "enabled": true,
      "slot": "slot-6",
      "running": true
    },
    "bypass_active": false,
    "bypass_slots": [],
    "slots": {
      "slot-6": {
        "label": "AWG Primary",
        "type": "awg",
        "port": 8086,
        "direct": false,
        "active": "de-nuremberg-1",
        "pool": ["de-nuremberg-1", "de-nuremberg-2"],
        "health": {
          "last_ip_check": 1745700000,
          "last_ip_ok": true,
          "last_ip": "89.105.208.130",
          "last_domain_check": 1745699000,
          "last_domain_ok": true,
          "failover_count": 0,
          "bypass_active": false,
          "bypass_since": null
        }
      }
    },
    "settings": {
      "ip_check_interval_min": 30,
      "domain_check_interval_min": 60,
      "ip_retries": 2,
      "domain_retries": 2,
      "total_vpn_bandwidth": "100mbit",
      "per_user_auth": false
    }
  }
}
```

---

## Slots

### GET /api/slots

List all slot configurations with current health state.

**Response (200):**
```json
{
  "ok": true,
  "data": [
    {
      "id": "slot-6",
      "label": "AWG Primary",
      "port": 8086,
      "direct": false,
      "enabled": true,
      "type": "awg",
      "socks_port": 1086,
      "active": "de-nuremberg-1",
      "pool": ["de-nuremberg-1", "de-nuremberg-2"],
      "health": {
        "last_ip_check": 1745700000,
        "last_ip_ok": true,
        "last_ip": "89.105.208.130",
        "last_domain_check": 1745699000,
        "last_domain_ok": true,
        "domain_ok_count": 12,
        "domain_total_count": 12,
        "failover_count": 0,
        "key_stats": {}
      }
    }
  ]
}
```

---

### GET /api/slots/:id

Get a specific slot's configuration and health.

**Response (200):** Same structure as individual items in `GET /api/slots`.

**Errors:**
- `404` — Slot not found

---

### POST /api/slots

Create a new tunnel slot with auto-assigned ID and SOCKS port.

**Request:**
```json
{
  "label": "My Tunnel",
  "type": "awg"
}
```

**Fields:**
- `label` (required) — Display name for the slot
- `type` (optional, default `"awg"`) — Slot type: `"awg"`, `"outline"`, `"xray"`, or `"zapret"`
- `dpi_args` (optional, zapret only) — nfqws2 strategy arguments

**Response (201):**
```json
{
  "ok": true,
  "data": {
    "id": "slot-9",
    "label": "My Tunnel",
    "port": null,
    "direct": false,
    "enabled": true,
    "type": "awg",
    "socks_port": 1089,
    "active": null,
    "pool": [],
    "health": { ... }
  }
}
```

For Outline, Xray, and Zapret slots, a Docker container is created automatically. If container creation fails, a `container_warning` field is included in the response.

**Errors:**
- `400` — Missing label or invalid type

---

### DELETE /api/slots/:id

Delete a tunnel slot. Stops and removes the associated container(s) and removes the slot from config.

**Response (200):**
```json
{
  "ok": true,
  "data": null
}
```

**Errors:**
- `400` — Cannot delete a DIRECT slot
- `404` — Slot not found

---

### PUT /api/slots/:id/via-slot

Set or clear tunnel chaining — route this slot's traffic through another slot.

**Request (set):**
```json
{
  "via_slot": "slot-6"
}
```

**Request (clear):**
```json
{
  "via_slot": null
}
```

**Response (200):** Updated slot object.

**Behavior:**
- Triggers dns-router reload when the via_slot changes
- Circular chain detection: if setting via_slot would create a loop (e.g., A→B→A), returns 400

**Errors:**
- `400` — Cannot chain a DIRECT slot, cannot chain to self, circular chain detected, or target slot is disabled
- `404` — Slot or via_slot not found

---

### PUT /api/slots/:id/dpi-args

Update the zapret nfqws2 DPI bypass strategy arguments for a zapret slot. Recreates the zapret container with the new arguments.

**Request:**
```json
{
  "dpi_args": "--dpi-desync=fake --dpi-desync-ttl=4"
}
```

Send an empty string to reset to default arguments.

**Response (200):** Updated slot object.

**Errors:**
- `400` — Slot is not a zapret type
- `404` — Slot not found
- `500` — Failed to recreate container

---

### POST /api/slots/:id/activate

Activate a specific key or AWG config for a slot. Runs in background: writes config, restarts container, waits 10s, checks IP.

**Request:**
```json
{
  "key": "de-nuremberg-1"
}
```

**Response (200):**
```json
{
  "ok": true,
  "data": {
    "op_id": "act-abc123",
    "message": "Activating de-nuremberg-1 on slot-6"
  }
}
```

**Errors:**
- `400` — Missing key field
- `404` — Slot or key/config not found

---

### POST /api/slots/:id/restart

Restart the tunnel client container for a slot. Runs in background: restarts container, waits 10s, checks IP.

**Response (200):**
```json
{
  "ok": true,
  "data": {
    "op_id": "rst-abc123",
    "message": "Restarting slot-6"
  }
}
```

**Errors:**
- `400` — Cannot restart a DIRECT slot
- `404` — Slot not found

---

### PUT /api/slots/:id/enabled

Enable or disable a slot. Disabling stops the tunnel container. Enabling starts it and triggers an IP check.

**Request:**
```json
{
  "enabled": false
}
```

**Response (200):**
```json
{
  "ok": true,
  "data": {
    "id": "slot-6",
    "label": "AWG Primary",
    "enabled": false,
    "op_id": "tog-abc123",
    ...
  }
}
```

**Errors:**
- `400` — Missing/invalid `enabled` field, or cannot toggle DIRECT slot
- `404` — Slot not found

---

### PUT /api/slots/:id/label

Update the display label for a slot.

**Request:**
```json
{
  "label": "AWG Germany"
}
```

**Response (200):** Updated slot object.

**Errors:**
- `400` — Label cannot be empty
- `404` — Slot not found

---

### PUT /api/slots/:id/pool

Replace the failover key/config pool for a slot.

**Request:**
```json
{
  "pool": ["de-nuremberg-1", "de-nuremberg-2", "nl-amsterdam-1"]
}
```

**Behavior:**
- If the currently active key is removed from the pool, it is deactivated.
- If the pool was empty and a key is added, the first key is auto-activated.

**Response (200):** Updated slot object.

**Errors:**
- `400` — Missing or invalid pool array
- `404` — Slot or key/config not found

---

### POST /api/slots/:id/check-ip

Manually trigger an IP check for a specific slot. Runs in background.

**Response (200):**
```json
{
  "ok": true,
  "data": {
    "op_id": "ipc-abc123",
    "message": "IP check started for slot-6"
  }
}
```

**Errors:**
- `400` — Cannot check IP for DIRECT slot
- `404` — Slot not found

---

### POST /api/slots/:id/check-domains

Manually trigger a domain check for a specific slot. Runs in background.

**Response (200):**
```json
{
  "ok": true,
  "data": {
    "op_id": "dmc-abc123",
    "message": "Domain check started for slot-6"
  }
}
```

**Errors:**
- `400` — Cannot check domains for DIRECT slot
- `404` — Slot not found

---

### POST /api/slots/check-all-ip

Trigger IP checks for all enabled, non-DIRECT slots. Runs sequentially in background.

**Response (200):**
```json
{
  "ok": true,
  "data": {
    "op_id": "bipc-abc123",
    "message": "IP check started for 3 slots"
  }
}
```

---

### POST /api/slots/check-all-domains

Trigger domain checks for all enabled, non-DIRECT slots. Runs sequentially in background.

**Response (200):**
```json
{
  "ok": true,
  "data": {
    "op_id": "bdmc-abc123",
    "message": "Domain check started for 3 slots"
  }
}
```

---

### POST /api/slots/restart-all

Restart all enabled, non-DIRECT slot containers, wait for startup, then check IPs. Runs in background.

**Response (200):**
```json
{
  "ok": true,
  "data": {
    "op_id": "brst-abc123",
    "message": "Restarting 3 slots"
  }
}
```

---

## Groups

### GET /api/groups

List all groups with domain counts.

**Response (200):**
```json
{
  "ok": true,
  "data": [
    {
      "id": "messaging",
      "label": "MESSAGING",
      "slot": "slot-6",
      "iplist_group": null,
      "custom_domains": ["telegram.org", "web.telegram.org"],
      "critical_domains": ["telegram.org"],
      "bandwidth": { "min": "5mbit", "max": "20mbit" },
      "block_ipv6": true,
      "domain_count": 45
    }
  ]
}
```

---

### GET /api/groups/summary

List groups with counts only (no full domain arrays). More efficient for the group overview display.

**Response (200):**
```json
{
  "ok": true,
  "data": [
    {
      "id": "messaging",
      "label": "MESSAGING",
      "slot": "slot-6",
      "iplist_group": "telegram",
      "domain_count": 45,
      "custom_count": 5,
      "iplist_count": 40,
      "critical_count": 3,
      "bandwidth": { "min": "5mbit", "max": "20mbit" },
      "block_ipv6": true
    }
  ]
}
```

---

### GET /api/groups/all-domains

Get all domains across all groups with source and group info. Used by the paginated domain table.

**Response (200):**
```json
{
  "ok": true,
  "data": [
    {
      "domain": "telegram.org",
      "group_id": "messaging",
      "group_label": "MESSAGING",
      "source": "custom",
      "critical": true,
      "note": "Primary domain"
    },
    {
      "domain": "t.me",
      "group_id": "messaging",
      "group_label": "MESSAGING",
      "source": "iplist",
      "critical": false
    }
  ]
}
```

**Source values:**
- `custom` — User-added domain
- `iplist` — Synced from iplist.opencck.org
- `static` — IP/CIDR entry

---

### GET /api/groups/domain-status

Get recent health check results for domains.

**Query parameters:**

| Parameter | Description |
|-----------|-------------|
| `domains` | Comma-separated domain list (most efficient) |
| `group_id` | Get status for all domains in a specific group |
| *(none)* | Get status for all domains across all groups |

**Response (200):**
```json
{
  "ok": true,
  "data": {
    "telegram.org": [
      {
        "ts": 1745700000,
        "ok": true,
        "http_status": 200,
        "exit_ip": "149.154.167.99",
        "egress_ip": "89.105.208.130"
      }
    ]
  }
}
```

Each domain has up to 5 most recent check results.

**Fields:**
- `exit_ip` — The resolved destination IP (domain's A record)
- `egress_ip` — The tunnel exit IP at the time of the check (from the slot's last IP check). Used by the UI to verify traffic exited through the correct tunnel.

---

### POST /api/groups

Create a new group.

**Request:**
```json
{
  "label": "STREAMING",
  "slot": "slot-6",
  "iplist_group": "youtube"
}
```

**Fields:**
- `label` (required) — Display name
- `slot` (required) — Slot ID or `"block"`
- `iplist_group` (optional) — Link to an iplist.opencck.org domain category

**Response (201):**
```json
{
  "ok": true,
  "data": {
    "id": "streaming",
    "label": "STREAMING",
    "slot": "slot-6",
    "iplist_group": "youtube",
    "custom_domains": []
  }
}
```

**Errors:**
- `400` — Missing label or invalid slot

---

### PUT /api/groups/:id

Update a group's properties.

**Request (all fields optional):**
```json
{
  "label": "VIDEO STREAMING",
  "slot": "slot-7",
  "block_ipv6": true,
  "bandwidth": {
    "min": "10mbit",
    "max": "50mbit"
  }
}
```

**Bandwidth format:** Values must match pattern `\d+[kmg]?bit` (e.g., `5mbit`, `100kbit`, `1gbit`). Set to `null` or `{}` to remove bandwidth limits.

**Response (200):** Updated group object.

**Errors:**
- `400` — Empty label or invalid bandwidth format
- `404` — Group not found

---

### DELETE /api/groups/:id

Delete a group and all its domain assignments.

**Response (200):**
```json
{
  "ok": true,
  "data": null
}
```

**Errors:**
- `404` — Group not found

---

### POST /api/groups/:id/domains

Add a single custom domain to a group.

**Request:**
```json
{
  "domain": "youtube.com",
  "critical": true,
  "note": "Main video platform"
}
```

**Accepts:**
- Domain names (e.g., `youtube.com`, `api.openai.com`)
- IP addresses (e.g., `149.154.167.50`)
- CIDR ranges (e.g., `149.154.160.0/20`)

**Response (201):** Updated group object.

**Errors:**
- `400` — Missing or invalid domain
- `404` — Group not found
- `409` — Domain already exists in this group **or** in another group

**Cross-group duplicate error (409):**
```json
{
  "ok": false,
  "error": "Domain already exists in group 'STREAMING'",
  "existing_group_id": "streaming",
  "existing_group_label": "STREAMING"
}
```

---

### DELETE /api/groups/:id/domains/:domain

Remove a custom domain from a group. Only custom domains can be removed (iplist domains are managed by sync).

**Response (200):** Updated group object.

**Errors:**
- `404` — Group or domain not found

---

### PUT /api/groups/:id/domains/:domain/critical

Toggle the critical flag for a domain. Critical domains trigger failover when unreachable during domain checks.

**Request:**
```json
{
  "critical": true
}
```

**Response (200):** Updated group object.

**Errors:**
- `404` — Group or domain not found

---

### PUT /api/groups/:id/domains/:domain/note

Set or clear a note for a domain.

**Request:**
```json
{
  "note": "Required for push notifications"
}
```

Send an empty string or omit `note` to clear.

**Response (200):**
```json
{
  "ok": true
}
```

**Errors:**
- `404` — Group not found

---

### PUT /api/groups/:id/critical-domains

Replace the entire critical domains list for a group.

**Request:**
```json
{
  "critical_domains": ["telegram.org", "web.telegram.org"]
}
```

**Response (200):** Updated group object.

**Errors:**
- `400` — Invalid or missing array, or domains not in group
- `404` — Group not found

---

### POST /api/groups/:id/domains/bulk

Add multiple custom domains at once. In-group duplicates are skipped. Cross-group duplicates are reported separately.

**Request:**
```json
{
  "domains": ["youtube.com", "ytimg.com", "ggpht.com", "googlevideo.com"]
}
```

**Response (201 if any added, 200 if all skipped):**
```json
{
  "ok": true,
  "data": {
    "added": ["ytimg.com", "ggpht.com"],
    "skipped": ["youtube.com"],
    "duplicates": [
      {
        "domain": "googlevideo.com",
        "group_id": "streaming",
        "group_label": "STREAMING"
      }
    ],
    "added_count": 2,
    "skipped_count": 1,
    "duplicate_count": 1
  }
}
```

- `skipped` — domains already in this group
- `duplicates` — domains that exist in a different group (not added)

**Errors:**
- `400` — Missing or empty domains array
- `404` — Group not found

---

### POST /api/groups/:id/domains/:domain/move

Move a custom domain from one group to another. Only custom domains can be moved.

**Request:**
```json
{
  "target_group_id": "streaming"
}
```

**Response (200):**
```json
{
  "ok": true
}
```

**Behavior:** The domain's note is moved with it. Critical status is cleared on move.

**Errors:**
- `400` — Missing target_group_id
- `404` — Source group, target group, or domain not found
- `409` — Domain already exists in target group

---

### POST /api/groups/:id/check-domains

Trigger a domain health check for this group's assigned slot.

**Response (200):**
```json
{
  "ok": true,
  "data": {
    "message": "Domain check started for slot-6"
  }
}
```

**Errors:**
- `400` — Cannot check domains for DIRECT slot
- `404` — Group not found

---

## Domains

Cross-group domain operations.

### GET /api/domains/search

Search domains across all groups (iplist + custom).

**Query parameters:**

| Parameter | Description | Default |
|-----------|-------------|---------|
| `q` | Search query (minimum 2 characters) | *(required)* |
| `limit` | Maximum results (max 500) | 100 |

**Response (200):**
```json
{
  "ok": true,
  "data": [
    {
      "domain": "youtube.com",
      "group_id": "streaming",
      "group_label": "STREAMING",
      "source": "custom",
      "critical": true
    }
  ],
  "truncated": false
}
```

**Errors:**
- `400` — Query too short

---

### POST /api/domains/check-duplicate

Check if a domain exists in any group.

**Request:**
```json
{
  "domain": "youtube.com"
}
```

**Response (200):**
```json
{
  "ok": true,
  "data": {
    "exists": true,
    "groups": [
      {
        "group_id": "streaming",
        "group_label": "STREAMING",
        "source": "custom"
      }
    ]
  }
}
```

---

### POST /api/domains/bulk

Bulk move or delete custom domains across groups.

**Request (move):**
```json
{
  "action": "move",
  "target_group_id": "streaming",
  "items": [
    { "domain": "youtube.com", "group_id": "ai" },
    { "domain": "ytimg.com", "group_id": "ai" }
  ]
}
```

**Request (delete):**
```json
{
  "action": "delete",
  "items": [
    { "domain": "old-domain.com", "group_id": "messaging" }
  ]
}
```

**Response (200):**
```json
{
  "ok": true,
  "data": {
    "moved": 2,
    "deleted": 0
  }
}
```

Only custom domains can be moved/deleted. IPList domains are managed by sync.

**Errors:**
- `400` — Invalid action or missing items

---

### GET /api/groups/export

Export all groups as portable JSON (without slot assignments) for cross-server sync.

**Response (200):**
```json
{
  "ok": true,
  "data": {
    "version": 2,
    "exported_at": 1745700000,
    "source": "ERG",
    "groups": [
      {
        "id": "messaging",
        "label": "MESSAGING",
        "iplist_group": "telegram",
        "custom_domains": ["telegram.org", "web.telegram.org"],
        "critical_domains": ["telegram.org"],
        "bandwidth": { "min": "5mbit" },
        "block_ipv6": true
      }
    ]
  }
}
```

---

## Keys

Shadowsocks key management.

### GET /api/keys

List all Shadowsocks keys.

**Response (200):**
```json
{
  "ok": true,
  "data": [
    {
      "name": "de-nuremberg-1",
      "server": "185.123.45.67",
      "port": 8388,
      "method": "chacha20-ietf-poly1305",
      "password": "secret123"
    }
  ]
}
```

---

### GET /api/keys/:name

Get a specific key.

**Response (200):** Single key object (same structure as list items).

**Errors:**
- `404` — Key not found

---

### POST /api/keys

Add a new key or update an existing one.

**Request (ss:// URI):**
```json
{
  "name": "de-nuremberg-1",
  "key": "ss://Y2hhY2hhMjAtaWV0Zi1wb2x5MTMwNTpzZWNyZXQxMjM@185.123.45.67:8388#DE%20Nuremberg"
}
```

**Request (manual fields):**
```json
{
  "name": "de-nuremberg-1",
  "server": "185.123.45.67",
  "port": 8388,
  "password": "secret123",
  "method": "chacha20-ietf-poly1305"
}
```

**Optional field:**
- `original_name` — For renaming. If provided and different from `name`, references in all slot pools and active assignments are updated automatically.

**Response (201 for new, 200 for update):**
```json
{
  "ok": true,
  "data": {
    "name": "de-nuremberg-1",
    "server": "185.123.45.67",
    "port": 8388,
    "method": "chacha20-ietf-poly1305"
  }
}
```

**Errors:**
- `400` — Missing name, invalid ss:// URI, or missing manual fields

---

### DELETE /api/keys/:name

Delete a Shadowsocks key.

**Response (200):**
```json
{
  "ok": true,
  "data": null
}
```

**Errors:**
- `404` — Key not found
- `409` — Key is active on a slot or present in a slot's pool. Remove from all pools and deactivate first.

---

### POST /api/keys/health-check

Test connectivity and latency for all SS keys and AWG configs.

**Response (200):**
```json
{
  "ok": true,
  "data": {
    "ss": [
      {
        "name": "de-nuremberg-1",
        "server": "185.123.45.67",
        "reachable": true,
        "latency_ms": 42.3
      }
    ],
    "awg": [
      {
        "name": "de-nuremberg-awg",
        "server": "185.123.45.68",
        "reachable": true,
        "latency_ms": 38.7
      }
    ]
  }
}
```

SS keys are tested via TCP connect to `server:port`. AWG configs are tested via TCP connect to the endpoint IP on ports 22/443/80, with ICMP ping fallback.

---

## AWG Configs

AmneziaWG configuration management.

### GET /api/awg-configs

List all AWG configs.

**Response (200):**
```json
{
  "ok": true,
  "data": [
    {
      "name": "de-nuremberg-awg",
      "endpoint": "185.123.45.68"
    }
  ]
}
```

---

### GET /api/awg-configs/:name

Get a specific AWG config including the full config text.

**Response (200):**
```json
{
  "ok": true,
  "data": {
    "name": "de-nuremberg-awg",
    "config": "[Interface]\nPrivateKey = ...\nAddress = 10.0.0.2/32\n\n[Peer]\nPublicKey = ...\nEndpoint = 185.123.45.68:51820\nAllowedIPs = 0.0.0.0/0",
    "endpoint": "185.123.45.68"
  }
}
```

**Errors:**
- `404` — Config not found

---

### POST /api/awg-configs

Add a new AWG config or update an existing one.

**Request:**
```json
{
  "name": "de-nuremberg-awg",
  "config": "[Interface]\nPrivateKey = ...\nAddress = 10.0.0.2/32\n\n[Peer]\nPublicKey = ...\nEndpoint = 185.123.45.68:51820\nAllowedIPs = 0.0.0.0/0"
}
```

**Optional field:**
- `original_name` — For renaming. References in slot pools and active assignments are updated automatically.

**Validation:**
- Config must contain `[Interface]` and `[Peer]` sections
- Endpoint IP is auto-extracted from the config

**Response (201 for new, 200 for update):**
```json
{
  "ok": true,
  "data": {
    "name": "de-nuremberg-awg",
    "endpoint": "185.123.45.68"
  }
}
```

**Errors:**
- `400` — Missing name, missing config, or invalid config format

---

### DELETE /api/awg-configs/:name

Delete an AWG config.

**Response (200):**
```json
{
  "ok": true,
  "data": null
}
```

**Errors:**
- `404` — Config not found
- `409` — Config is active on a slot or in a slot's pool

---

## Tunnel Configs

Unified tunnel configuration management (AWG, Outline, Xray). This is the newer unified API that handles all tunnel types in a single interface, compared to the type-specific AWG Configs and Keys endpoints above.

### GET /api/tunnels

List all tunnel configs across all types.

**Response (200):**
```json
{
  "ok": true,
  "data": [
    {
      "name": "de-nuremberg-awg",
      "endpoint": "185.123.45.68",
      "type": "awg"
    },
    {
      "name": "nl-amsterdam-ss",
      "endpoint": "194.56.78.90",
      "type": "outline",
      "ssconf_url": "ssconf://...",
      "location": "NL",
      "tag": "Amsterdam",
      "prefix": "",
      "method": "chacha20-ietf-poly1305"
    },
    {
      "name": "fi-helsinki-vless",
      "endpoint": "95.216.100.1",
      "type": "xray",
      "server": "95.216.100.1",
      "port": 443,
      "vless_uuid": "abc-def-...",
      "public_key": "...",
      "short_id": "abcd1234",
      "server_name": "www.example.com",
      "flow": "xtls-rprx-vision",
      "fingerprint": "chrome",
      "tag": ""
    }
  ]
}
```

---

### GET /api/tunnels/:name

Get a single tunnel config with full details.

**Response (200):**
```json
{
  "ok": true,
  "data": {
    "name": "de-nuremberg-awg",
    "type": "awg",
    "config": "[Interface]\n...\n[Peer]\n...",
    "endpoint": "185.123.45.68",
    "uuid": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

**Errors:**
- `404` — Tunnel config not found

---

### POST /api/tunnels

Add a new tunnel config or update an existing one. Supports AWG, Outline, and Xray types.

**Request (AWG):**
```json
{
  "name": "de-nuremberg-awg",
  "type": "awg",
  "config": "[Interface]\nPrivateKey = ...\n\n[Peer]\nEndpoint = 185.123.45.68:51820\n..."
}
```

**Request (Outline):**
```json
{
  "name": "nl-amsterdam-ss",
  "type": "outline",
  "ssconf_url": "ssconf://...",
  "location": "NL"
}
```

**Request (Xray/VLESS):**
```json
{
  "name": "fi-helsinki-vless",
  "type": "xray",
  "server": "95.216.100.1",
  "port": 443,
  "vless_uuid": "abc-def-...",
  "public_key": "...",
  "short_id": "abcd1234",
  "server_name": "www.example.com",
  "flow": "xtls-rprx-vision",
  "fingerprint": "chrome"
}
```

**Optional field:**
- `original_name` — For renaming. If provided and different from `name`, references in all slot pools and active assignments are updated automatically.

**Response (201 for new, 200 for update):**
```json
{
  "ok": true,
  "data": {
    "name": "de-nuremberg-awg",
    "endpoint": "185.123.45.68",
    "type": "awg"
  }
}
```

**Errors:**
- `400` — Missing required fields, invalid config format, or invalid ssconf URL
- `409` — Name exists with a different type (cannot overwrite AWG config with Outline, etc.)

---

### DELETE /api/tunnels/:name

Delete a tunnel config. Fails if the config is currently active on a slot or in any slot's pool.

**Response (200):**
```json
{
  "ok": true,
  "data": null
}
```

**Errors:**
- `404` — Tunnel config not found
- `409` — Config is active on a slot or in a slot's pool

---

### POST /api/tunnels/health-check

Measure connectivity and latency to all tunnel config endpoints. All checks run in parallel.

**Response (200):**
```json
{
  "ok": true,
  "data": {
    "tunnels": [
      {
        "name": "de-nuremberg-awg",
        "server": "185.123.45.68",
        "reachable": true,
        "latency_ms": 38.7
      },
      {
        "name": "nl-amsterdam-ss",
        "server": "194.56.78.90",
        "reachable": false,
        "latency_ms": null
      }
    ]
  }
}
```

Latency is measured via TCP connect (ports 22, 443, 80) with ICMP ping fallback.

---

### GET /api/tunnel-configs/export

Export all tunnel configs as an Excel file (.xlsx).

The file contains two sheets:
- **AWG** — Columns: UUID, Name, Endpoint, Config
- **Outline** — Columns: UUID, Name, ssconf URL, Location, Server, Port, Method

**Response:** Binary file download (`application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`).

---

### POST /api/tunnel-configs/import

Import tunnel configs from an Excel file. Matches by UUID: existing UUIDs are updated, missing UUIDs are created as new entries.

**Request:** `multipart/form-data` with a `file` field containing the `.xlsx` file.

**Response (200):**
```json
{
  "ok": true,
  "added": 3,
  "updated": 1,
  "errors": ["Outline row 5 'bad-config': missing ssconf URL"]
}
```

**Errors:**
- `400` — No file provided or invalid Excel format

---

## Settings

### GET /api/settings

Get all settings including health check intervals, bandwidth, and top-level config fields.

**Response (200):**
```json
{
  "ok": true,
  "data": {
    "ip_check_interval_min": 30,
    "domain_check_interval_min": 60,
    "ip_retries": 2,
    "domain_retries": 2,
    "total_vpn_bandwidth": "100mbit",
    "per_user_auth": false,
    "server_ip": "192.168.2.91",
    "public_ip": "46.138.254.119",
    "default_vpn_slot": "slot-6",
    "deployment": "ERG",
    "dns_upstream": "127.0.0.1#5353",
  }
}
```

---

### PUT /api/settings

Update one or more settings. All fields are optional; only provided fields are updated.

**Request:**
```json
{
  "ip_check_interval_min": 15,
  "domain_check_interval_min": 30,
  "server_ip": "192.168.2.91",
  "dns_upstream": "127.0.0.1#5353",
  "total_vpn_bandwidth": "100mbit",
  "per_user_auth": true
}
```

**Valid settings:**

| Field | Type | Validation |
|-------|------|------------|
| `ip_check_interval_min` | number | Positive integer |
| `domain_check_interval_min` | number | Positive integer |
| `ip_retries` | number | Positive integer |
| `domain_retries` | number | Positive integer |
| `server_ip` | string | Valid IPv4 address |
| `public_ip` | string | Valid IPv4 address |
| `default_vpn_slot` | string | Must be an existing AWG slot ID |
| `deployment` | string | Max 5 characters (e.g., `"ERG"`, `"OFC"`) |
| `dns_upstream` | string | Non-empty (e.g., `"8.8.8.8"`, `"127.0.0.1#5353"`) |
| `total_vpn_bandwidth` | string | tc format (e.g., `"100mbit"`) or empty to remove |
| `per_user_auth` | boolean | Enable/disable per-user device auth |

**Side effects:**
- Changing `dns_upstream` or `per_user_auth` triggers dnsmasq and dns-router config regeneration
- Changing `total_vpn_bandwidth` triggers tc/HTB reconfiguration
- Enabling `per_user_auth` restores previously authenticated device IPs to nftset

**Response (200):** Updated settings object.

**Errors:**
- `400` — Unknown settings, invalid values, or validation failures

---

### GET /api/local-domains

Get the list of local domain overrides.

**Response (200):**
```json
{
  "ok": true,
  "data": ["nas.local.example.com", "printer.home"]
}
```

---

### PUT /api/local-domains

Update the local domain overrides list.

**Request:**
```json
{
  "domains": ["nas.local.example.com", "printer.home"]
}
```

**Validation:** Each domain must match standard domain format and be at most 253 characters.

**Response (200):** Updated domain list.

**Errors:**
- `400` — Invalid domain format

---

## Performances

### GET /api/performances/timeseries

Get key success/failure rates over time, aggregated into daily buckets.

**Query parameters:**

| Parameter | Description | Default | Valid values |
|-----------|-------------|---------|--------------|
| `range` | Number of days | 7 | 7, 30, 90, 180 |
| `slot_id` | Filter by slot | *(all)* | e.g., `slot-6` |

**Response (200):**
```json
{
  "ok": true,
  "data": {
    "slot_id": null,
    "keys": [
      {
        "name": "de-nuremberg-1",
        "points": [
          { "ts": 1745625600, "ok": 48, "fail": 0 },
          { "ts": 1745712000, "ok": 47, "fail": 1 }
        ]
      }
    ]
  }
}
```

Each `ts` is a Unix timestamp at the start of the day (UTC). `ok` and `fail` are counts of successful and failed checks for that day.

---

### GET /api/performances/alltime

Get all-time cumulative statistics per key.

**Query parameters:**

| Parameter | Description | Default |
|-----------|-------------|---------|
| `slot_id` | Filter by slot | *(all)* |

**Response (200):**
```json
{
  "ok": true,
  "data": [
    {
      "key_name": "de-nuremberg-1",
      "total": 1440,
      "ok": 1435,
      "fail": 5,
      "success_rate": 99.65
    }
  ]
}
```

---

### POST /api/performances/reset

Reset performance data.

**Request:**
```json
{
  "scope": "all"
}
```

**Scope values:**
- `"current"` — Reset in-memory key stats only (default)
- `"all"` — Wipe all data from SQLite database as well

**Response (200):**
```json
{
  "ok": true,
  "data": {
    "message": "All performance data reset"
  }
}
```

---

## Users

Admin-only endpoints for user management.

### GET /api/users

List all user accounts with device counts.

**Response (200):**
```json
{
  "ok": true,
  "data": [
    {
      "id": 1,
      "username": "admin",
      "role": "admin",
      "enabled": true,
      "created_at": "2026-04-20 10:00:00",
      "device_count": 2
    },
    {
      "id": 2,
      "username": "can",
      "role": "user",
      "enabled": true,
      "created_at": "2026-04-22 14:30:00",
      "device_count": 1
    }
  ]
}
```

---

### POST /api/users

Create a new user account.

**Request:**
```json
{
  "username": "newuser",
  "password": "password123",
  "role": "user"
}
```

**Validation:**
- Username: minimum 2 characters, must be unique
- Password: minimum 4 characters
- Role: `"admin"` or `"user"`

**Response (201):**
```json
{
  "ok": true,
  "data": {
    "id": 3,
    "username": "newuser",
    "role": "user",
    "enabled": true,
    "created_at": "2026-04-27 12:00:00"
  }
}
```

**Errors:**
- `400` — Validation failures
- `409` — Username already exists

---

### PUT /api/users/:id

Update a user account. All fields are optional.

**Request:**
```json
{
  "password": "newpassword",
  "role": "admin",
  "enabled": false
}
```

**Behavior:**
- Disabling a user immediately removes all their device authentications from the nftset

**Response (200):** Updated user object (without password_hash).

**Errors:**
- `400` — Invalid fields or no valid fields to update
- `404` — User not found

---

### DELETE /api/users/:id

Delete a user account.

**Response (200):**
```json
{
  "ok": true,
  "data": {
    "message": "User 'newuser' deleted"
  }
}
```

**Behavior:**
- Cannot delete your own account
- All device authentications are revoked on deletion

**Errors:**
- `400` — Cannot delete own account
- `404` — User not found

---

### GET /api/users/:id/devices

List all authenticated devices for a specific user.

**Response (200):**
```json
{
  "ok": true,
  "data": [
    {
      "id": 1,
      "user_id": 2,
      "ip": "192.168.2.100",
      "user_agent": "Mozilla/5.0 ...",
      "last_seen": "2026-04-27 11:45:00"
    }
  ]
}
```

**Errors:**
- `404` — User not found

---

## Devices

Device authentication management.

### GET /api/devices

List all authenticated devices across all users.

**Response (200):**
```json
{
  "ok": true,
  "data": [
    {
      "id": 1,
      "user_id": 2,
      "username": "can",
      "ip": "192.168.2.100",
      "user_agent": "Mozilla/5.0 ...",
      "last_seen": "2026-04-27 11:45:00"
    }
  ]
}
```

---

### DELETE /api/devices/:id

Revoke authentication for a specific device. Removes the IP from the nftset.

**Response (200):**
```json
{
  "ok": true,
  "data": {
    "message": "Device 192.168.2.100 removed"
  }
}
```

**Errors:**
- `404` — Device not found

---

## VPN Server

ProximaVPN WireGuard peer management (admin only).

### GET /api/vpn/server

Get VPN server configuration and all peers with live status.

**Response (200) (VPN enabled):**
```json
{
  "ok": true,
  "data": {
    "enabled": true,
    "interface": "wg1",
    "endpoint": "46.138.254.119:5555",
    "subnet": "10.14.14.0/24",
    "address": "10.14.14.1/24",
    "dns": "10.14.14.1",
    "listen_port": 5555,
    "public_key": "ABC123...",
    "available": true,
    "peers": [
      {
        "name": "Can's Phone",
        "public_key": "DEF456...",
        "address": "10.14.14.2/32",
        "lan_access": true,
        "created_at": 1745700000,
        "has_private_key": true,
        "last_handshake": 1745699500,
        "transfer_rx": 1048576,
        "transfer_tx": 524288,
        "endpoint": "95.73.12.34:51820"
      }
    ]
  }
}
```

**Response (200) (VPN disabled):**
```json
{
  "ok": true,
  "data": {
    "enabled": false,
    "peers": []
  }
}
```

---

### POST /api/vpn/peers

Create a new WireGuard peer with auto-generated keys and IP.

**Request:**
```json
{
  "name": "Office Laptop",
  "owner": 2
}
```

**Fields:**
- `name` (required) — Display name for the peer
- `owner` (optional) — VPN user ID to assign ownership. Links the peer to a VPN user for quota and self-service management.

**Response (201):**
```json
{
  "ok": true,
  "data": {
    "peer": {
      "name": "Office Laptop",
      "public_key": "GHI789...",
      "address": "10.14.14.3/32",
      "lan_access": true,
      "created_at": 1745700100,
      "has_private_key": true,
      "last_handshake": null,
      "transfer_rx": 0,
      "transfer_tx": 0,
      "endpoint": null
    },
    "client_config": "[Interface]\nPrivateKey = ...\nAddress = 10.14.14.3/32\nDNS = 10.14.14.1\n\n[Peer]\nPublicKey = ...\nEndpoint = 46.138.254.119:5555\nAllowedIPs = 0.0.0.0/0\nPersistentKeepalive = 25",
    "amnezia_config": "[Interface]\nPrivateKey = ...\n..."
  }
}
```

**Errors:**
- `400` — Missing name, VPN not enabled, or no available IPs
- `409` — Peer name already exists
- `500` — Failed to generate keypair

---

### PUT /api/vpn/peers/:name

Update a peer's properties.

**Request:**
```json
{
  "name": "New Name",
  "lan_access": false
}
```

**Response (200):** Updated peer object.

**Errors:**
- `400` — Empty name or VPN not enabled
- `404` — Peer not found
- `409` — New name conflicts with existing peer

---

### DELETE /api/vpn/peers/:name

Remove a WireGuard peer. Removes the peer from live WireGuard config and cleans up iptables rules.

**Response (200):**
```json
{
  "ok": true,
  "data": {
    "message": "Peer Office Laptop removed"
  }
}
```

**Errors:**
- `400` — VPN not enabled
- `404` — Peer not found

---

### GET /api/vpn/peers/:peer_id/config

Get the client configuration text for a peer. Only works if the private key is stored (not for legacy-imported peers). If sing-box is enabled on the VPN server, also returns the sing-box JSON config and profile URL.

**Response (200):**
```json
{
  "ok": true,
  "data": {
    "config": "[Interface]\nPrivateKey = ...\nAddress = 10.14.14.2/32\nDNS = 10.14.14.1\n\n[Peer]\nPublicKey = ...\nEndpoint = 46.138.254.119:5555\nAllowedIPs = 0.0.0.0/0\nPersistentKeepalive = 25",
    "singbox_config": { ... },
    "singbox_profile_url": "https://example.com/vpn/profile/peer-id?token=..."
  }
}
```

The `singbox_config` and `singbox_profile_url` fields are only present when sing-box (VLESS+Reality) is enabled on the VPN server.

**Errors:**
- `400` — VPN not enabled or no private key stored
- `404` — Peer not found

---

### GET /vpn/profile/:peer_id

Public (no JWT) sing-box remote profile endpoint. Authenticated via `?token=<vless_uuid>` query parameter. Returns a sing-box JSON config with the appropriate DNS and routing rules for the peer.

**Query parameters:**

| Parameter | Description |
|-----------|-------------|
| `token` | The peer's `vless_uuid` (required for authentication) |

**Response (200):** sing-box JSON configuration object.

**Errors:**
- `403` — Missing or invalid token

---

## VPN Users

VPN user management for multi-user VPN deployments. VPN users can own peers and have bandwidth/peer limits.

### GET /api/vpn/users

List all VPN users with peer counts and monthly bandwidth usage.

**Response (200):**
```json
{
  "ok": true,
  "data": [
    {
      "id": 1,
      "username": "alice",
      "enabled": true,
      "max_peers": 5,
      "bandwidth_quota": 107374182400,
      "speed_download": "100mbit",
      "speed_upload": "50mbit",
      "assigned_groups": ["messaging", "streaming"],
      "peer_count": 2,
      "monthly_usage": {
        "rx_bytes": 1073741824,
        "tx_bytes": 536870912
      },
      "created_at": "2026-05-01 10:00:00"
    }
  ]
}
```

---

### POST /api/vpn/users

Create a new VPN user.

**Request:**
```json
{
  "username": "alice",
  "password": "securepass",
  "max_peers": 5,
  "bandwidth_quota": 107374182400,
  "speed_download": "100mbit",
  "speed_upload": "50mbit",
  "assigned_groups": ["messaging", "streaming"]
}
```

**Fields:**
- `username` (required) — Must be unique
- `password` (required) — Stored hashed; also encrypted for admin viewing
- `max_peers` (optional) — Maximum number of peers this user can create. `null` for unlimited.
- `bandwidth_quota` (optional) — Monthly bandwidth quota in bytes. `null` for unlimited.
- `speed_download` (optional) — Per-user download speed limit (e.g., `"100mbit"`, `"50"` → `"50mbit"`)
- `speed_upload` (optional) — Per-user upload speed limit
- `assigned_groups` (optional) — Array of group IDs for routing

**Response (201):**
```json
{
  "ok": true,
  "data": {
    "id": 3,
    "username": "alice",
    "enabled": true,
    "max_peers": 5,
    "created_at": "2026-05-01 10:00:00"
  }
}
```

**Errors:**
- `400` — Missing username/password, invalid max_peers or bandwidth_quota
- `409` — Username already exists
- `500` — Failed to create user

---

### PUT /api/vpn/users/:user_id

Update a VPN user. All fields are optional.

**Request:**
```json
{
  "password": "newpass",
  "enabled": true,
  "max_peers": 10,
  "bandwidth_quota": null,
  "speed_download": "200mbit",
  "speed_upload": "100mbit",
  "assigned_groups": ["messaging"]
}
```

**Behavior:**
- Changing `speed_download` or `speed_upload` triggers immediate rebuild of per-peer tc/HTB speed limits

**Response (200):** Updated user object.

**Errors:**
- `400` — No valid fields to update
- `404` — VPN user not found

---

### DELETE /api/vpn/users/:user_id

Delete a VPN user.

**Query parameters:**

| Parameter | Description | Default |
|-----------|-------------|---------|
| `cascade` | `true` to also delete all peers owned by the user | `false` |

Without `cascade=true`, owned peers are unassigned (owner set to null) instead of deleted.

**Response (200):**
```json
{
  "ok": true,
  "data": {
    "message": "VPN user alice deleted",
    "peers_deleted": 2
  }
}
```

**Errors:**
- `404` — VPN user not found

---

### GET /api/vpn/users/:user_id/traffic

Get per-user traffic history (aggregated from all owned peer traffic).

**Query parameters:**

| Parameter | Description | Default |
|-----------|-------------|---------|
| `range` | Number of days (1-30) | 30 |

**Response (200):**
```json
{
  "ok": true,
  "data": {
    "points": [
      { "date": "2026-06-01", "rx_bytes": 1073741824, "tx_bytes": 536870912 }
    ],
    "range_days": 30,
    "monthly_usage": { "rx_bytes": 5368709120, "tx_bytes": 2147483648 },
    "peer_count": 2
  }
}
```

**Errors:**
- `404` — VPN user not found

---

### POST /api/vpn/auth/login

Authenticate a VPN app user (not an admin account). Rate-limited per IP.

**Request:**
```json
{
  "username": "alice",
  "password": "securepass"
}
```

**Response (200):**
```json
{
  "ok": true,
  "data": {
    "token": "eyJhbGciOiJIUzI1NiIs...",
    "user": {
      "id": 1,
      "username": "alice"
    }
  }
}
```

**Errors:**
- `400` — Missing username or password
- `401` — Invalid credentials
- `403` — Account disabled
- `429` — Rate limited (too many failed attempts). Includes `retry_after` field.
- `500` — Auth not configured

---

### VPN Self-Service Endpoints

These endpoints use a VPN user JWT token (from `/api/vpn/auth/login`) rather than the admin JWT.

**GET /api/vpn/self/me** — Get own VPN user info with owned peers and server details.

**GET /api/vpn/self/peers** — List own peers with live connection status.

**POST /api/vpn/self/peers** — Create a new peer (respects max_peers limit).

**PUT /api/vpn/self/peers/:peer_id** — Rename own peer.

**DELETE /api/vpn/self/peers/:peer_id** — Delete own peer.

**GET /api/vpn/self/peers/:peer_id/config** — Get client config for own peer (WireGuard + sing-box if enabled).

**GET /api/vpn/self/peers/:peer_id/traffic** — Get traffic history for own peer.

**POST /api/vpn/self/password** — Change own password (requires `current_password` and `new_password`).

---

## Mode

Routing mode management.

### GET /api/mode

Get current routing mode and readiness status for all modes.

**Response (200):**
```json
{
  "ok": true,
  "data": {
    "current": "dns",
    "setup_complete": true,
    "modes": {
      "dns": { "ready": true, "issues": [] }
    }
  }
}
```

---

### PUT /api/mode

Switch the routing mode.

**Request:**
```json
{
  "mode": "dns"
}
```

**Valid modes:** `"dns"`

**Response (200):** Mode status after switch.

**Errors:**
- `400` — Missing or invalid mode
- `409` — Switch failed (preflight issues)

---

### GET /api/mode/preflight/:mode

Run preflight checks for a target mode without actually switching.

**Response (200):**
```json
{
  "ok": true,
  "data": {
    "ready": true,
    "issues": [],
    "warnings": []
  }
}
```

---

### POST /api/mode/complete-setup

Mark the initial setup wizard as complete.

**Request:**
```json
{
  "deployment": "ERG"
}
```

**Response (200):**
```json
{
  "ok": true,
  "data": {
    "setup_complete": true
  }
}
```

---

## Proxy Gateway

HTTP proxy gateway for Docker containers.

### GET /api/proxy-gateway

Get proxy gateway configuration and status.

**Response (200):**
```json
{
  "ok": true,
  "data": {
    "enabled": true,
    "port": 8080,
    "slot": "slot-6",
    "running": true
  }
}
```

The `port` field indicates the HTTP proxy port that other containers (or LAN clients) can connect to.

---

### PUT /api/proxy-gateway

Update proxy gateway settings.

**Request:**
```json
{
  "enabled": true,
  "slot": "slot-6"
}
```

Both fields are optional. Setting `enabled` triggers a gateway restart.

**Response (200):** Updated gateway status.

**Errors:**
- `400` — Invalid slot format, unknown slot, or DIRECT slot

---

## IPList

Domain list synchronization from iplist.opencck.org.

### GET /api/iplist/status

Get cache statistics: last sync time and per-group domain counts.

**Response (200):**
```json
{
  "ok": true,
  "last_sync": 1745690000,
  "groups": {
    "telegram": { "count": 120, "fetched_at": 1745690000 },
    "youtube": { "count": 340, "fetched_at": 1745690000 },
    "meta": { "count": 85, "fetched_at": 1745690000 }
  }
}
```

---

### GET /api/iplist/groups

List all available iplist groups with current cached domain counts.

**Response (200):**
```json
{
  "ok": true,
  "groups": [
    { "name": "telegram", "count": 120, "fetched_at": 1745690000 },
    { "name": "youtube", "count": 340, "fetched_at": 1745690000 },
    { "name": "meta", "count": 85, "fetched_at": 1745690000 },
    { "name": "twitter", "count": 65, "fetched_at": null },
    { "name": "openai", "count": 0, "fetched_at": null }
  ]
}
```

Groups with `fetched_at: null` have not been synced yet.

---

### POST /api/iplist/sync

Manually trigger a sync of all active iplist groups. Fetches fresh domain lists and regenerates dnsmasq + dns-router configs.

**Response (200):**
```json
{
  "ok": true,
  "synced_groups": 5,
  "total_domains": 630,
  "stats": {
    "telegram": 120,
    "youtube": 340,
    "meta": 85,
    "twitter": 65,
    "openai": 20
  }
}
```

---

### POST /api/iplist/sync/:group_name

Sync a single iplist group.

**Response (200):**
```json
{
  "ok": true,
  "group": "telegram",
  "count": 122
}
```

**Errors:**
- `400` — Unknown iplist group name

---

## Network Trace

Domain discovery tool for finding all domains used by a website.

### POST /api/trace

Start an asynchronous URL trace. Returns an operation ID for progress polling.

**Request (single URL):**
```json
{
  "url": "https://youtube.com",
  "slot_id": "slot-6"
}
```

**Request (multiple URLs):**
```json
{
  "urls": ["https://youtube.com", "https://telegram.org"],
  "slot_id": "slot-6"
}
```

**Fields:**
- `url` or `urls` (required) — One or more URLs to trace (maximum 20)
- `slot_id` (optional) — Trace through a specific slot's proxy. Must be an enabled, non-DIRECT slot.

**Response (200):**
```json
{
  "ok": true,
  "data": {
    "op_id": "trc-abc123"
  }
}
```

Poll `GET /api/operations` for progress, then fetch results when complete.

**Errors:**
- `400` — No URLs provided, too many URLs, or invalid slot

---

### GET /api/trace/:op_id/results

Get trace results for a completed operation.

**Response (200):**
```json
{
  "ok": true,
  "data": {
    "domains": [
      {
        "domain": "youtube.com",
        "ips": ["142.250.185.46"],
        "requests": 12
      },
      {
        "domain": "i.ytimg.com",
        "ips": ["142.250.185.47"],
        "requests": 8
      },
      {
        "domain": "yt3.ggpht.com",
        "ips": ["142.250.185.48"],
        "requests": 3
      }
    ],
    "ip_ranges": ["142.250.0.0/15"],
    "total_requests": 45,
    "duration_ms": 3200
  }
}
```

**Errors:**
- `404` — Results not found or trace still running. Results are stored for 30 minutes.

---

## Operations

Track long-running background operations.

### GET /api/operations

Get all currently active (in-progress) operations.

**Response (200):**
```json
{
  "ok": true,
  "data": [
    {
      "id": "ipc-abc123",
      "type": "ip-check",
      "label": "IP check: AWG Primary",
      "started_at": 1745700000,
      "completed": false,
      "steps": [
        { "message": "Checking IP for slot-6...", "ok": null, "ts": 1745700000 },
        { "message": "IP: 89.105.208.130", "ok": true, "ts": 1745700005 }
      ]
    }
  ]
}
```

**Operation types:**
- `activate` — Key/config activation
- `restart` — Slot container restart
- `ip-check` — Single slot IP check
- `domain-check` — Single slot domain check
- `bulk-ip-check` — All-slots IP check
- `bulk-domain-check` — All-slots domain check
- `bulk-restart` — All-slots restart
- `toggle` — Slot enable/disable
- `trace` — URL domain trace

Operations are automatically pruned after completion (retained briefly for the UI to display final status).

---

## Scheduler

**Admin-only.** Requires admin role.

### GET /api/scheduler/jobs

Get the state of all scheduled background jobs.

**Response (200):**
```json
{
  "ok": true,
  "data": {
    "scheduler_running": true,
    "mode": "dns",
    "jobs": [
      {
        "id": "ip_check",
        "scope": "per_slot",
        "interval_seconds": 1800,
        "interval_label": "30 min",
        "dns_only": false,
        "trigger": "/slots/check-all-ip",
        "slots": [
          {
            "slot_id": "slot-6",
            "slot_label": "AWG Estonia",
            "last_run": 1714300000.0,
            "next_run": 1714301800.0,
            "fail_count": 0,
            "consecutive_failovers": 0,
            "bypass_active": false
          }
        ]
      },
      {
        "id": "tunnel_health",
        "scope": "global",
        "interval_seconds": 1800,
        "interval_label": "30 min",
        "dns_only": true,
        "trigger": "/tunnel-health/check",
        "last_run": 1714300000.0,
        "next_run": 1714301800.0,
        "last_ok": true
      }
    ]
  }
}
```

**Job scopes:**
- `per_slot` — Job runs independently for each active slot. Contains a `slots` array.
- `global` — Single job for the entire system. Contains `last_run`, `next_run`, `last_ok`.

**Job IDs:** `ip_check`, `domain_check`, `tunnel_health`, `bandwidth_sampling`, `iplist_sync`

---

## Tunnel Health

### GET /api/tunnel-health

Get the cached result of the last tunnel health check (DNS Mode only).

**Response (200):**
```json
{
  "ok": true,
  "data": {
    "ok": true,
    "ts": 1714300000.0,
    "dns_router_running": true,
    "nftables": { "ok": true },
    "tunnels": []
  }
}
```

Returns `null` for `data` if no check has run yet.

### POST /api/tunnel-health/check

Run a tunnel health check immediately and return the result.

**Response (200):** Same structure as GET, with fresh results.

---

### POST /api/tunnel-health/restart-dns-router

Restart the dns-router container so tun2socks picks up the latest tunnels.json routing configuration.

**Response (200):**
```json
{
  "ok": true,
  "data": {
    "message": "dns-router restarted"
  }
}
```

**Errors:**
- `500` — Restart failed
- `503` — Docker unavailable

---

## Bandwidth

### GET /api/bandwidth/timeseries

Get daily aggregated RX/TX per tunnel.

**Query parameters:**

| Parameter | Description | Default |
|-----------|-------------|---------|
| `range` | Number of days: 7, 30, 90, or 180 | 7 |
| `slot_id` | Filter by slot ID | *(all)* |

### GET /api/bandwidth/summary

Get total bytes per tunnel/key.

**Query parameters:**

| Parameter | Description | Default |
|-----------|-------------|---------|
| `slot_id` | Filter by slot ID | *(all)* |

### POST /api/bandwidth/sample

Manually trigger one bandwidth sample collection. Reads `/sys/class/net/tunN/statistics` from the dns-router container and records deltas to SQLite.

**Response (200):**
```json
{ "ok": true }
```

---

## Logs

### GET /api/logs

Get log entries with optional filtering.

**Query parameters:**

| Parameter | Description | Default | Max |
|-----------|-------------|---------|-----|
| `slot` | Filter by slot tag (e.g., `slot-1` matches `[SLOT-1]` in logs) | *(all)* | - |
| `level` | Filter by log level: `INFO`, `WARNING`, `ERROR` | *(all)* | - |
| `lines` | Number of lines to return | 300 | 2000 |

**Response (200):**
```json
{
  "ok": true,
  "data": [
    "2026-04-27 01:39:00 INFO [SLOT-6] IP check OK: 89.105.208.130",
    "2026-04-27 01:38:55 INFO [SLOT-6] Running scheduled IP check",
    "2026-04-27 01:00:00 INFO [SLOT-6] Domain check: 12/12 OK"
  ]
}
```

Logs are returned newest-first as an array of strings. Each string is a complete log line.

**Errors:**
- `500` — Could not read log file
