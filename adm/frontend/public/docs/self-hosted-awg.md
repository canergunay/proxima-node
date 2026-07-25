# Self-Hosted AmneziaWG Server

Deploy your own AmneziaWG (obfuscated WireGuard) exit node on any Linux VPS and add it to Proxima in under 10 minutes.

## What is AmneziaWG

AmneziaWG (AWG) is WireGuard with traffic obfuscation. Standard WireGuard packets are detectable by DPI; AWG adds junk packets and scrambles the handshake headers, making VPN traffic undetectable. This is essential for Russia and other countries that block WireGuard by protocol fingerprint.

The obfuscation is controlled by server-side parameters (Jc, Jmin, Jmax, S1, S2, H1–H4) that must match between client and server.

---

## Architecture

```
[Client device]
    ↓  awg-client-slot-N container (AmneziaWG client)
    ↓  obfuscated UDP traffic
[VPS: ERG-DE / ERG-FI]
    ↓  amnezia-awg2 Docker container (AmneziaWG server)
    ↓  outbound internet
```

The AWG server runs in Docker with `NET_ADMIN` + `SYS_MODULE` capabilities and the host's `/lib/modules` mounted. The server config and all peer (client) keys live inside the container at `/opt/amnezia/awg/awg0.conf`.

---

## Setup Method: Amnezia Desktop Client (Recommended)

The Amnezia client automates server provisioning via SSH — it installs Docker, builds the container, and generates client configs. **This is the approach used for ERG-DE and ERG-FI.**

### Steps

1. **Install Amnezia client** on your local machine from [amnezia.org](https://amnezia.org)

2. **Add a new server**: Click `+` → "Your own server" → enter SSH credentials (host, root password or key)

3. **Choose protocol**: Select AmneziaWG

4. **Wait for provisioning**: Amnezia installs Docker on the VPS, pulls `amneziavpn/amneziawg-go`, generates random obfuscation parameters, and starts the container. Takes ~2 minutes.

5. **Share / export the config**: In Amnezia client → your server → "Share" → "Export config as file" → save the `.conf` file

6. **Add to Proxima**: Proxima → **Keys** → **AWG Configs** → paste the contents of the `.conf` file → Save

That's it. The `.conf` file is a standard AmneziaWG client config with the obfuscation parameters embedded.

---

## Manual Peer Management (No Amnezia Client)

Once the server is running (set up via Amnezia client), add new peers manually without reinstalling anything.

### Check current peers

```bash
docker exec amnezia-awg2 awg show
```

### Add a new peer

Run this on the VPS (as root). Replace `10.8.1.X` with the next available IP in the subnet.

```bash
# Generate keypair for the new peer
PRIVKEY=$(docker exec amnezia-awg2 awg genkey)
PUBKEY=$(echo "$PRIVKEY" | docker exec -i amnezia-awg2 awg pubkey)
PSK=$(docker exec amnezia-awg2 awg genpsk)
PEER_IP="10.8.1.X"   # e.g. 10.8.1.6

# Read server obfuscation params
SERVER_PUBKEY=$(docker exec amnezia-awg2 awg show awg0 public-key)
SERVER_IP="YOUR_VPS_IP"
SERVER_PORT="80"   # or 443 on ERG-FI

# Add peer to running interface (live, no restart)
docker exec amnezia-awg2 awg set awg0 \
  peer "$PUBKEY" \
  preshared-key <(echo "$PSK") \
  allowed-ips "$PEER_IP/32"

# Persist to config file
docker exec amnezia-awg2 /bin/sh -c "cat >> /opt/amnezia/awg/awg0.conf << EOF

[Peer]
PublicKey = $PUBKEY
PresharedKey = $PSK
AllowedIPs = $PEER_IP/32
EOF"
```

### Generate client config

Read the obfuscation parameters from the server config, then build the client `.conf`:

```bash
# Read server params
SERVER_CONF=$(docker exec amnezia-awg2 cat /opt/amnezia/awg/awg0.conf)
JC=$(echo "$SERVER_CONF" | grep '^Jc' | awk '{print $3}')
JMIN=$(echo "$SERVER_CONF" | grep '^Jmin' | awk '{print $3}')
JMAX=$(echo "$SERVER_CONF" | grep '^Jmax' | awk '{print $3}')
S1=$(echo "$SERVER_CONF" | grep '^S1' | awk '{print $3}')
S2=$(echo "$SERVER_CONF" | grep '^S2' | awk '{print $3}')
H1=$(echo "$SERVER_CONF" | grep '^H1' | awk '{print $3}' | cut -d'-' -f1)
H2=$(echo "$SERVER_CONF" | grep '^H2' | awk '{print $3}' | cut -d'-' -f1)
H3=$(echo "$SERVER_CONF" | grep '^H3' | awk '{print $3}' | cut -d'-' -f1)
H4=$(echo "$SERVER_CONF" | grep '^H4' | awk '{print $3}' | cut -d'-' -f1)

cat > /tmp/new-peer.conf << EOF
[Interface]
PrivateKey = $PRIVKEY
Address = $PEER_IP/32
DNS = 1.1.1.1
Jc = $JC
Jmin = $JMIN
Jmax = $JMAX
S1 = $S1
S2 = $S2
H1 = $H1
H2 = $H2
H3 = $H3
H4 = $H4

[Peer]
PublicKey = $SERVER_PUBKEY
PresharedKey = $PSK
Endpoint = $SERVER_IP:$SERVER_PORT
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = 25
EOF

cat /tmp/new-peer.conf
```

Copy the output and paste it into Proxima → **Keys** → **AWG Configs**.

---

## Manual Server Setup (No Amnezia Client)

Use this if you can't or don't want to use the Amnezia desktop client.

### 1. Prepare the VPS

```bash
# Debian 12 — install Docker
curl -fsSL https://get.docker.com | sh
```

### 2. Generate server keys and obfuscation params

```bash
# Pull the image and generate keys inside it
docker run --rm amneziavpn/amneziawg-go:latest awg genkey | tee /tmp/server-private.key | \
  docker run --rm -i amneziavpn/amneziawg-go:latest awg pubkey > /tmp/server-pub.key

SERVER_PRIVKEY=$(cat /tmp/server-private.key)
SERVER_PUBKEY=$(cat /tmp/server-pub.key)

# Generate random obfuscation parameters
JC=$((RANDOM % 6 + 3))        # 3-8
JMIN=10
JMAX=50
S1=$((RANDOM % 150 + 50))     # 50-199
S2=$((RANDOM % 150 + 50))
H1=$((RANDOM * RANDOM % 2000000000 + 1))
H2=$((RANDOM * RANDOM % 2000000000 + 1))
H3=$((RANDOM * RANDOM % 2000000000 + 1))
H4=$((RANDOM * RANDOM % 2000000000 + 1))
```

### 3. Create server config and start script

```bash
AWG_PORT=80   # use 443 if 80 is taken

mkdir -p /opt/amnezia/amnezia-awg2

cat > /opt/amnezia/amnezia-awg2/awg0.conf << EOF
[Interface]
PrivateKey = $SERVER_PRIVKEY
Address = 10.8.1.0/24
ListenPort = $AWG_PORT
Jc = $JC
Jmin = $JMIN
Jmax = $JMAX
S1 = $S1
S2 = $S2
H1 = $H1
H2 = $H2
H3 = $H3
H4 = $H4
EOF

cat > /opt/amnezia/amnezia-awg2/start.sh << 'EOF'
#!/bin/bash
awg-quick down /opt/amnezia/awg/awg0.conf 2>/dev/null
awg-quick up /opt/amnezia/awg/awg0.conf
iptables -A FORWARD -i awg0 -o eth0 -s 10.8.1.0/24 -j ACCEPT
iptables -A FORWARD -m state --state ESTABLISHED,RELATED -j ACCEPT
iptables -t nat -A POSTROUTING -s 10.8.1.0/24 -o eth0 -j MASQUERADE
tail -f /dev/null
EOF
chmod +x /opt/amnezia/amnezia-awg2/start.sh
```

### 4. Create Dockerfile and build

```bash
cat > /opt/amnezia/amnezia-awg2/Dockerfile << 'EOF'
FROM amneziavpn/amneziawg-go:latest
RUN apk add --no-cache bash curl dumb-init iptables
RUN mkdir -p /opt/amnezia/awg
COPY awg0.conf /opt/amnezia/awg/awg0.conf
COPY start.sh /opt/amnezia/start.sh
ENTRYPOINT ["dumb-init", "/opt/amnezia/start.sh"]
EOF

cd /opt/amnezia/amnezia-awg2
docker build -t amnezia-awg2-local .
```

### 5. Run the container

```bash
docker run -d \
  --name amnezia-awg2 \
  --restart unless-stopped \
  --cap-add NET_ADMIN \
  --cap-add SYS_MODULE \
  -v /lib/modules:/lib/modules \
  -p ${AWG_PORT}:${AWG_PORT}/udp \
  amnezia-awg2-local
```

### 6. Open UFW (if active)

```bash
ufw allow ${AWG_PORT}/udp
```

### 7. Add first peer and get client config

Follow the **Manual Peer Management** section above to add peers and generate client `.conf` files.

---

## Adding to Proxima

Once you have a client `.conf` file:

1. Proxima → **Keys** → **AWG Configs** section
2. Click **+ Add AWG Config**
3. Paste the full contents of the `.conf` file
4. Give it a name and save
5. Assign it to a slot (create a new AWG-type slot if needed)

The config will appear in the slot's pool. Proxima starts an `awg-client-slot-N` Docker container with this config on the Proxima server.

---

## File Locations

On the VPS (inside the container):

| Path | Contents |
|------|----------|
| `/opt/amnezia/awg/awg0.conf` | Server config + all peer public keys |
| `/opt/amnezia/start.sh` | Container entrypoint: brings up the interface |

On the Proxima server:

| Path | Contents |
|------|----------|
| `/config/proxima-config.json` → `tunnel_configs` | All AWG client configs (stored as text) |
| `/config/awg-slot-N.conf` | Active client config written by failover |

---

## Current Deployments

| Server | IP | Port | Subnet | Container |
|--------|----|------|--------|-----------|
| ERG-DE | 46.224.49.250 | 80/UDP | 10.8.1.0/24 | `amnezia-awg2` |
| ERG-FI | 109.120.187.205 | 80/UDP | 10.8.1.0/24 | `amnezia-awg2` |

Both containers set up via Amnezia desktop client. Auto-restart enabled (`--restart unless-stopped`).

> **Note:** ERG and OFC (Moscow servers) connect to both ERG-DE and ERG-FI as AWG clients via `awg-client-slot-N` containers managed by Proxima.
