# Troubleshooting

This guide covers common issues encountered when running Proxima in DNS Mode and their solutions. For architecture details, see the [DNS Mode](dns-mode.md) documentation. For deployment procedures, see the [Deployment & Operations](deployment.md) guide.

---

## DNS Not Resolving

**Symptom:** Devices using Proxima as their DNS server cannot resolve domain names. Browsers show "DNS_PROBE_FINISHED_NXDOMAIN" or similar errors.

### Check dnsmasq Container

```bash
docker compose --profile dns ps dnsmasq
```

The container should show `Up` status. If it is restarting or exited, check the logs:

```bash
docker compose --profile dns logs --tail=50 dnsmasq
```

Common causes for dnsmasq failure:
- Invalid config syntax in generated domain files
- Port 53 already in use by another service (systemd-resolved, AdGuard, etc.)

### Check Port 53 Is Open

```bash
# Check if port 53 is listening
ss -tlnp | grep ':53'
ss -ulnp | grep ':53'

# Check firewall (Ubuntu/Debian)
sudo ufw status | grep 53
```

If port 53 is blocked by the firewall:

```bash
sudo ufw allow 53
```

On ERG, AdGuard Home has been moved to port 5353 so dnsmasq can bind to port 53. Verify AdGuard is not conflicting:

```bash
ss -tlnp | grep ':53 '
```

### Verify Client DNS Settings

The client device must have its DNS server set to the Proxima server IP:

- **ERG clients:** DNS should point to `192.168.2.91`
- **OFC clients:** DNS should point to `192.168.77.121`

Test DNS resolution from the client:

```bash
# From a client machine
dig youtube.com @192.168.2.91
nslookup youtube.com 192.168.2.91
```

### Check Upstream DNS

Proxima forwards non-proxied DNS queries to an upstream resolver. Check the `dns_upstream` setting in `proxima-config.json`:

- **ERG:** `127.0.0.1#5353` (AdGuard Home)
- **OFC:** `192.168.77.1` (MikroTik router)

Verify the upstream file exists and is correct:

```bash
cat /config/dnsmasq/proxima-upstream.conf
# Should contain: server=UPSTREAM_IP#PORT
```

**Important:** If dnsmasq is running (port 53 listening) but DNS queries time out, the upstream server may be wrong or unreachable. Test the upstream directly:

```bash
# Test upstream DNS (replace with your configured upstream)
dig @127.0.0.1 -p 5353 github.com +short +timeout=3

# If upstream fails, test a known-good DNS
dig @8.8.8.8 github.com +short +timeout=3
```

If the upstream is unreachable, fix `proxima-upstream.conf` AND the `dns_upstream` setting in `proxima-config.json` (Proxima regenerates the file from config on restart). Then restart dnsmasq:

```bash
docker restart dnsmasq
```

---

## Websites Not Loading Through VPN

**Symptom:** DNS resolves correctly, but websites time out or fail to connect. Traffic is not reaching the VPN tunnel.

### Check the Full Data Plane

The DNS Mode data plane has several components that must all be running:

```bash
# 1. Check dns-router container
docker compose --profile dns ps dns-router

# 2. Check AWG client containers
docker compose --profile dns ps awg-client-slot-1

# 3. Check tun0 interface exists (inside dns-router)
docker compose --profile dns exec dns-router ip addr show tun0

# 4. Check gost SOCKS5 proxy is running
docker compose --profile dns exec dns-router ss -tlnp | grep 1080

# 5. Check tun2socks is running
docker compose --profile dns exec dns-router ps aux | grep tun2socks
```

### Verify nftables Sets Have IPs

When dnsmasq resolves a proxied domain, it adds the IP to an nftables set. If the set is empty, no traffic will be marked for VPN routing:

```bash
# Check if proxied IPs are in the nftables set
docker compose --profile dns exec dns-router nft list set inet proxima proxied

# Check all sets for a specific group
docker compose --profile dns exec dns-router nft list sets inet proxima
```

If the sets are empty:
- dnsmasq may not be generating nftset entries (check `proxima-domains.conf`)
- The domain may not have been queried yet (nftset entries are populated on DNS query)

### Test SOCKS5 Proxy Directly

Bypass the full routing chain and test the SOCKS5 proxy that feeds tun2socks:

```bash
# From the dns-router container
docker compose --profile dns exec dns-router \
    curl --socks5 127.0.0.1:1080 https://api.ipify.org

# Expected: VPN exit IP (not your real IP)
```

If this fails, the AWG tunnel itself is down. Check AWG logs:

```bash
docker compose --profile dns logs --tail=50 awg-client-slot-1
```

### Check AWG Tunnel

```bash
# Check if AWG interface is up
docker compose --profile dns exec awg-client-slot-1 wg show

# Check if AWG has a handshake
docker compose --profile dns exec awg-client-slot-1 wg show | grep "latest handshake"
```

If there is no recent handshake, the AWG server may be unreachable or the config may be invalid.

---

## QUIC / YouTube App Timeouts

**Symptom:** YouTube app (mobile or TV) takes 5-10 seconds to start playing, or some Google services are slow to connect initially.

### Why This Happens

QUIC is a UDP-based protocol on port 443. Because UDP ASSOCIATE through the AWG tunnel is unreliable (packets are silently lost), Proxima blocks QUIC traffic to force clients to fall back to TCP (HTTPS).

### Check the Block Rule

The QUIC block is an iptables rule in the FORWARD chain (not nftables). Check it with:

```bash
docker compose --profile dns exec dns-router \
    iptables -L FORWARD -n --line-numbers | grep "dpt:443"
```

Expected output (rule should be at or near position 1):

```
1  REJECT  udp  --  0.0.0.0/0  0.0.0.0/0  mark match 0x1/0x1 udp dpt:443 reject-with icmp-port-unreachable
```

- **REJECT** (not DROP): sends ICMP unreachable back immediately. Client falls back to TCP within 1-3 seconds.
- **DROP**: client waits for UDP timeout before trying TCP. Typical delay: 5-30 seconds.
- **Position 1 is critical**: if the rule appears deep in the chain (e.g., position 10+), LAN→tun ACCEPT rules above it will match first and proxied QUIC bypasses the block. Restart the dns-router container to re-apply the rules in the correct order.

If the rule is missing or mispositioned, restart dns-router:

```bash
docker compose --profile dns restart dns-router
```

### Expected Behavior

- First connection to a QUIC-capable service may take a few seconds while the client falls back to TCP.
- Subsequent connections are faster because the client caches the TCP preference.
- This is working as intended. Full QUIC support requires reliable UDP forwarding through the VPN tunnel.

---

## Health Check Failures

**Symptom:** Dashboard shows red status for a slot, or failover is triggered unexpectedly.

### IP Check Failures

IP checks verify the exit IP matches the expected VPN provider IP:

```bash
# Check what IP is seen through a specific slot's SOCKS5 proxy
curl -x socks5h://127.0.0.1:1081 https://api.ipify.org  # Slot 1 (AWG default)
curl -x socks5h://127.0.0.1:1082 https://api.ipify.org  # Slot 2 (AWG Russia)
curl -x socks5h://127.0.0.1:1083 https://api.ipify.org  # Slot 3 (AWG ERG-DE/FI)
```

Common causes:
- VPN provider changed the exit IP (update expected IP in config)
- VPN provider is down (check provider status page)
- IP check service (api.ipify.org) is temporarily unreachable (false positive, no failover)

### Domain Check Failures

Domain checks test if critical domains are accessible through each slot:

- Any HTTP response (even 4xx or 5xx) means the proxy is working. No failover needed.
- Only connection errors (timeout, connection refused) on DNS-resolvable domains trigger failover.
- Naked CDN domains (like `ytimg.com`, `ggpht.com`) have no DNS A record and are skipped.

### False Positives

If IP check fails but domain checks succeed, the IP check service is likely experiencing issues. Proxima is conservative about failover:

- A single IP check failure does not immediately trigger failover.
- Multiple consecutive failures are required.
- Domain check results are considered alongside IP checks.

Check the application log for details:

```bash
grep "health\|failover\|SLOT" config/proxima.log | tail -30
```

---

## Routing Loop (tun2socks)

**Symptom:** Traffic never reaches its destination. DNS resolves but connections hang. CPU usage spikes on the dns-router container.

### Root Cause

This happens when the `iif tun0 lookup main` policy routing rule is missing. Without it:

1. A packet destined for a proxied IP gets marked by nftables.
2. The fwmark rule sends it to tun0 (tun2socks).
3. tun2socks processes it and sends it back out.
4. nftables `meta mark set ct mark` in prerouting restores the mark on the return packet.
5. The fwmark rule sends the return packet back to tun0 again.
6. Infinite loop.

### Diagnosis

```bash
# Check policy routing rules
docker compose --profile dns exec dns-router ip rule list
```

Expected output should include (in this order):

```
32764:  from all iif tun0 lookup main
32765:  from all fwmark 0x1/0x1 lookup 100
```

The `iif tun0` rule MUST appear BEFORE the `fwmark` rule (lower priority number = higher priority).

### Fix

The dns-router entrypoint script should add this rule automatically. If it is missing:

```bash
# Manual fix (inside dns-router container)
ip rule add iif tun0 lookup main priority 32764
```

If this keeps happening after container restarts, check the dns-router entrypoint script for the rule creation logic.

### Additional Context

The `iif tun0 lookup main` rule ensures that response packets arriving from tun0 are routed via the main routing table (which knows about the LAN) instead of being sent back to tun0. The POSTROUTING masquerade rule (`ip saddr 192.168.0.0/16 masquerade`) SNATs client packets going to tun0, and conntrack de-SNATs the return packets. The iif rule ensures these de-SNATted packets reach the client correctly.

---

## Bypass Mode Stuck

**Symptom:** Dashboard shows "Bypass Mode" alert. All traffic goes direct (no VPN). The system is not recovering automatically.

### What Bypass Mode Means

Bypass mode activates when ALL pool configurations for a slot have been tried and failed. To maintain internet connectivity, Proxima removes dnsmasq nftset entries and flushes nftables sets, so traffic routes directly without VPN.

### Recovery Process

Proxima automatically checks for recovery every 2 minutes. To troubleshoot why recovery is not happening:

```bash
# 1. Check AWG container is running
docker compose --profile dns ps awg-client-slot-6

# 2. Check AWG logs for errors
docker compose --profile dns logs --tail=50 awg-client-slot-6

# 3. Check if AWG configs are valid
cat config/awg-slot-6.conf
# Should have [Interface] and [Peer] sections

# 4. Try manual connectivity test
docker compose --profile dns exec awg-client-slot-6 wg show
```

### Manual Recovery

1. Go to the **Dashboard** in the Proxima UI.
2. Check available configs in the slot's pool.
3. Try activating a different config manually.
4. If a config works, bypass mode will automatically deactivate.

### Common Causes

- All VPN servers in the pool are down or unreachable.
- AWG configs have expired or been revoked by the provider.
- Network connectivity issue between the server and VPN providers.
- DPI blocking is affecting the AWG connection (try a different server/port).

---

## Container Won't Start

**Symptom:** A container exits immediately or enters a restart loop.

### Crash-Looping Containers (High CPU)

If `docker stats` shows high CPU usage on `containerd` and `dockerd`, check for crash-looping containers:

```bash
# Find containers in restart loop
docker ps -a --format 'table {{.Names}}\t{{.Status}}' | grep Restarting
```

Common cause: **Shadowsocks client containers with no valid config file**. If SS slots are not configured (no `slot-N.json` exists), the SS client exits with code 255 ("Invalid config path") and Docker restarts it every ~60 seconds. Four crash-looping containers can consume ~200% CPU on containerd/dockerd combined.

**Fix:**

```bash
# Stop the crash-looping containers
docker stop ss-client-slot-1 ss-client-slot-2 ss-client-slot-3 ss-client-slot-4
```

After stopping them, verify the system load drops:

```bash
uptime  # load average should drop significantly
```

Proxima automatically stops disabled slot containers on startup. If SS slots are not in your config, they will be stopped automatically after deploy.

### General Debugging

```bash
# Check container status and exit code
docker compose ps -a

# Check container logs
docker compose logs --tail=100 CONTAINER_NAME

# Check container events
docker events --filter container=CONTAINER_NAME --since 5m
```

### AWG Client Won't Start

```bash
# Check config file exists and is valid
cat config/awg-slot-6.conf
```

The config must have both `[Interface]` and `[Peer]` sections. Common issues:
- Missing `PrivateKey` in `[Interface]`
- Missing `PublicKey` or `Endpoint` in `[Peer]`
- Invalid key format (must be base64-encoded 32-byte key)

### Shadowsocks Client Won't Start

```bash
# Check config file exists and is valid JSON
cat config/slot-1.json | python3 -m json.tool
```

Common issues:
- Invalid JSON syntax
- Missing required fields (`server`, `server_port`, `password`, `method`)
- Invalid encryption method name

### dnsmasq Won't Start

```bash
# Check for config syntax errors
docker compose --profile dns exec dnsmasq dnsmasq --test

# Check container logs for specific error
docker logs dnsmasq 2>&1 | tail -5
```

Common issues:
- Port 53 already in use
- Invalid domain syntax in generated config files
- Config file permissions
- **"Illegal repeated keyword"**: dnsmasq loads all `*.conf` files from `--conf-dir=/config/dnsmasq`. If a manually created `.conf` file (e.g., `logging.conf`) contains a directive that also exists in the base `/etc/dnsmasq.conf` (like `log-facility` or `log-queries`), dnsmasq will fail with this error. Remove any manually created config files from the `config/dnsmasq/` directory -- only Proxima-generated `proxima-*.conf` files should be there.

### Docker Socket Issues

```bash
# Check Docker socket exists and is accessible
ls -la /var/run/docker.sock

# Check Docker is running
systemctl status docker
```

---

## IPv6 Bypass

**Symptom:** Some traffic appears to bypass the VPN. Checking with tools shows the real server IP is being used for some connections.

### Root Cause

Proxima's nftsets only contain IPv4 addresses. If a client receives an AAAA (IPv6) DNS response, it may connect via IPv6, completely bypassing the nftables marking and VPN routing.

### Check Group Settings

Verify that `block_ipv6` is enabled for the affected group:

1. Go to **Groups** page in the UI.
2. Check the IPv6 blocking toggle for each group.
3. Enable it for any group where IPv6 bypass is a concern.

### Verify dnsmasq Config

When `block_ipv6` is enabled, dnsmasq should return `::` for AAAA queries:

```bash
cat /config/dnsmasq/proxima-ipv6-block.conf
# Should contain entries like:
# address=/youtube.com/::
# address=/google.com/::
```

### Important Warning

**Never use global IPv6 blocking** (`address=/#/::`). This blocks IPv6 for ALL domains, including those that require it to function properly. Services known to break with global IPv6 blocking include:

- YouTube (some CDN nodes are IPv6-only)
- ChatGPT
- Claude
- Various Google services

Always use per-group IPv6 blocking to target only the domains that need VPN routing.

---

## Wrong Tunnel / Compound Marks

**Symptom:** Traffic exits through the wrong VPN tunnel (e.g., all traffic goes through the default tunnel instead of per-group tunnels), or per-group routing doesn't work despite correct group assignments.

### Root Cause: Compound Marks

When an IP address appears in multiple group nftsets (common with CDN ranges like Google's), nftables OR-based marking accumulates bits into a compound mark (e.g., `0xF1 = video|arr|ai|proxied`). This compound mark doesn't match any per-group `ip rule`, so the traffic falls through to the default tunnel.

### Diagnosis

```bash
# Check nftables rules for first-match-wins pattern
nft list table inet proxima | grep "0xf0 == 0x00"

# Check if any static_group_* sets exist (they should NOT)
nft list sets inet proxima | grep static_group

# Check conntrack for compound marks
conntrack -L -m 0xf1 2>/dev/null | head -5
```

The nftables group marking rules should contain the condition `meta mark & 0xf0 == 0x00` (first-match-wins). If they show plain `meta mark set meta mark or 0xNN` without the condition, the config needs to be regenerated.

### Fix

1. Regenerate dns-router config from the Proxima UI (Settings → Apply DNS Config)
2. Flush conntrack to clear stale marks:
   ```bash
   sudo conntrack -F
   ```
3. Verify the new rules:
   ```bash
   nft list chain inet proxima proxima_prerouting | grep "0xf0"
   ```

### Prevention

- Never create per-group static CIDR sets (`static_group_*`). CIDRs should only go to `static_proxied`.
- Per-group identification must rely on DNS-based dynamic nftsets.
- After any nftables mark changes, always flush conntrack.

---

## Shared IP Routing (YouTube vs Gemini)

**Symptom:** Services that share IP addresses (e.g., YouTube and Gemini both resolving to Google anycast IPs) are routed through the wrong tunnel. For example, Gemini gets a Russian exit IP (geo-blocked) because YouTube's group has higher nftables priority.

### How It Works

Two mechanisms solve this problem:

1. **SNI Router (port 443):** For HTTPS traffic, the SNI router reads the TLS Server Name Indication from the ClientHello and routes each connection through the correct SOCKS5 proxy based on the domain. This provides definitive domain identification at the TCP level.

2. **DNS Arbiter (non-443 ports):** For non-HTTPS traffic, the DNS Arbiter monitors dnsmasq query logs and maintains a per-device nftables map (`device_routes`) that overrides the first-match-wins group behavior for conflicting IPs.

Additionally, a **conntrack restore** rule in the prerouting chain ensures established connections are not rerouted mid-session when the arbiter updates its map.

### Check SNI Router Status

```bash
# Verify sni-router is running
docker exec dns-router ps aux | grep sni-router

# Check SNI router PID file
docker exec dns-router cat /var/run/sni-router.pid

# Check SNI router logs
docker logs dns-router 2>&1 | grep sni-router

# Verify TPROXY iptables rule is in place
docker exec dns-router iptables -L INPUT -n | grep "0x200"

# Verify TPROXY ip rule and route
docker exec dns-router ip rule list | grep "0x200"
docker exec dns-router ip route show table 200
```

### Check Arbiter Status

```bash
# Verify arbiter is running
docker exec dns-router ps aux | grep arbiter

# Check the device_routes map (populated entries indicate active conflicts)
docker exec dns-router nft list map inet proxima device_routes

# Check domain-groups.map has entries
docker exec dns-router head -10 /config/dns-router/domain-groups.map
```

### If SNI Router Is Not Running

```bash
# Check dns-router container logs for errors
docker logs dns-router 2>&1 | grep -i "sni-router\|tproxy"

# Check if python3 is available in the container
docker exec dns-router python3 --version

# Check if sni-router.py exists
docker exec dns-router ls -la /sni-router.py

# Check if tunnels.json exists (SNI router needs it for port mapping)
docker exec dns-router cat /config/dns-router/tunnels.json
```

Common causes for SNI router not running:
- Python 3 not installed in dns-router container (rebuild needed after Dockerfile update)
- `tunnels.json` or `domain-groups.map` missing (regenerate via Settings -> Apply DNS Config)
- TPROXY ip rule not in place (restart dns-router container)
- UFW INPUT blocking TPROXY packets (missing `iptables -I INPUT -m mark --mark 0x200/0x200 -p tcp -j ACCEPT` rule)

### If Arbiter Is Not Running

```bash
# Check if domain-groups.map exists (arbiter won't start without it)
docker exec dns-router ls -la /config/dns-router/domain-groups.map

# Check if dnsmasq log file exists (arbiter needs it)
docker exec dns-router ls -la /var/log/dnsmasq/dnsmasq.log

# Check arbiter logs (it logs to stdout which goes to container logs)
docker logs dns-router 2>&1 | grep -i arbiter
```

Common causes for arbiter not running:
- `domain-groups.map` is empty (no groups configured)
- dnsmasq log file not created (dnsmasq crash or logging misconfigured)
- arbiter script error (check dns-router container logs)

### Fallback Behavior

When the SNI router is not running, HTTPS traffic falls back to the fwmark/tun2socks path using IP-level group marks and arbiter overrides. When the arbiter is also not running, the system falls back to first-match-wins group nftsets. This means the group listed first in the nftables rules (based on `nft_priority`) wins for shared IPs. To control which group wins in this fallback mode, adjust group priorities in the UI.

---

## YouTube Ads Despite VPN

**Symptom:** YouTube shows ads even though video traffic exits through a Russian IP (where YouTube is blocked and ads are not served).

### Root Cause: Ad Domain Routing Mismatch

YouTube's ad infrastructure uses domains like `doubleclick.net`, `googlesyndication.com`, and `googleadservices.com`. If these domains are in a different group (e.g., AI) than the YouTube video group, they exit through a different tunnel. YouTube detects the IP mismatch between video content and ad requests, identifies it as a VPN, and shows ads.

### Fix

Ensure YouTube ad domains are in the same group as YouTube video content:

1. Add these domains to the YouTube group's `custom_domains`:
   - `doubleclick.net`
   - `googlesyndication.com`
   - `googleadservices.com`
   - `ggpht.com`
   - `gvt1.com`
   - `gvt2.com`

2. With first-match-wins nftables rules, the YouTube group (which has a non-default slot) takes priority over other groups that might also claim these domains.

3. Flush conntrack after making changes:
   ```bash
   sudo conntrack -F
   ```

### Why Russia = No Ads

Russia officially blocks YouTube. Google does not sell ads for Russian traffic because the service is officially unavailable there. When your exit IP is Russian, YouTube serves content without ads. This only works if ALL YouTube-related traffic (video + ads) exits through the same Russian IP.

---

## Slow VPN Speed

**Symptom:** Websites load slowly through the VPN, or bandwidth is lower than expected.

### Check MSS Clamping (TCP MTU Black Hole)

**Symptom:** Some specific sites take 20+ seconds to load the first page, but subsequent loads are fast. Speed tests show good bandwidth. The problem is worse after blocking QUIC.

**Root cause:** The AWG tunnel MTU is ~1420 bytes. Without MSS clamping, TCP SYN packets advertise MSS=1460 (based on the LAN MTU). Large TCP segments with DF=1 are silently dropped when they exceed the tunnel MTU. PMTUD takes several seconds to discover the correct MTU -- causing long stalls on first connection. QUIC hides this (adaptive MTU), so the bug is only visible when QUIC is blocked.

**Check if clamping is active** (inside awg-client container):

```bash
docker compose --profile dns exec awg-client-slot-1 \
    iptables -t mangle -L POSTROUTING -n | grep TCPMSS
```

Expected output:
```
TCPMSS  tcp  --  0.0.0.0/0  0.0.0.0/0  tcp flags:0x06/0x02 TCPMSS clamp to PMTU
```

If missing, the awg-client container needs to be rebuilt and restarted with the current version of the entrypoint script. MSS clamping is automatically applied when the container starts.

---

### Check Bandwidth Limits

Proxima supports per-group bandwidth shaping via tc/HTB:

1. Go to **Groups** page and check bandwidth limits for each group.
2. Go to **Settings** page and check the total VPN bandwidth limit.
3. To test without shaping, temporarily set limits to a high value (e.g., 100 Mbps).

### Check AWG Tunnel Performance

```bash
# Check health check latency in the Dashboard
# Or test manually:
time curl -x socks5h://127.0.0.1:1081 https://api.ipify.org
```

If latency is high (>500ms), the VPN server may be overloaded or geographically distant.

### Check Server-Side Bandwidth

- VPN provider may have bandwidth caps or throttling.
- Server CPU/memory may be constrained (check with `docker stats`).
- Network interface may be saturated (check with `iftop` or `nethogs`).

### Check TCP Optimizations

For best VPN performance, both the Proxima host and VPN exit server should have TCP optimizations applied:

```bash
# Check congestion control (should be bbr)
cat /proc/sys/net/ipv4/tcp_congestion_control

# Check qdisc (should be fq)
cat /proc/sys/net/core/default_qdisc

# Check TCP Fast Open (should be 3)
cat /proc/sys/net/ipv4/tcp_fastopen
```

If these values are not optimal, apply the TCP tuning from `/etc/sysctl.d/99-proxima-tcp.conf`. See [Deployment & Operations](deployment.md) for the full configuration.

### Test Direct vs. VPN Speed

```bash
# Direct speed (no VPN)
curl -o /dev/null -w "Speed: %{speed_download}\n" https://speed.cloudflare.com/__down?bytes=10000000

# VPN speed (through SOCKS5)
curl -x socks5h://127.0.0.1:1081 -o /dev/null -w "Speed: %{speed_download}\n" https://speed.cloudflare.com/__down?bytes=10000000
```

---

## Frontend Not Loading

**Symptom:** Browser shows a blank page, connection refused, or error page when accessing the Proxima UI.

### Check Container Is Running

```bash
docker compose ps proxima
```

### Check Port Is Accessible

```bash
# From the server itself
curl -s http://localhost:5000 | head -5

# ERG uses port 5000, OFC uses port 5050
# Check the actual port mapping
docker port proxima
```

### Check Container Logs

```bash
docker compose logs --tail=50 proxima
```

Common issues:
- Flask failed to start (check for Python import errors)
- Port conflict (another service on port 5000)
- Config file parse error on startup

### Browser Issues

- Clear browser cache and hard refresh (Ctrl+Shift+R)
- Try incognito/private browsing mode
- Check browser console (F12) for JavaScript errors
- Verify the URL includes the correct port number

---

## Debug Commands Reference

A collection of useful commands for diagnosing Proxima issues. Run these on the server where Proxima is deployed.

### Container Status

```bash
# Check all container status
docker compose ps
docker compose --profile dns ps

# Resource usage
docker stats --no-stream
```

### nftables Inspection

```bash
# List all nftables sets
docker compose --profile dns exec dns-router nft list sets inet proxima

# List IPs in the proxied set
docker compose --profile dns exec dns-router nft list set inet proxima proxied

# Full nftables ruleset
docker compose --profile dns exec dns-router nft list table inet proxima

# Check QUIC block rule
docker compose --profile dns exec dns-router nft list table inet proxima | grep "udp dport 443"
```

### Policy Routing

```bash
# Check routing rules (inside dns-router)
docker compose --profile dns exec dns-router ip rule list

# Check VPN routing table
docker compose --profile dns exec dns-router ip route show table 100

# Check tun0 interface
docker compose --profile dns exec dns-router ip addr show tun0
```

### DNS Testing

```bash
# Test DNS resolution through Proxima
dig youtube.com @192.168.2.91
dig +short youtube.com @192.168.2.91

# Check dnsmasq config
cat config/dnsmasq/proxima-domains.conf | head -20

# Check upstream DNS config
cat config/dnsmasq/proxima-upstream.conf
```

### VPN Connectivity

```bash
# Test SOCKS5 proxy directly
curl --socks5 127.0.0.1:1080 https://api.ipify.org

# Test through specific slot
curl -x socks5h://127.0.0.1:1086 https://api.ipify.org

# Check AWG tunnel status
docker compose --profile dns exec awg-client-slot-6 wg show
```

### Config Files

```bash
# Check nftables config
cat config/dns-router/proxima.nft

# Check dnsmasq domain config
cat config/dnsmasq/proxima-domains.conf

# Check dnsmasq IPv6 block config
cat config/dnsmasq/proxima-ipv6-block.conf

# Validate main config JSON
python3 -m json.tool config/proxima-config.json > /dev/null && echo "Valid JSON" || echo "Invalid JSON"
```

### SNI Router

```bash
# Check SNI router is running
docker compose --profile dns exec dns-router ps aux | grep sni-router

# Check SNI router PID
docker compose --profile dns exec dns-router cat /var/run/sni-router.pid

# Check SNI router logs (connection traces)
docker compose --profile dns logs dns-router 2>&1 | grep sni-router | tail -20

# Check TPROXY iptables INPUT rule
docker compose --profile dns exec dns-router iptables -L INPUT -n | grep 0x200

# Check TPROXY routing (ip rule + route table 200)
docker compose --profile dns exec dns-router ip rule list | grep 0x200
docker compose --profile dns exec dns-router ip route show table 200

# Check tunnels.json (SOCKS5 port mapping for SNI router)
docker compose --profile dns exec dns-router cat /config/dns-router/tunnels.json
```

### DNS Arbiter

```bash
# Check arbiter is running
docker compose --profile dns exec dns-router ps aux | grep arbiter

# Check device_routes map
docker compose --profile dns exec dns-router nft list map inet proxima device_routes

# Check domain-groups.map
docker compose --profile dns exec dns-router head -20 /config/dns-router/domain-groups.map

# Check dnsmasq query log (recent entries)
docker compose --profile dns exec dns-router tail -20 /var/log/dnsmasq/dnsmasq.log
```

### Logs

```bash
# Proxima application log
tail -100 config/proxima.log

# Search for errors
grep -i "error\|fail\|exception" config/proxima.log | tail -20

# Search for specific slot activity
grep "\[SLOT-6\]" config/proxima.log | tail -20

# Search for failover events
grep -i "failover\|bypass" config/proxima.log | tail -20
```

---

## Tunnel Chaining Issues

### Chained Slot Shows No Exit IP

If a slot with `via_slot` set shows no exit IP:

1. **Check parent slot health** — The parent must be healthy first: `curl http://localhost:5050/api/slots`
2. **Verify dns-router is running** — `docker ps | grep dns-router`
3. **Check tunnels.json** — `cat config/dns-router/tunnels.json | jq .` — the chained slot should have `via_slot`, `via_table`, `via_device`, and `container_ip` fields
4. **Verify container IP resolution** — The child container must be on `vpn_net`: `docker network inspect vpn_net`

### Chained Traffic Not Routing

1. **Check nftables FORWARD rules** — `sudo nft list chain inet proxima forward` should show ACCEPT rules for the child container IP and TUN devices
2. **Check raw PREROUTING bypass** — `sudo nft list chain ip raw PREROUTING` should show NOTRACK rules that bypass Docker's conntrack for chained traffic
3. **Verify routing tables** — `ip rule show` should show rules for both parent and child slot marks pointing to their respective routing tables

### Docker Raw PREROUTING Issue

Docker versions that use raw table PREROUTING rules can interfere with tunnel chaining. The dns-router `entrypoint.sh` and `reload.sh` scripts automatically add NOTRACK rules to bypass Docker's raw PREROUTING for traffic between container IPs and TUN interfaces. If chaining stops working after a Docker update, check:

```bash
# Inside dns-router (or from host since it's host network)
nft list chain ip raw PREROUTING
```

The rules should include entries like:
```
ip saddr CONTAINER_IP notrack
ip daddr CONTAINER_IP notrack
```
