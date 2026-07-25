# Domain Management

Proxima routes internet traffic based on domain names. Domains are organized into **groups**, and each group is assigned to a **slot** (VPN tunnel). When a device on your network requests a domain that belongs to a group, the traffic is transparently routed through that group's assigned tunnel.

This document covers how to create groups, add domains, use the community database, trace domains, and manage CDN IP ranges.

---

## Groups

Groups are the primary organizational unit in Proxima. Each group contains a list of domains and maps them to a specific VPN tunnel slot.

### Creating a Group

1. Go to the **Groups** page in the Proxima UI
2. Click **New Group**
3. Enter a label (display name) for the group
4. Select which slot should handle this group's traffic
5. Click **Create**

The group ID is automatically generated from the label as a lowercase slug (e.g., "Video Streaming" becomes `video-streaming`).

### Group Properties

| Property | Type | Description |
|----------|------|-------------|
| `id` | string | Machine-readable identifier, auto-generated from label |
| `label` | string | Display name shown in the UI, editable |
| `slot` | number | Which slot handles this group's traffic (1-8) |
| `domains` | array | List of domain entries routed through this group |
| `critical_domains` | array | Subset of domains that trigger failover when unreachable |
| `bandwidth` | object | Min/max bandwidth limits in kbps (DNS Mode only) |
| `block_ipv6` | boolean | Whether to block AAAA DNS responses for this group's domains |

### Assigning Groups to Slots

Each group must be assigned to exactly one slot. The slot determines which VPN tunnel carries the group's traffic.

Multiple groups can share the same slot. This is common in DNS Mode where a single AWG tunnel handles all proxied traffic:

```
MESSAGING group    -->  slot-6  -->  awg-client-slot-6
STREAMING group    -->  slot-6  -->  awg-client-slot-6 (shared)
AI group           -->  slot-6  -->  awg-client-slot-6 (shared)
SOCIAL group       -->  slot-6  -->  awg-client-slot-6 (shared)
```

To change a group's slot, edit the group and select a different slot from the dropdown. Only enabled slots appear in the dropdown.

### Blocked Groups

Blocked groups perform DNS-level blocking for their domains. Instead of routing traffic, dnsmasq returns `0.0.0.0` for these domains, effectively blocking access. This is useful for ad-blocking or restricting access to specific services.

---

## Adding Domains

### Single Domain Add

1. Open a group on the **Groups** page
2. Click **Add Domain**
3. Enter the domain name (e.g., `youtube.com`)
4. Optionally add a note describing the domain's purpose
5. Click **Add**

### Domain Validation Rules

Proxima validates every domain before adding it:

- **Format:** Must be a valid domain name (letters, numbers, hyphens, dots) or a valid CIDR range
- **Maximum length:** 253 characters (per DNS specification)
- **No protocol prefix:** Enter `youtube.com`, not `https://youtube.com`
- **No trailing dot:** Enter `youtube.com`, not `youtube.com.`
- **No wildcard prefix needed:** dnsmasq automatically matches all subdomains (see [Best Practices](#best-practices))

### Cross-Group Duplicate Prevention

Proxima enforces that each domain exists in at most one group. Having the same domain in multiple groups causes unpredictable routing (nftables first-match-wins ambiguity).

**Single domain add:** If the domain already exists in another group's `custom_domains`, the API returns a `409` error with the existing group's name and ID. You must remove it from the other group first, or use the Move function.

**Bulk domain add:** Domains that exist in other groups are reported in a separate `duplicates` array (with group ID and label) and are not added. Domains already in the target group are reported as `skipped`.

**Config sync (merge mode):** Domains that already exist in other local groups are silently skipped during import.

**Config sync (full mode):** Since the remote is the source of truth, domains are automatically moved from the other local group to the synced group. The backend logs each cross-group move.

### IP Ranges (CIDR Notation)

Some services use IP addresses directly rather than domain names. You can add CIDR ranges to a group:

```
149.154.160.0/20    (Telegram)
91.108.4.0/22       (Telegram)
2001:67c:4e8::/48   (Telegram IPv6)
```

IP ranges are added to the nftables sets directly, without needing DNS resolution. This is essential for services like Telegram that connect to IP addresses without DNS lookups.

### Domain Notes

Each domain entry supports an optional **note** field. Use notes to document:

- Why the domain was added (e.g., "CDN for YouTube thumbnails")
- When it was added or who requested it
- Which service depends on it

Notes are visible in the domain list and can be filtered using the **Note filter** dropdown in the Domains tab. Notes do not affect routing.

---

## Filtering Domains

The Domains tab provides six independent filters that can be combined:

| Filter | Type | Description |
|--------|------|-------------|
| **Search** | Text input | Searches domain names and notes (case-insensitive, debounced) |
| **Critical** | Single-select | All / Critical only / Non-critical only |
| **Source** | Multi-select | Filter by custom, iplist, or static (with counts) |
| **Group** | Multi-select | Filter by one or more groups (with counts) |
| **Slot** | Multi-select | Filter by assigned slot, e.g., "slot-6 AWG Estonia" (with counts) |
| **Note** | Multi-select | Filter by note value (hidden when no notes exist) |

When any filter is active, a status bar shows how many domains match out of the total, with a "Clear filters" button to reset all filters at once.

The **Slot column** shows the resolved slot name for each domain's group (e.g., "slot-6 AWG Estonia", "slot-7 SS Russia", "Block"). This makes it easy to identify which tunnel a domain's traffic uses without navigating to the group's settings.

---

## Bulk Domain Operations

The Groups page supports efficient bulk operations for managing large domain lists.

### Multi-Select

- Click the checkbox next to individual domains to select them
- Use the "Select All" checkbox in the header to select all visible domains
- The selection toolbar appears when one or more domains are selected

### Bulk Move

1. Select the domains you want to move
2. Click **Move** in the selection toolbar
3. Choose the target group from the dropdown
4. Confirm the move

All selected domains are removed from the current group and added to the target group. Duplicate checks are performed before the move completes.

### Bulk Delete

1. Select the domains you want to remove
2. Click **Delete** in the selection toolbar
3. Confirm the deletion

This permanently removes the selected domains from the group.

### Import / Export Groups as JSON

#### Exporting

1. Click the **Export** button on the Groups page
2. A JSON file is downloaded containing all groups with their domains, critical domains, and settings
3. Use this for backup or transferring configuration between Proxima instances

The export format:

```json
{
  "groups": [
    {
      "id": "streaming",
      "label": "Streaming",
      "slot": 6,
      "domains": [
        { "domain": "youtube.com", "note": "Main site" },
        { "domain": "googlevideo.com", "note": "Video CDN" }
      ],
      "critical_domains": ["youtube.com"],
      "bandwidth": { "min": 0, "max": 0 },
      "block_ipv6": true
    }
  ]
}
```

#### Importing

Proxima supports importing groups from a remote Proxima instance via URL or from inline JSON data.

**Sync Modes:**

| Mode | Behavior | Use Case |
|------|----------|----------|
| **Merge** (default) | Only adds new domains, notes, and critical domains from remote. Existing local data is preserved. | Safe incremental sync |
| **Full** | Remote is source of truth. Overwrites `custom_domains`, `notes`, and `critical_domains` to match remote exactly. Domains not in remote are removed. | Full mirror from primary server |

**Import workflow:**

1. Go to **Settings** > **Config Sync**
2. Enter the remote URL (e.g., `http://192.168.2.91:5000/api/groups/export`)
3. Select sync mode: **Merge** or **Full Sync**
4. Click **Preview** to see the diff (added, removed, changed)
5. Review the preview — in Full mode, removed domains are highlighted
6. Click **Apply** to execute

**Cross-group dedup:** In merge mode, domains already in other local groups are skipped. In full mode, they are moved from the other group to maintain source-of-truth semantics. See [Cross-Group Duplicate Prevention](#cross-group-duplicate-prevention).

---

## Critical Domains

Critical domains are the subset of a group's domains that Proxima actively monitors during [health checks](/docs/health-failover.md). Only failures on critical domains trigger automatic failover.

### Why Critical Domains Matter

Not every domain in a group is equally important or reliable for health checking:

- CDN domains may return different status codes depending on the request
- Some domains are region-specific and may not resolve from the VPN exit
- API domains may require authentication to return a successful response

Critical domains should be the **most reliable, always-reachable** domains that definitively prove the tunnel is working.

### Automatic Critical Domain Assignment

For **single-domain groups**, the only domain is automatically marked as critical. There is no need to manually configure it.

For **multi-domain groups**, you must explicitly mark which domains are critical. If no domains are marked as critical, the group will not participate in failover health checks.

### How Critical Domain Checks Work

During a scheduled domain check:

1. Proxima fetches each critical domain via the group's assigned slot
2. Any HTTP response (even 4xx/5xx) counts as **success** -- it proves the tunnel works
3. Only connection errors (timeout, refused, DNS failure) count as **failure**
4. If all critical domains fail, failover is triggered for the slot

> **See also:** [Health & Failover](/docs/health-failover.md) for the complete failover algorithm

### Best Practices for Critical Domains

- **Choose 1-3 critical domains per group** -- enough for reliable detection, not so many that checks are slow
- **Use the primary domain**, not CDN subdomains (e.g., `youtube.com` not `ytimg.com`)
- **Avoid naked CDN domains** that have no DNS A record (e.g., `ggpht.com`) -- these fail DNS resolution and produce false alarms
- **Pick domains that always return an HTTP response** -- even a 403 is fine, as long as the connection succeeds

---

## Community Domain Database

Proxima includes a curated database of approximately 2000 commonly blocked domains, organized by category. This database helps you quickly populate your groups with relevant domains without manual research.

### Categories

The community database organizes domains into categories:

| Category | Examples |
|----------|---------|
| **Video** | youtube.com, vimeo.com, twitch.tv |
| **Music** | spotify.com, soundcloud.com |
| **AI** | openai.com, claude.ai, gemini.google.com |
| **Social** | instagram.com, twitter.com, facebook.com |
| **News** | bbc.com, medium.com |
| **Messaging** | telegram.org, whatsapp.com |
| **Developer** | github.com, stackoverflow.com |
| **Search** | google.com, duckduckgo.com |
| **Cloud** | amazonaws.com, cloud.google.com |

### Auto-Sync

The community database automatically syncs from the [Re-filter](https://github.com/nickspaargaren/no-google) filter list source every 24 hours. The sync runs as a background scheduled task.

You can also trigger a manual sync from the **Groups** page by clicking **Sync Community DB**.

### Browsing and Searching

1. On the **Groups** page, click **Community DB**
2. Browse categories in the sidebar
3. Use the search bar to find specific domains across all categories
4. Each domain shows which category it belongs to

### Mapping Categories to Groups

1. In the Community DB panel, select one or more categories
2. Click **Map to Group**
3. Choose which Proxima group should receive the domains
4. Click **Apply**

Domains are added to the target group. Duplicates (domains already in the group) are skipped automatically.

### Category Mappings

You can save persistent mappings between community DB categories and your groups. When the community database syncs new domains, the mappings allow you to quickly apply updates:

1. Go to **Community DB** > **Mappings**
2. Assign each category to a group (or leave unmapped)
3. Click **Apply Mappings** to add any new domains from mapped categories

---

## Domain Trace

Domain Trace is a discovery tool that helps you find all the domains and IP ranges a service uses. Many services load resources from multiple CDN domains, and missing even one can break functionality.

### How to Use Domain Trace

1. On the **Groups** page, click **Domain Trace**
2. Enter a URL (e.g., `https://youtube.com`)
3. Click **Trace**

Proxima opens the URL through the VPN tunnel and records:

- All HTTP redirects followed
- All resource domains loaded (scripts, images, API calls)
- DNS resolutions and IP addresses

### Reading Trace Results

The results table shows:

| Column | Description |
|--------|-------------|
| **Domain** | The discovered domain name |
| **Status** | Whether the domain is already in a group or new |
| **Group** | If already assigned, which group it belongs to |
| **Action** | Button to add the domain to a group |

Domains are color-coded:
- **Green** -- Already in a group (no action needed)
- **Yellow** -- New domain, not yet in any group
- **Red** -- Domain that failed to load (may indicate a problem)

### Adding Discovered Domains

For each new domain in the trace results, you can:

1. Click **Add** next to the domain
2. Select the target group
3. The domain is immediately added

This is the recommended workflow for setting up a new service:

1. Trace the main URL
2. Add all discovered CDN/API domains to the appropriate group
3. Test the service
4. Trace again if something is still broken (some resources load lazily)

### Common CDN Domains Found by Trace

When tracing `youtube.com`, you will typically discover:

```
youtube.com              (main site)
googlevideo.com          (video streams)
ytimg.com                (thumbnails)
ggpht.com                (profile images)
googleapis.com           (API calls)
gstatic.com              (static assets)
google.com               (auth/accounts)
```

Without these CDN domains in your group, YouTube would partially load but videos would fail to play.

---

## CDN IP Range Management (iplist)

Some services (notably Google, Cloudflare, Telegram, and AWS) publish their IP ranges for network operators. Proxima can fetch these ranges and add them to nftables sets directly, ensuring traffic is routed correctly even without DNS resolution.

### Static Routes Configuration

IP ranges are managed in `static_routes.json` within the config directory. Each entry defines a service with its IP ranges and fetch source:

```json
{
  "services": [
    {
      "name": "google",
      "group": "streaming",
      "ranges": ["142.250.0.0/15", "172.217.0.0/16"],
      "fetch_url": "https://www.gstatic.com/ipranges/goog.json",
      "fetch_format": "goog_json"
    },
    {
      "name": "telegram",
      "group": "messaging",
      "ranges": ["149.154.160.0/20", "91.108.4.0/22"],
      "fetch_url": "https://core.telegram.org/resources/cidr.txt",
      "fetch_format": "text_lines"
    }
  ]
}
```

### Supported Fetch Formats

| Format | Source | Description |
|--------|--------|-------------|
| `goog_json` | Google | Google's IP range JSON format with `prefixes` array |
| `text_lines` | Telegram, Cloudflare | Plain text with one CIDR range per line |
| `aws_json` | AWS | Amazon's `ip-ranges.json` format with `prefixes` array |

### Auto-Refresh

Proxima can automatically refresh IP ranges from their authoritative sources:

1. Go to **Settings** or use the API endpoint
2. Click **Refresh CDN Ranges** or call `POST /api/static-routes/refresh`
3. Proxima fetches the latest ranges from each service's `fetch_url`
4. A diff is shown: new ranges added, old ranges removed
5. Click **Apply** or call `POST /api/static-routes/apply-refresh` to commit changes

After applying, the nftables sets are regenerated and reloaded.

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/static-routes` | List all static route services and their ranges |
| `POST` | `/api/static-routes/refresh` | Fetch latest ranges (returns diff) |
| `POST` | `/api/static-routes/apply-refresh` | Apply the fetched ranges |

---

## Domain Changes in DNS Mode

When you add, remove, or move domains in the Proxima UI, the changes must propagate to the data plane. Here is what happens under the hood:

### Propagation Flow

```
1. UI saves domain changes to proxima-config.json
2. Backend regenerates dnsmasq config files:
   - proxima-domains.conf    (domain → nftset mappings)
   - proxima-ipv6-block.conf (AAAA blocking per group)
3. Backend sends SIGHUP to the dnsmasq container
4. dnsmasq reloads config without restarting
5. New DNS queries populate the updated nftset entries
6. nftables routes traffic based on the updated sets
```

### Key Points

- **No restart needed** -- dnsmasq reloads on `SIGHUP`, existing connections are unaffected
- **One line per domain** -- each domain gets its own nftset line in the config (never joined into one line, which would exceed buffer limits)
- **nftset timeout** -- resolved IPs stay in the nftset for 3600 seconds (1 hour) by default
- **dnsmasq cache** -- enabled with `cache-size=1000`, safe because DNS TTLs are much shorter than the nftset timeout
- **IPv6 blocking** -- when `block_ipv6` is true for a group, dnsmasq returns `::` for AAAA queries, forcing clients to use IPv4 where nftables can intercept

---

## Best Practices

### Use Implicit Wildcard Matching

dnsmasq automatically matches all subdomains of a domain. Adding `youtube.com` also matches `www.youtube.com`, `m.youtube.com`, `music.youtube.com`, etc.

You do **not** need to add each subdomain separately. Only add the root domain:

```
youtube.com        -->  matches *.youtube.com
googleapis.com     -->  matches *.googleapis.com
```

The exception is when you want to route a subdomain differently from its parent domain. In that case, add both the parent and the subdomain to different groups -- the more specific entry takes priority in dnsmasq.

### Keep Critical Domain Lists Small

Choose 1-3 critical domains per group. Every critical domain is checked on each health check cycle, so large lists slow down the process and increase false-positive risk.

Good critical domains:
- `youtube.com` (always responds, widely available)
- `api.openai.com` (stable API endpoint)
- `web.telegram.org` (reliable web interface)

Poor critical domains:
- `ytimg.com` (no A record on naked domain)
- `cdn.example.com` (CDN-specific, may vary by region)
- `login.service.com` (may require auth to respond)

### Use Domain Trace for New Services

When adding a new service, always start with Domain Trace rather than guessing which domains are needed. Services often use 5-15 different CDN and API domains that are not obvious from the main URL.

### Sync Community DB Regularly

The community database is updated with new domains as services change their infrastructure. Regular syncing (automatic every 24 hours) ensures your domain lists stay current without manual intervention.

### Organize Groups by Service Type

Group domains by the type of service, not by the specific service. This makes management easier as you add more domains:

```
STREAMING   -->  youtube.com, twitch.tv, vimeo.com
AI          -->  openai.com, claude.ai, gemini.google.com
SOCIAL      -->  instagram.com, twitter.com, facebook.com
```

Rather than:

```
YOUTUBE     -->  youtube.com, googlevideo.com, ytimg.com
CHATGPT     -->  openai.com, oaiusercontent.com
```

The service-type approach means all services in a group share the same slot, bandwidth limits, and failover behavior.

### Monitor Domain Check Results

Check the **Performances** page periodically to see domain check success rates. Consistently failing domains may indicate:

- The domain no longer exists
- The domain is blocked at the VPN exit
- The domain requires a different routing path

> **See also:** [Health & Failover](/docs/health-failover.md) for monitoring details, [Keys & Tunnels](/docs/keys-tunnels.md) for tunnel management
