#!/usr/bin/env bash
# Zapret Agent — lightweight management API
# Part of proxima-node setup
#
# Installs a Flask-based HTTP agent on port 5050 that allows
# remote management of zapret (nfqws2) and shadowsocks services.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/common.sh"

AGENT_DIR="/opt/zapret-agent"
AGENT_SRC="$SCRIPT_DIR/../zapret-agent"

setup_zapret_agent() {
    log_step "Zapret Agent (management API)"

    # Install Python + pip + Flask
    log_info "Installing Python dependencies..."
    apt-get install -y -qq python3 python3-pip python3-venv curl > /dev/null 2>&1

    # Copy agent files
    mkdir -p "$AGENT_DIR"
    cp "$AGENT_SRC/agent.py" "$AGENT_DIR/agent.py"
    cp "$AGENT_SRC/requirements.txt" "$AGENT_DIR/requirements.txt"

    # Create venv and install dependencies
    if [[ ! -d "$AGENT_DIR/venv" ]]; then
        python3 -m venv "$AGENT_DIR/venv"
    fi
    "$AGENT_DIR/venv/bin/pip" install --quiet -r "$AGENT_DIR/requirements.txt"
    log_info "Flask installed in venv"

    # Generate sync_key if not exists
    local sync_key
    sync_key=$(read_config "ZAPRET_AGENT_SYNC_KEY")
    if [[ -z "$sync_key" ]]; then
        sync_key=$(generate_secret 32)
        save_config "ZAPRET_AGENT_SYNC_KEY" "$sync_key"
        log_info "Generated new sync key"
    fi

    # Detect server IP
    local server_ip
    server_ip=$(read_config "SERVER_IP")
    if [[ -z "$server_ip" ]]; then
        server_ip=$(detect_public_ip)
        if [[ -z "$server_ip" ]]; then
            # Fall back to local IP
            server_ip=$(hostname -I | awk '{print $1}')
        fi
        save_config "SERVER_IP" "$server_ip"
    fi

    # Node name
    local node_name
    node_name=$(read_config "NODE_NAME")
    if [[ -z "$node_name" ]]; then
        node_name="zapret-$(hostname -s)"
        save_config "NODE_NAME" "$node_name"
    fi

    # Write agent config
    cat > "$AGENT_DIR/config.json" <<JSON
{
    "sync_key": "${sync_key}",
    "server_ip": "${server_ip}",
    "node_name": "${node_name}"
}
JSON
    chmod 600 "$AGENT_DIR/config.json"
    log_info "Agent config written to $AGENT_DIR/config.json"

    # Create systemd service
    cat > /etc/systemd/system/zapret-agent.service <<'SERVICE'
[Unit]
Description=Zapret Agent (management API)
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/zapret-agent
ExecStart=/opt/zapret-agent/venv/bin/python /opt/zapret-agent/agent.py
Restart=always
RestartSec=5
Environment=ZAPRET_AGENT_CONFIG=/opt/zapret-agent/config.json

[Install]
WantedBy=multi-user.target
SERVICE

    systemctl daemon-reload
    systemctl enable --now zapret-agent
    log_info "zapret-agent service started on port 5050"

    # Open port in UFW if installed
    if command -v ufw &>/dev/null; then
        ufw allow 5050/tcp comment "Zapret Agent API" > /dev/null 2>&1
        log_info "UFW: port 5050 opened"
    fi

    # Verify
    sleep 2
    if systemctl is-active --quiet zapret-agent; then
        log_info "Agent is running — http://${server_ip}:5050/health"
    else
        log_warn "Agent may not have started — check: journalctl -u zapret-agent"
    fi

    echo ""
    echo -e "${BOLD}── Zapret Agent ────────────────────────────────────────${NC}"
    echo -e "  URL:      http://${server_ip}:5050"
    echo -e "  Sync Key: ${sync_key}"
    echo -e "  Config:   $AGENT_DIR/config.json"
    echo ""
}
