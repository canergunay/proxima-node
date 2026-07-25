# UI Guide

Proxima's web interface is a single-page React application built with MUI v6 and a dark theme. It is served by the Flask backend and accessible at `http://SERVER_IP:5000` (or the configured port).

This guide covers every page and feature of the interface.

---

## Table of Contents

- [Login](#login)
- [Setup Wizard](#setup-wizard)
- [Dashboard](#dashboard)
- [Groups](#groups)
- [Keys](#keys)
- [Logs](#logs)
- [Performances](#performances)
- [Speed Test](#speed-test)
- [Users](#users)
- [ProximaVPN](#proximavpn)
- [Scheduler](#scheduler)
- [Settings](#settings)
- [Navigation & Layout](#navigation--layout)

---

## Login

The login page is the first screen shown to unauthenticated users.

**Fields:**
- **Username** — the account username
- **Password** — the account password

**Behavior:**
- On successful login, a JWT token is returned and stored in the browser's local storage.
- All subsequent API requests include this token in the `Authorization: Bearer <token>` header.
- If no admin account has been created yet (first run), the login page automatically redirects to the [Setup Wizard](#setup-wizard).
- On logout, the JWT token is cleared and (in DNS Mode with per-user auth) the device IP is removed from the authenticated nftset.

---

## Setup Wizard

Shown on first launch when no admin account exists.

**Steps:**

1. **Create Admin Account** — Enter a username (minimum 2 characters) and password (minimum 4 characters). This creates the initial admin user who has full access to all features.

2. **Server Configuration** — Set the server's LAN IP address and deployment code (e.g., HOME, OFC).

3. **Complete Setup** — Finalizes the initial configuration. The system generates required config files and marks setup as complete.

After setup, the user is logged in automatically and redirected to the [Dashboard](#dashboard).

---

## Dashboard

The Dashboard is the primary monitoring page. It shows the health status of all configured tunnel slots at a glance.

### Slot Health Cards

Each slot is displayed as a card containing:

| Element | Description |
|---------|-------------|
| **Slot label** | User-defined name (e.g., "AWG Primary", "SS Backup") |
| **Active key/config** | The currently active tunnel config name (AWG, Outline/SS, or Xray/VLESS) |
| **Via** | If tunnel chaining is configured, shows which parent slot this slot routes through |
| **Last IP** | The exit IP address from the most recent IP check |
| **Health status** | Color-coded indicator showing tunnel health |
| **Failover count** | Number of automatic failovers that have occurred |
| **Domain check results** | Ratio of successful vs. total domain checks (e.g., "12/12") |

### Health Status Colors

| Color | Status | Meaning |
|-------|--------|---------|
| Green | Healthy | Last IP check and domain check both passed |
| Red | Failed | Last IP check or domain check failed |
| Grey | Unknown | No checks have been run yet, or slot is disabled |

### Per-Slot Actions

Each slot card provides action buttons:

- **Check IP** — Trigger a manual IP check for this slot. Verifies the tunnel is connected by checking the exit IP.
- **Check Domains** — Trigger a manual domain check for this slot. Tests all critical domains assigned to this slot's groups.
- **Restart** — Restart the tunnel client container. After restart, the system waits 10 seconds and then automatically runs an IP check.
- **Activate** — Switch to a different key/config from the slot's pool. Opens a dropdown with available keys/configs.
- **Enable/Disable** — Toggle the slot on or off. Disabling a slot stops its tunnel container.

### Pool Management

Clicking the pool indicator on a slot card opens the pool editor where you can:

- View all keys/configs currently in the failover pool
- Add keys/configs to the pool
- Remove keys/configs from the pool
- Reorder pool entries (failover rotates through this order)

### Bulk Actions

The toolbar at the top of the Dashboard provides bulk operations:

- **Check All IP** — Run IP checks on all enabled, non-DIRECT slots simultaneously
- **Check All Domains** — Run domain checks on all enabled, non-DIRECT slots
- **Restart All** — Restart all enabled tunnel containers, then check IPs
- **Enable All** — Enable all slots
- **Disable All** — Disable all slots

### Via (Tunnel Chaining) Dropdown

Each non-DIRECT slot card has a **Via** dropdown selector. This sets the `via_slot` for tunnel chaining:

- **Direct** (default) — Slot routes directly to the internet
- **via slot-N** — Slot routes through another slot's tunnel first (e.g., VLESS via AWG)

Changing the via slot triggers a dns-router reload to update routing tables.

### Slot Type Sections

Slots are organized into sections by type:

- **AmneziaWG** — AWG tunnel slots
- **Outline** — Shadowsocks (Outline) tunnel slots
- **Xray** — VLESS+Reality tunnel slots
- **Zapret** — DPI bypass slots (no VPN tunnel)
- **Direct** — Bypass slot (no tunnel)

### DNS Mode Status

When running in DNS Mode, a status section shows:

- **dnsmasq** container status (running/stopped/not found)
- **dns-router** container status (running/stopped/not found)
- Whether DNS Mode is fully active (both containers running)

### Bypass Mode Warning

If all pool configs fail for a slot and bypass mode activates, a prominent warning banner appears at the top of the Dashboard. Bypass mode means traffic for that slot's groups is going direct (unproxied) until the tunnel recovers. The banner shows which slots are in bypass mode and when bypass activated.

### Operations Bar

Long-running operations (IP checks, restarts, domain checks, traces) display progress in a floating operations bar at the bottom of the screen. Each operation shows:

- Operation type and label
- Step-by-step progress messages
- Success/failure indicators for each step
- Auto-dismiss after completion

---

## Groups

The Groups page manages domain groups and their routing assignments. It has multiple tabs.

### Overview Tab

Displays all groups as cards with summary information:

| Field | Description |
|-------|-------------|
| **Group label** | Display name (e.g., "MESSAGING", "STREAMING") |
| **Slot assignment** | Which slot handles this group's traffic |
| **Domain count** | Total domains (custom + iplist) |
| **Custom count** | Number of user-added domains |
| **IPList count** | Number of domains from iplist.opencck.org sync |
| **Critical count** | Number of critical domains (trigger failover on failure) |
| **Bandwidth** | Min/max bandwidth limits if configured |
| **IPv6 blocking** | Whether AAAA responses are blocked for this group |

**Group actions:**

- **Create Group** — Opens a dialog to create a new group with a label, slot assignment, and optional iplist group linkage.
- **Edit Group** — Modify label, slot, bandwidth limits, and IPv6 blocking.
- **Delete Group** — Remove the group and all its domain assignments. Requires confirmation.
- **Check Domains** — Run a domain health check for this group's assigned slot.

### Domains Tab

A unified, searchable table of all domains across all groups.

**Columns:**
- **Domain** — The domain name or IP/CIDR
- **Critical** — Star icon indicating whether the domain is marked as critical for failover
- **Source** — Where the domain came from: `custom` (user-added), `iplist` (synced from iplist.opencck.org), or `static` (IP/CIDR entry)
- **Group** — Which group the domain belongs to (color-coded chip)
- **Slot** — The assigned slot for the domain's group (e.g., "slot-6 AWG Estonia", "Block")
- **Note** — Optional user note for the domain
- **Health** — Last check result indicators (hover for details)

**Filters:**

Each filterable column has a dropdown in the filter row below the header:

- **Search** — Text search across domain names and notes
- **Critical filter** — Show all, only critical, or only non-critical domains
- **Source filter** — Multi-select: custom, iplist, static (with counts)
- **Group filter** — Multi-select: filter by one or more groups (with counts)
- **Slot filter** — Multi-select: filter by assigned slot (with counts)
- **Note filter** — Multi-select: filter by note value (hidden when no notes exist)

Active filters show a count bar with a "Clear filters" button.

**Other features:**
- **Pagination** — Large domain lists are paginated (25, 50, or 100 rows per page)
- **Multi-select** — Select multiple custom/static domains for bulk operations (move, delete, mark critical)
- **Inline editing** — Toggle critical status directly in the table

### Add Domain Dialog

Click the "Add Domain" button to open the dialog:

- **Domain** — Enter a domain name (e.g., `youtube.com`) or IP/CIDR (e.g., `149.154.160.0/20`)
- **Group** — Select which group to add the domain to
- **Critical** — Toggle whether this domain should trigger failover when unreachable
- **Note** — Optional note about why this domain was added

The system validates the domain format and checks for duplicates across all groups before adding.

### Domain Trace

The Domain Trace tool helps discover all domains and IP ranges used by a website.

1. Enter one or more URLs (up to 20)
2. Optionally select a specific slot to trace through
3. Click "Trace" to start
4. The tracer loads each URL through the proxy and captures all network requests
5. Results show discovered domains, their IP addresses, and which are already in groups
6. One-click "Add" buttons let you add discovered domains to groups

This is useful for finding all the CDN domains, API endpoints, and subdomains that a service uses.

### Community Domain Database

Browse curated domain categories from iplist.opencck.org:

- View available categories (e.g., "Antifilter Community", "YouTube", "Meta", etc.)
- See domain count per category
- Map categories to groups — linking a category to a group automatically syncs those domains
- Synced domains appear with source "iplist" in the domain table

### Bandwidth Limits Tab

Configure per-group bandwidth shaping (DNS Mode only):

- **Min bandwidth** — Guaranteed minimum bandwidth for this group's traffic (e.g., `5mbit`)
- **Max bandwidth** — Maximum bandwidth cap (e.g., `20mbit`)
- **Format** — Values use tc/HTB format: number followed by `kbit`, `mbit`, or `gbit`

Bandwidth limits are enforced by tc/HTB classes in the dns-router container.

---

## Keys

The Keys page manages all tunnel configurations: Shadowsocks keys, AmneziaWG configs, and VLESS/Xray configs.

### SS Keys Tab

Lists all Shadowsocks keys with:

| Column | Description |
|--------|-------------|
| **Name** | User-defined key name |
| **Server** | SS server hostname or IP |
| **Port** | SS server port |
| **Method** | Encryption method (e.g., `chacha20-ietf-poly1305`) |

**Actions:**
- **Add Key** — Paste an `ss://` URI to auto-parse all fields, or manually enter server, port, password, and method
- **Edit Key** — Modify any field, including renaming (references in pools update automatically)
- **Delete Key** — Remove a key. Protected if the key is active on any slot or in any pool.

### AWG Configs Tab

Lists all AmneziaWG configurations with:

| Column | Description |
|--------|-------------|
| **Name** | User-defined config name |
| **Endpoint** | AWG server IP (extracted from config) |

**Actions:**
- **Add Config** — Paste a WireGuard/AmneziaWG `.conf` file content. Must contain `[Interface]` and `[Peer]` sections.
- **Edit Config** — Modify the config text or rename
- **Delete Config** — Remove a config. Protected if active or in any pool.

### Xray Configs Tab

Lists all VLESS+Reality (Xray) configurations:

| Column | Description |
|--------|-------------|
| **Name** | User-defined config name |
| **Server** | Xray server IP address |
| **Port** | Server port (typically 443) |
| **Tag** | Location tag (e.g., "Poland", "Germany") |

**Actions:**
- **Add Config** — Enter server address, port, VLESS UUID, Reality public key, short ID, server name (SNI), flow, fingerprint, and tag
- **Edit Config** — Modify any field or rename
- **Delete Config** — Remove a config. Protected if active or in any pool.

### Health Check

The "Health Check" button tests connectivity and latency for all keys and configs:

- **SS keys** — TCP connect to server:port (measures SYN-ACK round-trip time)
- **AWG configs** — TCP connect to endpoint IP on common ports (22, 443, 80), falling back to ICMP ping

Results show:
- **Reachable** — Whether the server responded
- **Latency** — Round-trip time in milliseconds

All checks run in parallel for speed.

### Delete Protection

Keys and configs that are currently active on a slot or present in any slot's failover pool cannot be deleted. You must first remove them from all pools and deactivate them before deletion is allowed.

---

## Logs

The Logs page provides a real-time log viewer for the Proxima backend.

**Controls:**

| Control | Description |
|---------|-------------|
| **Slot filter** | Filter logs by slot. Dropdown shows slot ID and label (e.g., "slot-1 — Estonia"). Matches `[SLOT-N]` tags in log lines. |
| **Level filter** | Filter by severity: All, DEBUG, INFO, WARNING, ERROR |
| **Line count** | Number of log lines to load from the server (default: 300, max: 2000) |
| **Search** | Client-side text search — filters visible lines instantly as you type. Matching text is highlighted in yellow. |
| **Auto-refresh** | Toggle switch — when on, logs reload automatically every 5 seconds |
| **Refresh** | Manual refresh button |

**Line counter:** A "N / total lines" count is displayed above the log panel, showing how many lines match the current search out of the total loaded lines.

**Log format:**
```
2026-04-15 01:39:00 INFO [SLOT-6] IP check OK: 89.105.208.130
2026-04-15 01:39:05 WARNING [SLOT-1] Domain check failed: youtube.com — ConnectionError
2026-04-15 01:39:10 ERROR [SLOT-2] Failover triggered — rotating to next key in pool
```

Logs are displayed newest-first. The log file rotates daily with 7-day retention.

**Color coding:**
- Red — ERROR
- Orange — WARNING
- Grey — DEBUG
- Default — INFO

---

## Performances

The Performances page shows key success rate statistics over time, helping identify unreliable VPN servers.

### Time Series Charts

Line charts showing daily success/failure counts for each key:

- **X-axis** — Date
- **Y-axis** — Number of successful and failed checks
- **Lines** — One line per key, color-coded

### Time Range Selection

| Range | Description |
|-------|-------------|
| **1 Week** | Last 7 days (default) |
| **1 Month** | Last 30 days |
| **3 Months** | Last 90 days |
| **6 Months** | Last 180 days |

### All-Time Statistics Table

A table showing cumulative statistics per key:

| Column | Description |
|--------|-------------|
| **Key name** | The SS key or AWG config name |
| **Total checks** | Total number of IP/domain checks |
| **Successes** | Number of successful checks |
| **Failures** | Number of failed checks |
| **Success rate** | Percentage of successful checks |

### Reset

The "Reset" button allows clearing performance data:
- **Current period** — Resets in-memory counters only
- **All data** — Wipes the SQLite database performance records as well

---

## Speed Test

The Speed Test page measures tunnel throughput and latency through each active slot's SOCKS5 proxy against a dedicated speed test server.

### Running a Test

- **Run All** — Runs all active slots plus a direct (no-proxy) baseline in parallel
- **Run Slot** — Run the test for a specific slot only

Tests run with a progress bar per slot showing latency → download → upload steps.

### Result Cards

Each slot shows a result card with:

| Field | Description |
|-------|-------------|
| **Download** | Measured download speed in Mbps |
| **Upload** | Measured upload speed in Mbps |
| **Latency** | Average round-trip time in ms (5 samples, highest dropped) |
| **TTFB** | Time to first byte on the download request — reflects connection setup and DPI overhead. Low TTFB (< 200ms) indicates a healthy tunnel with no DPI interference. |
| **Badge** | Full / Partial / Error |
| **Egress IP** | The tunnel exit IP active at test time |

**Full** — All three measurements succeeded.
**Partial** — Latency measured but DL/UL skipped (hairpin tunnel or DPI timeout).
**Error** — All measurements failed.

### Direct Baseline

The **Direct** card shows results without any proxy — raw server-to-speed-test-server performance. On Moscow servers this shows latency only because Russian ISP DPI blocks large outbound TCP transfers to Germany.

### History Chart

A line chart below the result cards shows historical speed test results per slot over the last 7 days. Each slot is a separate line for download and upload speeds.

### Settings

The speed test server URL and API key are configured in **Settings → Speed Test Server**. Test file sizes (download and upload, in MB) are also configurable there.

> **See also:** [Keys & Tunnel Management](/docs/keys-tunnels.md) for details on how speed test handles AWG hairpin and DPI limitations

---

## Users

> **Note:** This page is only available in DNS Mode with per-user auth enabled. It is visible only to admin users.

The Users page manages user accounts and their device authentication for selective VPN routing.

### User List

| Column | Description |
|--------|-------------|
| **Username** | Account username |
| **Role** | `admin` (full access) or `user` (limited access) |
| **Enabled** | Whether the account is active |
| **Device count** | Number of currently authenticated devices |
| **Peer count** | Number of ProximaVPN peers owned by this user |
| **Routing mode** | `full` (all groups) or `selected` (assigned groups only) |

### User Actions

- **Create User** — Add a new user with username, password, role, max peers, bandwidth quota, speed limits, and assigned groups
- **Edit User** — Change password, role, enabled status, routing mode, assigned groups, speed limits, or bandwidth quota. Disabling a user immediately revokes all their device authentications.
- **Delete User** — Remove the user account. Cannot delete your own account. Optionally cascade-delete owned peers. All device auths are revoked on deletion.

### Device Management

Expanding a user row shows their authenticated devices:

| Column | Description |
|--------|-------------|
| **IP address** | The device's current LAN IP |
| **User agent** | Browser/app identification string |
| **Last seen** | Timestamp of last activity |

- **Disconnect** — Revoke authentication for a specific device. Removes the IP from the nftset, so the device's traffic immediately stops going through VPN.

### Per-User Auth

When per-user auth is enabled in [Settings](#settings):
- Only devices belonging to logged-in users get VPN routing
- The network default is direct internet (no VPN)
- Device IPs are added to an nftables nftset on login
- IPs are refreshed periodically and on browser visibility changes
- Logging out removes the device IP from the nftset

---

## ProximaVPN

> **Note:** This page is only available in DNS Mode when a VPN server is configured. It is visible only to admin users.

ProximaVPN provides a WireGuard hop for mobile devices on restricted networks (e.g., Russian LTE where direct VPN connections are blocked by DPI).

### Server Status

| Field | Description |
|-------|-------------|
| **Interface** | WireGuard interface name (e.g., `wg1`) |
| **Endpoint** | Public IP and port for client connections |
| **Subnet** | VPN subnet (e.g., `10.14.14.0/24`) |
| **Listen port** | UDP port for WireGuard |
| **Peer count** | Number of configured peers |
| **Available** | Whether the WireGuard tools are installed on the server |

### Peer List

Each peer card shows:

| Field | Description |
|-------|-------------|
| **Name** | Peer name (e.g., "Can's Phone", "Office Laptop") |
| **Owner** | VPN user who owns this peer (if assigned). Peers can be unowned (admin-managed) or owned by a VPN user. |
| **Address** | Assigned VPN IP (e.g., `10.14.14.2/32`) |
| **Last handshake** | Timestamp of the most recent WireGuard handshake |
| **Transfer** | Bytes received and transmitted |
| **Endpoint** | The peer's real IP and port (if connected) |
| **LAN access** | Whether this peer can access other devices on the server's LAN |

### Add Peer

1. Enter a name for the new peer
2. The system automatically generates a keypair and assigns the next available IP
3. On creation, client configuration is immediately available

### Client Configuration

After creating a peer, the following are provided:

- **QR Code** — Scan with AmneziaVPN or WireGuard app to import configuration
- **Config text** — Full WireGuard configuration for manual copy/paste
- **AmneziaWG config** — Configuration with AmneziaWG-specific obfuscation parameters

The "Get Config" button on existing peers regenerates the configuration display (requires the private key to be stored).

### LAN Access Toggle

Each peer has a LAN access toggle:
- **Enabled** — Peer can access other devices on the server's LAN (e.g., NAS, printers)
- **Disabled** — Peer can only access the internet through the VPN tunnel

### Peer Limits

Click the gear icon (⚙) on any peer to open the **Peer Limits Drawer** — a right-side panel for configuring per-peer access control and bandwidth limits.

**Master toggle** — Enable or disable limits for this peer. When disabled, the peer has unrestricted access to all groups.

**Total bandwidth** — Set download/upload bandwidth caps for the peer's total traffic (in mbit).

**Per-group access** — Each VPN group is listed with:
- An access toggle (allow/deny)
- Optional per-group bandwidth limits (download/upload in mbit) when access is allowed

Peers with active limits show a "Limits" warning chip next to their name in the peer table.

> **Note:** Limits are currently stored in config only. nftables/tc enforcement on wg1 is planned for Phase 2.

### Compare Matrix

Click the **Compare** button in the header to switch from the peer table to the **Compare Matrix** view — a read-only table showing all peers across all groups:

- **Rows** = domain groups (with slot chip)
- **Columns** = peers (clickable to open the limits drawer)
- **First row** = total bandwidth per peer
- **Cells** show: ✓ (allowed), ✗ (blocked), or bandwidth values
- Peers without limits show "All Access" chips

Click any cell or peer name to open the limits drawer for that peer. Click "Back to Peers" to return to the table view.

---

## Scheduler

The Scheduler page provides visibility into all background jobs running in Proxima. It shows when each job last ran, when it will run next, and allows manual triggering. This page is **admin-only**.

### Job List

The page displays a table with all scheduled jobs:

| Job | Scope | Default Interval | Description |
|-----|-------|-----------------|-------------|
| **IP Check** | Per-slot | 30 min | Verifies each tunnel exits at the expected IP |
| **Domain Check** | Per-slot | 60 min | Tests critical domains are reachable through VPN |
| **Tunnel Health** | Global | 30 min | Checks dns-router, nftables rules, TUN devices (DNS Mode only) |
| **Bandwidth Sampling** | Global | 60 sec | Records per-tunnel RX/TX byte deltas (DNS Mode only) |
| **iplist Sync** | Global | 24 hours | Updates community domain database from iplist.opencck.org |

### Per-Slot Jobs

IP Check and Domain Check run independently for each active slot. They are displayed as grouped rows:
- **Parent row** — The job name with a Run button that triggers checks for all slots
- **Sub-rows** — One per active slot, showing individual last/next run times and status

### Status Indicators

Each job row shows a colored status dot:
- **Green** — Last run succeeded
- **Red** — Failures detected (fail count > 0) or bypass mode active
- **Grey** — Never run yet

Per-slot rows also show status chips:
- **OK** — No issues
- **Failed (N)** — Number of consecutive failures
- **Bypass** — Bypass mode active (all pool configs exhausted)

### Manual Triggers

Each job has a play button to trigger it immediately. This bypasses the interval timer and runs the job right away. DNS-only jobs (Tunnel Health, Bandwidth Sampling) are disabled when not in DNS Mode.

### Auto-Refresh

The page auto-refreshes every 30 seconds. Relative times ("2m ago", "in 28m") update every 10 seconds.

---

## Settings

The Settings page provides system-wide configuration options.

### Server

| Setting | Description |
|---------|-------------|
| **Deployment** | Server identifier code (e.g., `ERG`, `OFC`) |
| **LAN IP** | Server's IP on the local network (used for proxy endpoints and DNS config) |
| **Public IP** | Server's public IP address |

### Health Checks

| Setting | Description | Default |
|---------|-------------|---------|
| **IP check interval** | Minutes between automatic IP checks | 30 |
| **Domain check interval** | Minutes between automatic domain checks | 60 |
| **IP retries** | Number of retry attempts for failed IP checks | 2 |
| **Domain retries** | Number of retry attempts for failed domain checks | 2 |

### Bandwidth

| Setting | Description |
|---------|-------------|
| **Total VPN bandwidth** | Maximum total bandwidth for all VPN traffic combined (e.g., `100mbit`). This sets the root class for tc/HTB shaping. |

### Proxy Gateway

The proxy gateway provides an HTTP proxy endpoint for Docker containers that need VPN access.

| Setting | Description |
|---------|-------------|
| **Enabled** | Toggle the proxy gateway on/off |
| **Upstream slot** | Which slot the proxy gateway forwards traffic through |
| **Status** | Whether the gateway process is currently running |
| **Address** | The proxy URL for container configuration (e.g., `http://proxima:8080`) |

### DNS Upstream

The upstream DNS server that dnsmasq forwards non-intercepted queries to. Examples:
- `8.8.8.8` — Google DNS
- `127.0.0.1#5353` — Local AdGuard on port 5353
- `192.168.77.1` — Router DNS

### Local Domains

A list of local domain overrides for hairpin NAT fixes. These domains are resolved directly by the server instead of going through VPN. Useful when services on the local network use public domain names that would otherwise be routed through VPN.

### LAN Subnets

A list of LAN CIDR subnets used by ProximaVPN's LAN Access control. When a VPN peer has LAN access disabled, traffic to these subnets is blocked with FORWARD DROP rules.

- **Default behavior:** If not configured, a single `/24` is derived from the server's LAN IP.
- **Multi-subnet:** Add all LAN subnets that should be controlled (e.g., `192.168.2.0/24`, `192.168.1.0/24`).
- **UI:** Chip-based editor (same interaction pattern as Local Domains) -- type a CIDR and press Enter to add.
- **Validation:** Each entry is validated as a valid IPv4 CIDR notation.
- **Effect:** Changing subnets triggers an async re-apply of LAN access rules for all VPN peers. Old rules from removed subnets are cleaned up automatically.

### Speed Test Server

Configure the speed test server for tunnel throughput measurement:

| Setting | Description |
|---------|-------------|
| **URL** | Base URL of the global speed test server (e.g., `https://46.224.49.250:8999`) |
| **API Key** | Bearer token for authentication |
| **Download size** | Size of the test download payload in MB |
| **Upload size** | Size of the test upload payload in MB |

A second table in this section allows per-key configuration. Each slot/key can use:

- **Global** — Use the global server URL and API key above. The URL field shows "Uses global server URL" (read-only).
- **Public** — Use a per-key URL pointing to a public CDN speed test (no auth required). Useful for slots where a geographically closer server gives more accurate measurements. A dropdown of preset public URLs is provided.

### Config Sync

Synchronize domain groups between Proxima servers:

- **Sync source URL** — URL of another Proxima server's export endpoint
- **Import preview** — Shows a diff of what would change (new groups, new domains)
- **Apply import** — Merge remote groups and domains into the local configuration

### Per-User Auth

Toggle per-user authentication for DNS Mode:
- When enabled, only authenticated devices get VPN routing
- When disabled, all devices on the network get VPN routing
- Toggling this regenerates nftables rules

### Account

- **Change password** — Requires current password and new password (minimum 4 characters)

---

## Navigation & Layout

### Sidebar

The navigation sidebar provides access to all pages:

| Behavior | Description |
|----------|-------------|
| **Expanded** | 200px wide, shows icons and labels |
| **Collapsed** | 60px wide, shows icons only |
| **Toggle** | Click the collapse button to switch between expanded and collapsed |

### Mode-Aware Items

Navigation items are context-aware:

- **Users** — Only shown in DNS Mode with per-user auth capability
- **ProximaVPN** — Only shown in DNS Mode with VPN server configured

### Role-Based Visibility

Navigation items respect user roles:

- **Admin** — Sees all pages
- **User** — Cannot see Users, ProximaVPN, Scheduler, or admin-only Settings sections

### Language Selector

A language dropdown in the sidebar footer allows switching between:

- **EN** — English (default)
- **TR** — Turkish
- **RU** — Russian

The language preference is saved in local storage and persists across sessions.

### Mobile Responsive

On small screens (below the `md` breakpoint):

- The sidebar becomes a temporary drawer that slides in from the left
- Opened via a hamburger menu button in the top-left corner
- Closes automatically when a navigation item is selected
- All functionality remains available on mobile

### Theme

The UI uses a consistent dark theme with MUI v6:

- Dark background with light text
- Accent colors for interactive elements
- Color-coded health indicators (green, red, grey, orange)
- Cards and panels with subtle elevation
