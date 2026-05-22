#!/usr/bin/env bash
# Common functions for proxima-node setup scripts

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }
log_step()  { echo -e "${BLUE}[STEP]${NC} ${BOLD}$*${NC}"; }

# Generate a cryptographically secure random string
# Usage: generate_secret <length>
generate_secret() {
    local len="${1:-32}"
    openssl rand -base64 "$len" | tr -d '/+=' | head -c "$len"
}

# Generate a base64-encoded 32-byte key (for Shadowsocks)
generate_ss_key() {
    openssl rand -base64 32
}

# Generate a hex token
generate_token() {
    local len="${1:-48}"
    openssl rand -hex "$((len / 2))"
}

# Detect public IPv4
detect_public_ip() {
    local ip
    ip=$(curl -4 -s --max-time 5 https://ifconfig.me 2>/dev/null) ||
    ip=$(curl -4 -s --max-time 5 https://api.ipify.org 2>/dev/null) ||
    ip=$(curl -4 -s --max-time 5 https://checkip.amazonaws.com 2>/dev/null) ||
    ip=""
    echo "$ip"
}

# Generate self-signed TLS certificate
# Usage: generate_self_signed_cert <cert_path> <key_path>
generate_self_signed_cert() {
    local cert_path="$1"
    local key_path="$2"
    local ip
    ip=$(detect_public_ip)

    openssl req -x509 -nodes -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 \
        -keyout "$key_path" -out "$cert_path" -days 3650 \
        -subj "/CN=proxima-node" \
        -addext "subjectAltName=IP:${ip:-127.0.0.1}" 2>/dev/null

    chmod 644 "$cert_path"
    chmod 600 "$key_path"
}

# Check if running as root
require_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root"
        exit 1
    fi
}

# Check if Debian 12
check_os() {
    if [[ ! -f /etc/os-release ]]; then
        log_error "Cannot detect OS"
        exit 1
    fi
    # shellcheck disable=SC1091
    source /etc/os-release
    if [[ "$ID" != "debian" && "$ID" != "ubuntu" ]]; then
        log_warn "This script is designed for Debian/Ubuntu. Detected: $ID $VERSION_ID"
        log_warn "Proceeding anyway..."
    fi
}

# Save a value to the node config file
# Usage: save_config <key> <value>
NODE_CONFIG="/opt/proxima-node/config.env"
save_config() {
    local key="$1"
    local value="$2"
    mkdir -p "$(dirname "$NODE_CONFIG")"
    if grep -q "^${key}=" "$NODE_CONFIG" 2>/dev/null; then
        sed -i "s|^${key}=.*|${key}=${value}|" "$NODE_CONFIG"
    else
        echo "${key}=${value}" >> "$NODE_CONFIG"
    fi
}

# Read a value from the node config file
# Usage: read_config <key>
read_config() {
    local key="$1"
    grep "^${key}=" "$NODE_CONFIG" 2>/dev/null | cut -d'=' -f2- || echo ""
}
