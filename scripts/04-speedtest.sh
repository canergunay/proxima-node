#!/usr/bin/env bash
# Proxima speed test server setup
# Part of proxima-node setup

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/common.sh"

SPEEDTEST_DIR="/opt/proxima-speedtest"

setup_speedtest() {
    log_step "Proxima Speed Test Server"

    mkdir -p "$SPEEDTEST_DIR"

    # Generate API key
    local api_key
    api_key=$(read_config "SPEEDTEST_API_KEY")
    if [[ -z "$api_key" ]]; then
        api_key=$(generate_secret 43)
        save_config "SPEEDTEST_API_KEY" "$api_key"
        log_info "Generated speedtest API key"
    fi

    # Generate TLS cert
    if [[ ! -f "$SPEEDTEST_DIR/cert.pem" ]]; then
        log_info "Generating self-signed TLS certificate for speedtest..."
        generate_self_signed_cert "$SPEEDTEST_DIR/cert.pem" "$SPEEDTEST_DIR/key.pem"
    fi

    # Copy speedtest server script
    cp "$REPO_DIR/templates/speedtest-server.py" "$SPEEDTEST_DIR/speedtest-server.py"

    # systemd service
    cat > /etc/systemd/system/proxima-speedtest.service <<SERVICE
[Unit]
Description=Proxima Speed Test Server
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 ${SPEEDTEST_DIR}/speedtest-server.py
Environment=SPEEDTEST_API_KEY=${api_key}
Environment=SPEEDTEST_CERT=${SPEEDTEST_DIR}/cert.pem
Environment=SPEEDTEST_KEY=${SPEEDTEST_DIR}/key.pem
Restart=always
RestartSec=5
User=nobody
Group=nogroup
WorkingDirectory=${SPEEDTEST_DIR}

[Install]
WantedBy=multi-user.target
SERVICE

    systemctl daemon-reload
    systemctl enable --now proxima-speedtest

    local server_ip
    server_ip=$(read_config "SERVER_IP")
    log_info "Speedtest server started on port 8999"
    log_info "Health check: https://${server_ip}:8999/speedtest/health"
}
