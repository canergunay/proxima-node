#!/usr/bin/env bash
# Outline Shadowsocks server setup
# Part of proxima-node setup

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/common.sh"

OUTLINE_DIR="/opt/outline-ss"
OUTLINE_BIN="$OUTLINE_DIR/outline-ss-server"
OUTLINE_VERSION="1.5.0"

setup_outline_ss() {
    log_step "Outline Shadowsocks Server"

    mkdir -p "$OUTLINE_DIR"

    # Download outline-ss-server binary
    if [[ ! -f "$OUTLINE_BIN" ]]; then
        log_info "Downloading outline-ss-server v${OUTLINE_VERSION}..."
        local arch
        arch=$(uname -m)
        case "$arch" in
            x86_64)  arch="x86_64" ;;
            aarch64) arch="arm64" ;;
            *)       log_error "Unsupported architecture: $arch"; exit 1 ;;
        esac
        local url="https://github.com/Jigsaw-Code/outline-ss-server/releases/download/v${OUTLINE_VERSION}/outline-ss-server_${OUTLINE_VERSION}_linux_${arch}.tar.gz"
        curl -sSL "$url" | tar xz -C "$OUTLINE_DIR" outline-ss-server
        chmod +x "$OUTLINE_BIN"
        log_info "Downloaded to $OUTLINE_BIN"
    else
        log_info "outline-ss-server already exists at $OUTLINE_BIN"
    fi

    # Generate SS password if not exists
    local ss_password
    ss_password=$(read_config "SS_PASSWORD")
    if [[ -z "$ss_password" ]]; then
        ss_password=$(generate_ss_key)
        save_config "SS_PASSWORD" "$ss_password"
        log_info "Generated new SS password"
    fi

    # Generate TLS ClientHello prefix
    local ss_prefix
    ss_prefix=$(read_config "SS_PREFIX")
    if [[ -z "$ss_prefix" ]]; then
        ss_prefix="FgMBAgABAAH8AwM="
        save_config "SS_PREFIX" "$ss_prefix"
    fi

    # Detect public IP
    local server_ip
    server_ip=$(read_config "SERVER_IP")
    if [[ -z "$server_ip" ]]; then
        server_ip=$(detect_public_ip)
        save_config "SERVER_IP" "$server_ip"
        log_info "Detected public IP: $server_ip"
    fi

    # Node ID
    local node_id
    node_id=$(read_config "NODE_ID")
    if [[ -z "$node_id" ]]; then
        node_id="proxima-node-$(hostname -s)"
        save_config "NODE_ID" "$node_id"
    fi

    # Write config
    cat > "$OUTLINE_DIR/config.yml" <<YAML
services:
  - listeners:
      - type: tcp
        address: "[::]:8388"
      - type: udp
        address: "[::]:8388"
    keys:
      - id: ${node_id}
        cipher: chacha20-ietf-poly1305
        secret: "${ss_password}"
        prefix: "${ss_prefix}"
YAML
    log_info "Config written to $OUTLINE_DIR/config.yml"

    # systemd service
    cat > /etc/systemd/system/outline-ss-server.service <<'SERVICE'
[Unit]
Description=Outline SS Server
After=network.target

[Service]
Type=simple
ExecStart=/opt/outline-ss/outline-ss-server -config /opt/outline-ss/config.yml
Restart=always
RestartSec=5
User=nobody
Group=nogroup

[Install]
WantedBy=multi-user.target
SERVICE

    systemctl daemon-reload
    systemctl enable --now outline-ss-server
    log_info "outline-ss-server service started"
}
