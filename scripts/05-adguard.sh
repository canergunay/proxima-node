#!/usr/bin/env bash
# AdGuard Home setup via Docker
# Part of proxima-node setup

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/common.sh"

ADGUARD_DIR="/opt/adguardhome"

setup_adguard() {
    log_step "AdGuard Home (Docker)"

    # Install Docker if not present
    if ! command -v docker &>/dev/null; then
        log_info "Installing Docker..."
        curl -fsSL https://get.docker.com | bash > /dev/null 2>&1
        systemctl enable --now docker
        log_info "Docker installed"
    else
        log_info "Docker already installed"
    fi

    mkdir -p "$ADGUARD_DIR/work" "$ADGUARD_DIR/conf"

    # Stop existing container if any
    docker rm -f adguardhome 2>/dev/null || true

    # Run AdGuard Home
    log_info "Starting AdGuard Home container..."
    docker run -d \
        --name adguardhome \
        --restart always \
        -v "$ADGUARD_DIR/work:/opt/adguardhome/work" \
        -v "$ADGUARD_DIR/conf:/opt/adguardhome/conf" \
        -p 53:53/tcp \
        -p 53:53/udp \
        -p 3000:3000/tcp \
        adguard/adguardhome:latest

    local server_ip
    server_ip=$(read_config "SERVER_IP")

    log_info "AdGuard Home container started"
    log_info "Setup wizard: http://${server_ip}:3000"
    log_warn "After initial setup, port 3000 becomes the admin panel"
    log_warn "Configure upstream DNS and filtering lists via the web UI"

    save_config "ADGUARD_ENABLED" "true"
}
