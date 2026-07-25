# Health & Failover

Proxima continuously monitors VPN tunnel health and automatically fails over to backup configurations when issues are detected. This document covers every aspect of the health monitoring system, failover algorithm, bypass mode, and performance tracking.

---

## Overview

The health system runs as a background scheduler thread inside the Proxima Flask container. It performs two independent checks on configurable intervals:

- **IP Check** -- Verifies the tunnel exit IP by making requests through the proxy
- **Domain Check** -- Verifies that critical domains are reachable through the proxy

Health checks run **in parallel** across slots using a `ThreadPoolExecutor` (max 4 workers). This means a slow or unresponsive slot does not block checks on other slots -- all active slots are checked concurrently.

These checks feed into a retry and failover pipeline that automatically rotates VPN credentials when a tunnel is confirmed down, while avoiding false positives from transient IP service outages.

```
                    Scheduler Thread
                    ----------------
                    |               |
              IP Check Timer   Domain Check Timer
              (default 30m)    (default 60m)
                    |               |
                    v               v
              ThreadPoolExecutor (max 4 workers)
              Check all active slots in parallel
                    |               |
                    v               v
              Update health    Update health
              state            state
                    |               |
                    +----> Failover Decision <----+
                                |
                          Rotate pool
                          Restart container
                          Post-activation check
```

---

## IP Check

The IP check verifies that traffic routed through a slot's tunnel exits at the expected IP address. This confirms the tunnel is operational and traffic is not leaking.

### How It Works

1. Select the proxy endpoint for the target slot
2. Make an HTTP GET request through the slot's SOCKS proxy to an IP check service
3. Compare the returned IP against the expected exit IP (if configured)
4. Record success or failure in health state

### IP Check Services (Fallback Chain)

Proxima uses multiple IP check services with automatic fallback:

| Priority | Service | URL |
|----------|---------|-----|
| 1 | ipify | `https://api.ipify.org` |
| 2 | ifconfig.me | `https://ifconfig.me/ip` |
| 3 | icanhazip | `https://icanhazip.com` |
| 4 | my-ip.io | `https://api.my-ip.io/v2/ip.txt` |

If the first service times out or returns an error, the next one is tried. All four must fail before the IP check is considered failed.

### Proxy Routing

Each request is routed through the slot's proxy to verify the tunnel itself:

- **Shadowsocks slots**: Use `socks5h://` -- DNS resolution happens inside the tunnel
- **AmneziaWG slots**: Use `socks5://` -- DNS resolution happens locally

The distinction for AWG is critical: VPN providers may hijack DNS queries made inside the tunnel, returning incorrect IP addresses. Using `socks5://` (local DNS) for AWG health checks avoids this problem while still routing the HTTP request through the tunnel.

### Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `ip_check_interval` | 30 minutes | Time between scheduled IP checks |
| `ip_check_timeout` | 15 seconds | HTTP request timeout per attempt |
| `ip_check_retries` | 3 | Number of failed checks before escalation |

### IP Check Flow

```
For each active slot:
  1. GET https://api.ipify.org via socks5[h]://slot-proxy:1080
     Timeout: 15s
  2. If success:
       - Record exit IP in health state
       - Reset retry counter
       - Log: [SLOT-N] IP check OK: 1.2.3.4
  3. If fail:
       - Try next IP service in fallback chain
       - If all services fail:
           - Increment retry counter
           - Log: [SLOT-N] IP check failed (attempt M/N)
```

---

## Domain Check

The domain check verifies that critical domains defined in groups are reachable through the proxy. This catches cases where the tunnel is up (IP check passes) but specific services are blocked or unreachable.

### How It Works

1. For each group, iterate over `critical_domains` (sourced from both iplist and custom_domains)
2. Resolve the domain via DNS-over-HTTPS (DoH) through the proxy
3. Make an HTTP request to the domain through the proxy
4. Record the result (HTTP status, resolved destination IP, **egress IP**, response time)

The **egress IP** is the tunnel's exit IP (from the last successful IP check) captured at the time of the domain check. This allows the UI to show whether the domain check traffic actually exited through the expected tunnel.

### Success Criteria

The domain check uses a pragmatic success definition:

- **Any HTTP response = SUCCESS** -- Even 4xx (Forbidden) or 5xx (Server Error) responses mean the proxy is working. The server responded, which proves traffic is flowing through the tunnel.
- **Connection error on resolvable domain = FAIL** -- If DNS resolves but the HTTP connection fails (timeout, connection refused, reset), this indicates a proxy or tunnel issue.
- **Naked CDN domains are skipped** -- Domains like `ytimg.com` and `ggpht.com` have no DNS A record at the naked domain level (only subdomains like `i.ytimg.com` resolve). These are automatically skipped during failover evaluation to prevent false positives.

### Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `domain_check_interval` | 60 minutes | Time between scheduled domain checks |
| `domain_check_retries` | 2 | Failed checks before domain is considered down |

### Domain Check Flow

```
For each group with critical_domains:
  For each domain:
    1. DNS resolve via DoH through proxy
    2. If no A record → skip (naked CDN domain)
    3. HTTP GET https://domain/ via proxy
       Timeout: 15s
    4. Any HTTP response → SUCCESS
       Connection error → FAIL
    5. Log: [SLOT-N] Domain check: example.com → 200 OK via 1.2.3.4
           [SLOT-N] Domain check: example.com → FAIL (ConnectionError)
```

---

## Retry Logic

The retry system prevents false positives from flaky IP check services while still catching real tunnel failures. The key insight is: if the IP check service is down but domains work fine, the tunnel is healthy.

### Retry Pipeline

```
IP Check Failed
      |
      v
Increment retry counter
      |
      v
retry_count >= ip_check_retries (default 3)?
      |                    |
      No                   Yes
      |                    |
      v                    v
Wait for next         Run Domain Check
scheduled check       immediately
                           |
                     +-----+-----+
                     |           |
               Domains OK    Domains FAIL
                     |           |
                     v           v
              IP service      FAILOVER
              is down.        Tunnel is
              Tunnel is OK.   confirmed down.
              Reset retries.
```

This two-stage verification is essential because IP check services (ipify, ifconfig.me, etc.) occasionally go down or become unreachable from certain regions. Without the domain check confirmation, Proxima would unnecessarily failover healthy tunnels.

### Retry Counter Behavior

- **Incremented**: On each failed IP check (all fallback services failed)
- **Reset to 0**: On successful IP check OR when domain check confirms tunnel is healthy
- **Triggers escalation**: When counter reaches `ip_check_retries` threshold

---

## Failover Algorithm

When both IP check retries are exhausted AND domain check confirms failure, Proxima executes the failover sequence.

### Step-by-Step Failover

```
1. LOCK SLOT
   - Acquire per-slot lock (prevents concurrent failovers)
   - If lock already held → skip (another failover in progress)

2. ROTATE POOL
   - current_index = index of active key/config in pool
   - next_index = (current_index + 1) % len(pool)
   - Select next key/config from pool

3. WRITE CONFIG
   - SS slots: Write new slot-N.json with server/port/password/method
   - AWG slots: Write new awg-slot-N.conf with endpoint/keys/addresses
   - AWG config sanitization: Remove DNS, Table, PostUp, PostDown directives
     Inject Table = off to prevent routing conflicts

4. RESTART CONTAINER
   - Docker SDK: container.restart(timeout=10)
   - Waits for container to stop and start

5. WAIT 10 SECONDS
   - Tunnel needs time to establish (TCP handshake, key exchange)
   - Non-negotiable delay — skipping this causes false failures

6. POST-ACTIVATION IP CHECK
   - Run IP check against the slot
   - Update health state with new exit IP
   - If check fails → slot is marked unhealthy (will retry on next cycle)

7. UPDATE STATE
   - Increment failover_count in health state
   - Update active key index in config
   - Save config to disk (atomic write)

8. LOG
   - [SLOT-N] Failover: OldKeyName → NewKeyName
   - [SLOT-N] New exit IP: 5.6.7.8

9. RELEASE LOCK
```

### Edge Cases

- **Single-entry pool**: If the pool has only one key/config, rotation produces the same entry. Proxima logs a warning: `[SLOT-N] Pool has only 1 entry, cannot failover`. The container is still restarted (sometimes a restart alone fixes transient issues).
- **All pool entries exhausted**: If every entry in the pool has been tried and all fail, bypass mode is activated (see below).
- **Concurrent failover attempts**: The per-slot lock ensures only one failover runs at a time. Additional attempts are silently skipped.

### Failover Timing

```
IP check fails (attempt 1/3)          t=0
IP check fails (attempt 2/3)          t=30m
IP check fails (attempt 3/3)          t=60m
  → Domain check triggered
  → Domains also fail
  → FAILOVER starts                   t=60m
    Lock acquired                     t=60m + 0s
    Config written                    t=60m + 0.1s
    Container restarted               t=60m + 2s
    Wait 10s                          t=60m + 12s
    Post-activation IP check          t=60m + 13s
    Failover complete                 t=60m + 15s
```

---

## Chained Slot Health Checks

When a slot has a `via_slot` parent (tunnel chaining), health checks verify the full chain:

- **IP check** runs through the chained path (child via parent), so the exit IP reflects the final hop
- **If the parent slot fails**, the child slot's health check will also fail since its traffic depends on the parent
- **Failover** operates independently per slot — if the child slot fails, it rotates its own pool; if the parent fails, the parent rotates its own pool
- **Restart** of a chained slot triggers dns-router reload to update routing tables

The Dashboard shows the `via` relationship on each slot card, making chain dependencies visible.

---

## Post-Activation Check

After **any** activation -- whether from automatic failover or manual key/config change in the UI -- Proxima always performs a post-activation verification.

### Post-Activation Sequence

```
1. Activation event (failover or manual change)
2. Config written + container restarted
3. Wait 10 seconds (background thread, non-blocking)
4. IP check through the slot
5. Update health state:
   - last_ip_check = now
   - last_ip_ok = true/false
   - last_ip = exit IP (if successful)
6. UI updates in real-time via polling
```

This check is critical because:

- A new key might be expired or revoked
- A new AWG config might have the wrong endpoint
- The VPN server might be overloaded and rejecting connections
- Network conditions might prevent tunnel establishment

The check runs in a background thread so it does not block the API response. The UI reflects the result on the next status poll.

---

## Bypass Mode

Bypass mode is a safety mechanism that keeps internet working when the VPN is completely down. It activates when all pool configurations for a slot have been tried and all fail.

### Activation

```
Pool rotation exhausted (all entries tried)
AND all IP checks fail
AND all domain checks fail
      |
      v
BYPASS MODE ACTIVATED
      |
      +-- Remove dnsmasq nftset entries for affected groups
      +-- Flush nftsets → no IPs to match
      +-- Traffic goes direct (no VPN)
      +-- Log: [SLOT-N] BYPASS MODE: All configs failed, traffic going direct
```

### What Happens in Bypass Mode

When bypass mode is active for a slot:

1. **dnsmasq nftset entries are removed** -- DNS still resolves, but resolved IPs are not added to nftables sets
2. **nftsets are flushed** -- Any previously added IPs are cleared
3. **Traffic goes direct** -- Without nftset matches, nftables does not mark packets, and they route normally (direct internet)
4. **Internet keeps working** -- Users can still access all services, just without VPN protection

### Recovery

Bypass mode is not permanent. Proxima actively tries to recover:

- **Recovery check interval**: Every 2 minutes
- **Recovery check**: Try each pool config in order with IP check
- **On success**:
  1. Activate the working config
  2. Regenerate dnsmasq config with nftset entries
  3. Reload dnsmasq and nftsets
  4. Resume VPN routing
  5. Log: `[SLOT-N] BYPASS MODE ENDED: Recovered with KeyName`
  6. Clear bypass mode flag

### UI Indication

The dashboard displays a prominent warning banner when any slot is in bypass mode:

- Lists affected slots and groups
- Shows time since bypass mode activated
- Updates in real-time when recovery succeeds

---

## Health State

The health state is an in-memory data structure that serves as the single source of truth for slot health across the entire application.

### Structure

```json
{
  "slot-1": {
    "last_ip_check": "2026-04-27T10:30:00Z",
    "last_ip_ok": true,
    "last_ip": "185.32.100.45",
    "last_domain_check": "2026-04-27T10:00:00Z",
    "last_domain_ok": true,
    "failover_count": 2,
    "retry_count": 0,
    "bypass_mode": false,
    "key_stats": {
      "server-de-1": { "success": 48, "fail": 2 },
      "server-nl-3": { "success": 12, "fail": 0 }
    }
  },
  "slot-6": {
    "last_ip_check": "2026-04-27T10:30:00Z",
    "last_ip_ok": true,
    "last_ip": "89.105.208.130",
    "last_domain_check": "2026-04-27T10:00:00Z",
    "last_domain_ok": true,
    "failover_count": 0,
    "retry_count": 0,
    "bypass_mode": false,
    "key_stats": {
      "awg-config-1": { "success": 100, "fail": 0 }
    }
  }
}
```

### Key Properties

| Field | Type | Description |
|-------|------|-------------|
| `last_ip_check` | ISO timestamp | When the last IP check ran |
| `last_ip_ok` | boolean | Whether the last IP check succeeded |
| `last_ip` | string | The exit IP returned by the last successful check |
| `last_domain_check` | ISO timestamp | When the last domain check ran |
| `last_domain_ok` | boolean | Whether the last domain check succeeded |
| `failover_count` | integer | Total number of failovers since last reset |
| `retry_count` | integer | Current IP check retry counter (resets on success) |
| `bypass_mode` | boolean | Whether the slot is in bypass mode |
| `key_stats` | object | Per-key success/fail counters |

### Lifecycle

- **Built on startup**: Empty state, populated by first scheduled check
- **Updated in real-time**: Every IP check, domain check, failover, and manual action updates the state
- **Not persisted to disk**: Health state is in-memory only. On container restart, it starts fresh and is rebuilt by the first check cycle
- **Thread-safe**: All updates go through the health module with proper locking

### Why In-Memory?

Persisting health state to disk would add complexity without real benefit:

- Health state becomes stale quickly (IP addresses change, tunnels drop)
- The first scheduled check (within minutes of startup) fully populates the state
- Disk persistence would need atomic writes and corruption handling for data that is inherently ephemeral

---

## Manual Checks

Users can trigger health checks on demand from the UI without waiting for the scheduled interval.

### Available Manual Actions

| Action | Scope | Description |
|--------|-------|-------------|
| **Check IP** | Single slot | Triggers an immediate IP check for one slot |
| **Check Domains** | Single group | Triggers an immediate domain check for one group's critical domains |
| **Check All IP** | All active slots | Runs IP check on every active slot in parallel |
| **Check All Domains** | All groups | Runs domain check for every group with critical domains |

### Behavior

- Manual checks update health state identically to scheduled checks
- Results appear in the UI within seconds (the dashboard polls status)
- Manual checks can trigger failover if the check reveals a failure
- Manual checks reset the scheduled timer (prevents double-checking)
- Operations progress is tracked in the Operations Bar at the top of the UI

---

## Performance Tracking

Proxima records health check results in a SQLite database (`/config/proxima.db`) for long-term analysis and visualization.

### Recorded Events

**Key Events Table:**

| Column | Description |
|--------|-------------|
| `timestamp` | When the event occurred |
| `slot` | Which slot (e.g., `slot-1`, `slot-6`) |
| `key_name` | Which key/config was active |
| `event_type` | `activation`, `ip_check_ok`, `ip_check_fail` |
| `exit_ip` | The exit IP address (for successful checks) |

**Domain Results Table:**

| Column | Description |
|--------|-------------|
| `timestamp` | When the check occurred |
| `slot` | Which slot handled the request |
| `domain` | The domain that was checked |
| `http_status` | HTTP response status code (or error string) |
| `exit_ip` | The resolved destination IP (domain's A record) |
| `egress_ip` | The tunnel exit IP at the time of the check (from slot's last IP check) |
| `response_time_ms` | Response time in milliseconds |

> **Note:** `exit_ip` is the IP address the domain resolved to (destination), while `egress_ip` is the IP address traffic exited through (source tunnel). The UI displays `egress_ip` below the health dots, color-coded green when it matches the slot's active IP, red when it doesn't.

### Performances Page

The Performances page in the UI visualizes this data as interactive charts:

- **Success rate over time** -- Line chart showing percentage of successful checks per key
- **Time range selector** -- 1 week, 1 month, 3 months, 6 months
- **Per-key breakdown** -- Compare reliability of different keys/configs
- **Domain check history** -- See which domains had issues and when

### Data Management

- Performance data accumulates over time in the SQLite database
- Data can be reset from the Settings page (clears all historical records)
- Database is located at `/config/proxima.db` inside the container volume
- Survives container restarts (persisted on the mounted volume)

---

## Summary: Check and Failover Decision Tree

```
Scheduled IP Check
      |
      v
IP Check → SUCCESS? ──Yes──→ Update health state, reset retries. Done.
      |
      No
      |
      v
Try next IP service (up to 4)
      |
      v
All services failed?
      |         |
      No        Yes
      |         |
      v         v
   (retry     Increment retry counter
    that       |
    service)   v
             retry_count >= threshold?
                  |          |
                  No         Yes
                  |          |
                  v          v
             Wait for    Domain Check
             next cycle       |
                        +-----+-----+
                        |           |
                  Domains OK    Domains FAIL
                        |           |
                        v           v
                  Reset retries  FAILOVER
                  Tunnel is OK   (rotate pool, restart, verify)
                                      |
                                      v
                                All pool entries tried?
                                      |          |
                                      No         Yes
                                      |          |
                                      v          v
                                   Normal     BYPASS MODE
                                   operation  (direct traffic)
```

> **See also:** [Architecture](/docs/architecture.md) for system design details, [Introduction](/docs/introduction.md) for a feature overview
