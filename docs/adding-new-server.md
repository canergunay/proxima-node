# Adding a New Server

Step-by-step guide for provisioning a new Proxima server node.

## Prerequisites

- Fresh Debian 12+ VPS with root SSH access
- Ansible installed on the control machine (ERG server)
- This repo cloned on the control machine

## Step 1: Get a VPS

Choose a provider with:
- Debian 12 or Ubuntu 22+ (Debian 12 preferred)
- At least 1 GB RAM, 10 GB disk
- Root SSH access (password OK for initial connect)
- Clean IP (not on blocklists)

See [provider-notes.md](provider-notes.md) for recommendations.

## Step 2: Add to Inventory

### `inventory/hosts.yml`

Add the server under the appropriate group:

```yaml
# For a VPN exit node:
vpn_exit:
  hosts:
    erg-new:
      ansible_host: 1.2.3.4
      server_location: US
      server_provider: ProviderName

# For a DPI bypass node:
dpi_bypass:
  hosts:
    erg-new:
      ansible_host: 192.168.1.100
      server_location: RU-LAN
      server_provider: local
```

### `inventory/host_vars/<hostname>.yml`

Copy the example and fill in real values:

```bash
cp inventory/host_vars/erg-pl.yml.example inventory/host_vars/erg-new.yml
```

Generate secrets:
```bash
# SS password (32 chars)
openssl rand -base64 24

# API keys and tokens (48 chars)
openssl rand -base64 36
```

Fill in:
```yaml
server_ip: "1.2.3.4"
node_id: "proxima-node-new"
ss_password: "<generated>"
ssconf_token: "<generated>"       # VPN exit only
speedtest_api_key: "<generated>"  # VPN exit only
agent_api_key: "<generated>"
install_adguard: false
```

## Step 3: Run the Playbook

```bash
# First connection (password auth):
ansible-playbook playbooks/setup-vpn-exit.yml -l erg-new --ask-pass

# Subsequent runs (key auth):
ansible-playbook playbooks/setup-vpn-exit.yml -l erg-new
```

For DPI bypass nodes:
```bash
ansible-playbook playbooks/setup-dpi-bypass.yml -l erg-new --ask-pass
```

The playbook will:
1. Harden the system (sysctl, SSH key injection, UFW)
2. Install and configure all components
3. Start all services
4. Display a summary with URLs and credentials

## Step 4: Install AWG/Xray (Optional, VPN Exit Only)

Use the [AmneziaVPN](https://amnezia.org) client app to add:
- AmneziaWG (port 80/udp)
- Xray VLESS (port 443/tcp)

These are managed by AmneziaVPN, not by Ansible.

## Step 5: Register in Proxima

Add the server's credentials to your Proxima instance:
1. Add a new key in Proxima with the SS credentials
2. Assign to a slot
3. Verify connectivity via the Dashboard

## Verification

After setup, verify the server is healthy:

```bash
# Check all services from the control machine:
ansible-playbook playbooks/health-check.yml -l erg-new

# Or check the agent directly:
curl -sk https://1.2.3.4:5051/health
curl -sk -H "X-API-Key: <key>" https://1.2.3.4:5051/api/status | jq
```
