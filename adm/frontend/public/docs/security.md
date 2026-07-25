# Security

## Overview

Proxima is a self-hosted proxy and VPN management system that runs on trusted LAN servers. It manages sensitive VPN credentials, controls DNS resolution for connected devices, and routes traffic through encrypted tunnels. While Proxima is not exposed to the public internet, it handles critical security functions and must be configured and maintained carefully.

This document covers authentication, network security, VPN and DNS security, DPI bypass strategies, configuration protection, Docker security considerations, IPv6 leak prevention, and audit logging.

---

## Authentication

### JWT Token Authentication

Proxima uses JSON Web Tokens (JWT) for API authentication:

- All API endpoints under `/api/` require a valid JWT token in the `Authorization` header.
- Tokens are issued upon successful login and expire after a configurable period.
- Token expiration is checked on every API request.
- Expired tokens are rejected with a 401 status code, requiring the user to re-authenticate.

### Password Security

- Passwords are hashed using **bcrypt** with an automatically generated salt.
- Plaintext passwords are never stored anywhere in the system.
- The admin account is created during first-run setup.
- Password changes require the current password for verification.

### Admin Account

- A single admin account is created when Proxima is first started.
- The initial password is set during setup via the UI.
- There is no password recovery mechanism. If the password is lost, it must be reset by editing `proxima-config.json` directly and restarting the container.

### Per-User Device Authentication

Proxima supports per-user authentication for device-level VPN control:

- Users log in through the Proxima web interface (PWA).
- Upon authentication, the user's device IP is added to an nftables set that enables VPN routing for that device.
- Device identification uses a combination of username, DHCP hostname, IP address, and session token.
- MAC address-based identification is intentionally not used because iOS and Android randomize MAC addresses.
- The network default is **direct internet** (no VPN). Only authenticated devices get VPN routing.

### VPN User Authentication

The VPN user system adds a second authentication layer for ProximaVPN peers:

- **Login rate limiting** — The `/api/vpn/users/<id>/login` endpoint is rate-limited to prevent brute force attacks
- **Password storage** — User passwords are hashed with bcrypt. An optional encrypted copy (using JWT secret as key) allows password display in the admin UI
- **JWT tokens** — VPN user login returns a JWT token for subsequent API calls from the ProximaVPN client app
- **Device registration** — On login, the user's device IP is registered in nftables auth sets, granting VPN routing access
- **Per-user routing** — Users can be restricted to specific domain groups (`routing_mode: "selected"` with `assigned_groups`), enforced at the nftables level via per-group auth sets
- **Bandwidth quotas** — Monthly data limits and speed caps (upload/download) are configurable per user
- **Account disable** — Disabled users have all device registrations removed, immediately revoking VPN routing access

---

## Network Security

### LAN-Only Access

Proxima is designed to run on a trusted local area network and is **not exposed to the public internet**:

- The web UI and API are accessible only from the LAN.
- No port forwarding or reverse proxy is configured to expose Proxima externally.
- Firewall rules on the server should restrict access to the LAN subnet only.

### Proxy Gateway

The proxy gateway (`proxima:8080`) provides a stable HTTP proxy endpoint for Docker containers on the same network:

- The proxy gateway has **no authentication**. This is an intentional design choice because it serves only LAN containers.
- If the server is accessible from untrusted networks, the proxy gateway port should be restricted via firewall rules.

### ProximaVPN LAN Access Enforcement

ProximaVPN peers can be granted or denied access to the local network via a per-peer LAN Access toggle. When LAN access is disabled for a peer, iptables FORWARD DROP rules block traffic from the peer's WG IP to all configured LAN subnets.

- **Multi-subnet support:** The `lan_subnets` setting in `proxima-config.json` lists all LAN CIDRs to block (e.g., `["192.168.2.0/24", "192.168.1.0/24"]`). Without this setting, only a single `/24` derived from `server_ip` is blocked -- which may leave other reachable subnets exposed.
- **Server-side enforcement:** DROP rules are applied regardless of the client's `AllowedIPs` configuration. Even if a client modifies their config to include LAN ranges, the server blocks the traffic.
- **Rule cleanup:** When subnets are added or removed from the configuration, stale rules are automatically cleaned up and new rules applied for all affected peers.

### API Authentication Scope

- **Authenticated endpoints:** All `/api/*` routes require a valid JWT token.
- **Unauthenticated endpoints:** Static files (frontend assets) and documentation files are accessible without authentication.

### Docker Socket

- The Docker socket (`/var/run/docker.sock`) is mounted read-write into the Proxima container.
- This is **required** for container management (restarting SS/AWG clients, checking container status).
- If the Proxima container is compromised, Docker socket access provides **root-level access** to the host.
- Mitigation: the server is LAN-only, and SSH access is restricted.

---

## VPN Security

### AmneziaWG (AWG)

AmneziaWG is a modified WireGuard implementation with anti-DPI (Deep Packet Inspection) obfuscation:

- Standard WireGuard has a recognizable handshake pattern that DPI systems can detect and block.
- AWG adds random padding and modified headers to the WireGuard protocol, making it indistinguishable from random UDP traffic.
- This is essential for deployments in Turkey and Russia, where both countries actively identify and block WireGuard and OpenVPN traffic.

### Shadowsocks (SS)

Shadowsocks is an encrypted proxy protocol:

- Traffic is encrypted using AEAD ciphers (e.g., `chacha20-ietf-poly1305`, `aes-256-gcm`).
- The encrypted stream appears as random data to DPI systems, making it harder to detect than pattern-based VPN protocols.
- Shadowsocks uses a pre-shared key model (no public key exchange), so there is no recognizable handshake.

### VPN DNS Considerations

- When using `socks5h://` proxy URLs, DNS resolution happens **inside** the VPN tunnel. This prevents DNS leaks but means the VPN provider's DNS is used.
- Some VPN providers hijack DNS queries and return incorrect IPs. For AWG health checks, Proxima uses `socks5://` (local DNS resolution) to avoid this issue.
- For regular Shadowsocks slots, `socks5h://` is used to prevent DNS leaks.

---

## DNS Security

### DoH Canary Domain

Modern browsers attempt to use DNS-over-HTTPS (DoH) to encrypt DNS queries. While this is generally a privacy improvement, it bypasses dnsmasq entirely, which means:

- Domain queries would go directly to Cloudflare, Google, or another DoH provider.
- dnsmasq would never see the query, so it cannot add the resolved IP to nftables sets.
- The traffic would not be routed through the VPN.

Proxima addresses this by serving the **DoH canary domain** (`use-application-dns.net`) through dnsmasq. When browsers query this domain and receive a negative response, they automatically disable DoH and fall back to standard DNS. This ensures all DNS queries go through dnsmasq.

### DNS as the Routing Trigger

In DNS Mode, the entire routing mechanism depends on DNS resolution through dnsmasq:

1. Client queries a domain (e.g., `youtube.com`).
2. dnsmasq resolves the domain and adds the resulting IP(s) to an nftables set.
3. nftables marks packets destined for IPs in the set.
4. Policy routing sends marked packets to the tun0 interface (tun2socks).
5. tun2socks forwards traffic through the VPN tunnel.

If DNS resolution bypasses dnsmasq (via DoH, hardcoded DNS, or IPv6), the entire routing chain breaks and traffic goes direct.

### IPv6 DNS Blocking

nftables sets in Proxima only handle IPv4 addresses. If a client receives an AAAA (IPv6) DNS response, it may connect via IPv6, completely bypassing VPN routing. Per-group `block_ipv6` settings force dnsmasq to return `::` for AAAA queries on proxied domains, ensuring clients use IPv4.

See the [IPv6 Leak Prevention](#ipv6-leak-prevention) section for details.

---

## DPI Bypass Strategies

Proxima is designed to operate in countries with active DPI (Deep Packet Inspection) and internet censorship, specifically Turkey and Russia.

### AmneziaWG Obfuscation

- Modifies WireGuard packet headers to evade signature-based DPI.
- Adds junk packets and randomized padding.
- The handshake looks like random UDP traffic rather than WireGuard.
- Effective against both Turkish and Russian DPI systems.

### Domestic Hop (ProximaVPN)

For Russian mobile networks (LTE), where even AWG may be blocked:

- Phone connects via standard WireGuard to the ERG server in Moscow.
- This is a **domestic** connection (Moscow to Moscow) and is not inspected by Russian DPI.
- ERG then routes traffic through DNS Mode to the actual VPN exit.
- The ISP sees only domestic WireGuard traffic, which is not blocked.

### Shadowsocks

- Encrypted stream protocol with no recognizable handshake or header.
- Traffic looks like random TCP data to DPI systems.
- Multiple encryption methods available for flexibility.

### QUIC Blocking

- QUIC (UDP port 443) is blocked at the nftables level with REJECT rules.
- This forces clients to use TCP-based HTTPS, which can be reliably tunneled.
- UDP forwarding through the VPN tunnel is unreliable (packets are silently lost in some configurations).
- REJECT (not DROP) is used to send ICMP unreachable, causing faster client fallback to TCP.

---

## Config Security

### proxima-config.json

This file is the single source of truth for all Proxima configuration and contains sensitive data:

- VPN server credentials (keys, passwords, endpoints)
- JWT secret for API authentication
- bcrypt password hashes for user accounts
- Slot configurations with VPN provider details

### Protection Measures

```bash
# Restrict file permissions
chmod 600 config/proxima-config.json
chown root:root config/proxima-config.json
```

- The file should be readable only by the root user and the Docker process.
- Never commit this file to version control (it is gitignored).
- Always back up this file securely. If it contains VPN credentials, treat backups with the same sensitivity.

### JWT Secret

- The JWT secret is auto-generated on first run and stored in `proxima-config.json`.
- If the secret is changed, all existing tokens are invalidated and users must re-authenticate.
- The secret should be a long random string. The auto-generated default is secure.

### Password Hashes

- User passwords are stored as bcrypt hashes with auto-generated salts.
- bcrypt is intentionally slow to compute, making brute-force attacks impractical.
- Even if `proxima-config.json` is exposed, password recovery from bcrypt hashes is computationally infeasible.

---

## Docker Security

### Docker Socket Exposure

The Proxima container requires read-write access to the Docker socket for container management:

```yaml
volumes:
  - /var/run/docker.sock:/var/run/docker.sock
```

**Risk:** Docker socket access is equivalent to root access on the host. A compromised Proxima container could:
- Start/stop any container on the host
- Mount host filesystems
- Execute commands as root on the host

**Mitigations:**
- Proxima is LAN-only and not exposed to the internet.
- SSH access to the server is restricted.
- The web UI requires JWT authentication.
- Firewall rules limit access to trusted LAN subnets.

### Host Network Mode

The `dnsmasq` and `dns-router` containers run with host network mode:

```yaml
network_mode: host
```

This is required because:
- dnsmasq must bind to port 53 on the host.
- dns-router must manage host nftables rules and create the tun0 interface.
- Policy routing rules must apply to the host network namespace.

**Risk:** Host network mode gives containers full access to the host's network stack.

**Mitigations:**
- These containers run specific, well-understood software (dnsmasq, nftables, tun2socks).
- Container images are built from the project's own Dockerfiles, not arbitrary third-party images.
- Containers use `restart: unless-stopped` for automatic recovery.

### Container Isolation

- SS client containers run in isolated Docker networks.
- Each SS client gets its own container with a dedicated SOCKS5 port.

---

## IPv6 Leak Prevention

### The Problem

Proxima's nftables sets only contain IPv4 addresses. When a client device receives both A (IPv4) and AAAA (IPv6) DNS responses, it may prefer the IPv6 address (per RFC 6724 "Happy Eyeballs"). This IPv6 connection bypasses the nftables marking entirely, and the traffic goes direct without VPN.

### The Solution

Per-group `block_ipv6` toggle in dnsmasq configuration:

- When enabled, dnsmasq returns `::` (unroutable address) for all AAAA queries on domains in that group.
- Clients see no usable IPv6 address and fall back to IPv4.
- IPv4 traffic is intercepted by nftables and routed through the VPN.

### Configuration

IPv6 blocking is controlled per group in the Proxima UI:

1. Go to the **Groups** page.
2. Each group has a `block_ipv6` toggle (enabled by default).
3. When enabled, a dnsmasq config file is generated with `address=/domain/::` entries.

### Critical Warning

**Never use global IPv6 blocking** (`address=/#/::`).

Global IPv6 blocking returns `::` for ALL domains, not just proxied ones. This breaks services that rely on IPv6 for certain functionality:

- YouTube (some CDN edges are IPv6-only in certain regions)
- ChatGPT / OpenAI services
- Claude / Anthropic services
- Various Google services
- Content delivery networks that use IPv6 for load balancing

Always use per-group IPv6 blocking to target only the specific domains that need VPN routing.

---

## Audit Logging

### DNS Query Logging

dnsmasq can log all DNS queries it processes:

- Logs show which domains are being queried by which client IP.
- Useful for debugging (why is a domain not being routed?) and auditing (what is a device accessing?).
- Logs are stored in the dnsmasq container output (accessible via `docker compose logs dnsmasq`).

### User-to-IP Mapping

When per-user authentication is enabled:

- Each login creates a record mapping the username to the device IP address.
- Session tokens track which devices are currently authenticated.
- This mapping enables audit trails showing which user accessed which domains.

### Application Logs

Proxima logs record operational events:

- **Slot activations:** Which VPN config was activated and when.
- **Failover events:** Which slot failed, what the failure was, and what action was taken.
- **Config changes:** Domain additions/removals, group changes, settings updates.
- **Health check results:** IP check and domain check outcomes per slot.

Log location: `config/proxima.log` (7-day rotation via `TimedRotatingFileHandler`).

### Performance Database

The SQLite database (`config/proxima.db`) stores:

- Key success rates over time
- Health check history
- Failover event records

This data is retained indefinitely (no automatic cleanup) and is visualized in the Performances page.

### Recommended Retention Policy

- **Application logs:** 7 days (automatic rotation).
- **DNS query logs:** 90 days for audit compliance (if per-user auth is enabled).
- **Performance database:** Indefinite (SQLite file size is manageable for typical usage).
- **Config backups:** Keep at least 30 days of daily backups.

---

## Best Practices

### Server Hardening

- **Keep the OS updated:** Apply security patches regularly. Both Ubuntu/Debian and Docker should be kept current.
- **Restrict SSH access:** Use key-based authentication. Disable password auth if possible. Limit SSH to specific IPs using `ufw` or `iptables`.
- **Enable a firewall:** Use `ufw` to allow only necessary ports (53 for DNS, 5000/5050 for Proxima, 22 for SSH).
- **Disable unused services:** Minimize the attack surface on the server.

### Proxima Configuration

- **Use a strong admin password:** The admin account controls VPN routing for all devices on the network.
- **Back up proxima-config.json regularly:** This file contains all VPN credentials and cannot be reconstructed without the original provider keys.
- **Restrict config file permissions:** `chmod 600 config/proxima-config.json`.
- **Monitor health checks:** Unexpected changes in exit IP may indicate VPN provider compromise or man-in-the-middle attacks.

### Device Management

- **Review authenticated devices periodically:** Check which devices are currently authorized for VPN routing.
- **Revoke stale sessions:** Remove devices that are no longer active or recognized.
- **Use per-user groups:** Assign appropriate routing policies (full VPN vs. selected domains) based on user needs.
- **Audit DNS logs:** Periodically review DNS query logs for unexpected patterns.

### Operational Security

- **Do not expose Proxima to the internet:** It is designed for LAN-only operation and lacks the hardening needed for public exposure.
- **Do not share VPN credentials:** Each slot's credentials should be unique. If a key is compromised, rotate it immediately.
- **Monitor for bypass mode:** Bypass mode means VPN routing is down and all traffic is going direct. Investigate and resolve promptly.
- **Test after updates:** After deploying a new version, verify that VPN routing is working correctly by checking the exit IP through the Dashboard.
- **Keep VPN provider configs current:** AWG and SS configs may expire or be revoked. Maintain a pool of backup configurations for failover.

### Incident Response

If you suspect the server has been compromised:

1. **Disconnect** the server from the network immediately.
2. **Check Docker containers** for unexpected images or containers.
3. **Review** `proxima-config.json` for unauthorized changes.
4. **Check** system logs (`/var/log/auth.log`, `journalctl`) for unauthorized access.
5. **Rotate** all VPN credentials (AWG keys, SS passwords).
6. **Regenerate** the JWT secret (invalidates all sessions).
7. **Change** the admin password.
8. **Rebuild** Docker images from trusted source (git repository).
