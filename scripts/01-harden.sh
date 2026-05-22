#!/usr/bin/env bash
# System hardening: sysctl, SSH, UFW
# Part of proxima-node setup

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/common.sh"

setup_harden() {
    log_step "System hardening"

    # --- sysctl ---
    log_info "Configuring sysctl (ip_forward, BBR)..."
    cat > /etc/sysctl.d/99-proxima-node.conf <<'SYSCTL'
# IP forwarding (required for VPN)
net.ipv4.ip_forward = 1

# TCP BBR congestion control
net.core.default_qdisc = fq
net.ipv4.tcp_congestion_control = bbr

# Hardening
net.ipv4.conf.all.rp_filter = 1
net.ipv4.conf.default.rp_filter = 1
net.ipv4.icmp_echo_ignore_broadcasts = 1
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.conf.default.accept_redirects = 0
net.ipv4.conf.all.send_redirects = 0
net.ipv4.conf.default.send_redirects = 0
SYSCTL
    sysctl --system > /dev/null 2>&1
    log_info "BBR enabled: $(sysctl -n net.ipv4.tcp_congestion_control)"

    # --- SSH hardening ---
    log_info "Hardening SSH..."
    local sshd_config="/etc/ssh/sshd_config"
    # Disable password auth if key-based auth works
    if [[ -f /root/.ssh/authorized_keys ]] && [[ -s /root/.ssh/authorized_keys ]]; then
        sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' "$sshd_config"
        sed -i 's/^#\?PubkeyAuthentication.*/PubkeyAuthentication yes/' "$sshd_config"
        log_info "Password authentication disabled (SSH keys detected)"
    else
        log_warn "No SSH keys found — keeping password auth enabled"
    fi
    sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin prohibit-password/' "$sshd_config"
    sed -i 's/^#\?X11Forwarding.*/X11Forwarding no/' "$sshd_config"
    systemctl reload sshd 2>/dev/null || systemctl reload ssh 2>/dev/null || true

    # --- UFW ---
    log_info "Configuring UFW firewall..."
    apt-get install -y -qq ufw > /dev/null 2>&1

    # Reset without prompt
    ufw --force reset > /dev/null 2>&1

    ufw default deny incoming > /dev/null 2>&1
    ufw default allow outgoing > /dev/null 2>&1

    # SSH
    ufw allow 22/tcp comment "SSH" > /dev/null 2>&1
    # Outline SS
    ufw allow 8388/tcp comment "Outline SS TCP" > /dev/null 2>&1
    ufw allow 8388/udp comment "Outline SS UDP" > /dev/null 2>&1
    # ssconf
    ufw allow 8390/tcp comment "ssconf HTTPS" > /dev/null 2>&1
    # Speedtest
    ufw allow 8999/tcp comment "Proxima speedtest" > /dev/null 2>&1
    # AmneziaWG (managed by AmneziaVPN client, default port 80/udp)
    ufw allow 80/udp comment "AmneziaWG" > /dev/null 2>&1
    # Xray VLESS+Reality (managed by AmneziaVPN client, default port 443/tcp)
    ufw allow 443/tcp comment "Xray VLESS Reality" > /dev/null 2>&1
    # AdGuard Home admin panel (restricted to VPN clients later)
    ufw allow 3000/tcp comment "AdGuard Home setup" > /dev/null 2>&1

    ufw --force enable > /dev/null 2>&1
    log_info "UFW enabled with rules:"
    ufw status numbered 2>/dev/null | grep -v "^Status:" | grep -v "^$" | head -20

    log_info "System hardening complete"
}
