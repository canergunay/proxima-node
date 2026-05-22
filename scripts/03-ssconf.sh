#!/usr/bin/env bash
# ssconf HTTPS server setup — serves SS config for Proxima clients
# Part of proxima-node setup

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/common.sh"

OUTLINE_DIR="/opt/outline-ss"

setup_ssconf() {
    log_step "ssconf HTTPS Server"

    # Generate ssconf token
    local ssconf_token
    ssconf_token=$(read_config "SSCONF_TOKEN")
    if [[ -z "$ssconf_token" ]]; then
        ssconf_token=$(generate_token 48)
        save_config "SSCONF_TOKEN" "$ssconf_token"
        log_info "Generated ssconf token"
    fi

    # Generate TLS cert for ssconf if not exists
    if [[ ! -f "$OUTLINE_DIR/cert.pem" ]]; then
        log_info "Generating self-signed TLS certificate..."
        generate_self_signed_cert "$OUTLINE_DIR/cert.pem" "$OUTLINE_DIR/key.pem"
    fi

    # Copy ssconf server script
    cp "$REPO_DIR/templates/ssconf-server.py" "$OUTLINE_DIR/ssconf-server.py"

    # Read config values
    local server_ip ss_password ss_prefix
    server_ip=$(read_config "SERVER_IP")
    ss_password=$(read_config "SS_PASSWORD")
    ss_prefix=$(read_config "SS_PREFIX")

    # systemd service with environment variables
    cat > /etc/systemd/system/proxima-ssconf.service <<SERVICE
[Unit]
Description=Proxima ssconf HTTPS Server
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 ${OUTLINE_DIR}/ssconf-server.py
Environment=SSCONF_TOKEN=${ssconf_token}
Environment=SSCONF_SERVER_IP=${server_ip}
Environment=SSCONF_SS_PORT=8388
Environment=SSCONF_SS_PASSWORD=${ss_password}
Environment=SSCONF_SS_CIPHER=chacha20-ietf-poly1305
Environment=SSCONF_SS_PREFIX=${ss_prefix}
Environment=SSCONF_CERT=${OUTLINE_DIR}/cert.pem
Environment=SSCONF_KEY=${OUTLINE_DIR}/key.pem
Restart=always
RestartSec=5
User=nobody
Group=nogroup
WorkingDirectory=${OUTLINE_DIR}

[Install]
WantedBy=multi-user.target
SERVICE

    systemctl daemon-reload
    systemctl enable --now proxima-ssconf
    log_info "ssconf server started on port 8390"
    log_info "ssconf URL: https://${server_ip}:8390/${ssconf_token}"
}
