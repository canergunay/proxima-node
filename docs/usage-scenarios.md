# Usage Scenarios

Day-to-day operational procedures for proxima-node infrastructure.

## Prerequisites

- Ansible installed on the control machine (ERG server at `/opt/proxima-node`)
- `inventory/host_vars/<hostname>.yml` populated for all target servers
- SSH key access to all servers (established during initial provisioning)

---

## 1. Provision a New VPN Exit Server

A new VPS is purchased and needs to be set up as a Proxima VPN exit node.

```bash
# 1. Add server to inventory
vi inventory/hosts.yml                    # Add under vpn_exit group
cp inventory/host_vars/erg-pl.yml.example inventory/host_vars/erg-new.yml
vi inventory/host_vars/erg-new.yml        # Fill in real credentials

# 2. Generate secrets
openssl rand -base64 24   # ss_password
openssl rand -base64 36   # ssconf_token, speedtest_api_key, agent_api_key

# 3. Run provisioning (first time — password auth)
ansible-playbook playbooks/setup-vpn-exit.yml -l erg-new --ask-pass

# 4. Verify
ansible-playbook playbooks/health-check.yml -l erg-new

# 5. Get SS key for Proxima registration
curl -sk -H "X-API-Key: <key>" https://<ip>:5051/api/ss-key | jq
```

**What gets installed:** system hardening, SSH key injection, UFW, Docker,
outline-ss-server, ssconf, speedtest, proxima-agent.

**What to do next:** Install AWG/Xray via AmneziaVPN app (optional),
register the server's SS key in Proxima.

---

## 2. Provision a New DPI Bypass Server

A local machine (e.g., Raspberry Pi) needs DPI bypass capabilities.

```bash
# 1. Add to inventory under dpi_bypass group
vi inventory/hosts.yml
cp inventory/host_vars/erg-ru.yml.example inventory/host_vars/new-dpi.yml
vi inventory/host_vars/new-dpi.yml

# 2. Run provisioning
ansible-playbook playbooks/setup-dpi-bypass.yml -l new-dpi --ask-pass

# 3. Verify
ansible-playbook playbooks/health-check.yml -l new-dpi
```

**What gets installed:** system hardening, SSH key injection, UFW,
shadowsocks-libev, zapret-nfqws2, watchdog timer, proxima-agent.

---

## 3. Check Server Health

Run periodically or after suspected issues.

```bash
# All servers
ansible-playbook playbooks/health-check.yml

# Single server
ansible-playbook playbooks/health-check.yml -l erg-pl

# Quick manual check (no Ansible)
curl -sk https://<ip>:5051/health | jq
curl -sk -H "X-API-Key: <key>" https://<ip>:5051/api/status | jq
```

**Checks performed:** agent reachable, services running, disk usage < 90%,
memory usage < 90%, public IP reachable.

---

## 4. Rotate Credentials

Recommended monthly. Generates new SS password, API keys, and tokens.

```bash
# Single server
ansible-playbook playbooks/rotate-credentials.yml -l erg-pl

# All VPN exit servers
ansible-playbook playbooks/rotate-credentials.yml -l vpn_exit
```

**Output:** New credentials are printed in the Ansible output. Copy them
to update the corresponding Proxima tunnel_config entries.

**Important:** After rotation, update the SS key/password in every Proxima
instance that uses this server (ERG, OFC, etc.).

---

## 5. Update the Agent

Deploy the latest `agent.py` to all servers without reprovisioning.

```bash
# All servers
ansible-playbook playbooks/update-agent.yml

# Single server
ansible-playbook playbooks/update-agent.yml -l erg-de
```

**What happens:** Copies new `agent.py`, updates Python venv, restarts
`proxima-agent` systemd service, verifies `/health` responds.

---

## 6. Migrate from zapret-agent to proxima-agent

For servers still running the old zapret-agent on port 5050.

```bash
ansible-playbook playbooks/migrate-agent.yml -l erg-tr
```

**What happens:**
1. Deploys proxima-agent on port 5051 (new service)
2. Verifies the new agent responds
3. Stops and disables the old `zapret-agent` service
4. Removes old agent files from `/opt/zapret-agent/`

**Rollback:** If the new agent fails health check, the old agent is left
running. Fix the issue and re-run the playbook.

---

## 7. Handle a Blocked IP

When an exit server's IP gets blocked by censors:

```bash
# 1. Get a new VPS with a clean IP
# 2. Provision it
ansible-playbook playbooks/setup-vpn-exit.yml -l erg-new --ask-pass

# 3. Decommission the old server
ansible-playbook playbooks/decommission.yml -l erg-old

# 4. Update Proxima tunnel_config with new IP + credentials
# 5. Remove old server from inventory
vi inventory/hosts.yml
rm inventory/host_vars/erg-old.yml
```

---

## 8. Decommission a Server

Safely shut down and clean up a server that's no longer needed.

```bash
ansible-playbook playbooks/decommission.yml -l erg-old
```

**What happens:** Stops all Proxima services, removes systemd units,
cleans config directories. Prompts for hostname confirmation as safety check.

**After decommission:**
- Remove from `inventory/hosts.yml`
- Delete `inventory/host_vars/<hostname>.yml`
- Remove the server's keys from all Proxima instances
- Cancel the VPS if applicable

---

## 9. Bring Existing Servers to Standard

For servers set up manually (before Ansible) that need standardization.

```bash
# Dry run first (no changes)
ansible-playbook playbooks/setup-vpn-exit.yml -l erg-tr --check

# Apply (idempotent — safe to run on existing servers)
ansible-playbook playbooks/setup-vpn-exit.yml -l erg-tr
```

All roles are idempotent: running them on an already-configured server
will only update what's changed (configs, binaries, etc.).

---

## 10. Full Site Deployment

Provision or update all servers at once.

```bash
# All servers (VPN exit + DPI bypass)
ansible-playbook playbooks/site.yml

# Only VPN exit servers
ansible-playbook playbooks/setup-vpn-exit.yml

# Only DPI bypass servers
ansible-playbook playbooks/setup-dpi-bypass.yml
```

---

## Common One-Liners

```bash
# Check agent version on all servers
ansible all -m uri -a "url=https://localhost:5051/health validate_certs=no return_content=yes"

# Restart outline-ss on a specific server
curl -sk -X POST -H "X-API-Key: <key>" \
  -d '{"services":["outline-ss"]}' \
  https://<ip>:5051/api/restart

# Get current DPI args (DPI bypass node)
curl -sk -H "X-API-Key: <key>" https://192.168.2.92:5051/api/dpi-args | jq

# Update DPI args
curl -sk -X PUT -H "X-API-Key: <key>" \
  -d '{"dpi_args":"--dpi-desync=fake,split2 --dpi-desync-ttl=3"}' \
  https://192.168.2.92:5051/api/dpi-args

# Run blockcheck (DPI bypass node)
curl -sk -X POST -H "X-API-Key: <key>" \
  -d '{"domain":"youtube.com","strategies":["--dpi-desync=fake --dpi-desync-ttl=3"]}' \
  https://192.168.2.92:5051/api/blockcheck/start
```
