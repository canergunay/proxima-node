#!/usr/bin/env bash
# Zapret (nfqws2) DPI bypass setup
# Part of proxima-node setup
#
# Builds nfqws2 from source (zapret2), installs as systemd service.
# DPI args are stored in /etc/zapret/dpi-args.conf and can be updated
# remotely via the zapret-agent API.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/common.sh"

ZAPRET_DIR="/opt/zapret"
ZAPRET_BIN="$ZAPRET_DIR/bin"
ZAPRET_CONF="/etc/zapret"
DPI_ARGS_FILE="$ZAPRET_CONF/dpi-args.conf"
QUEUE_NUM=200

setup_zapret() {
    log_step "Zapret (nfqws2) DPI Bypass"

    # Install build dependencies
    log_info "Installing build dependencies..."
    apt-get install -y -qq build-essential git libnetfilter-queue-dev \
        libcap-dev zlib1g-dev > /dev/null 2>&1

    # Clone or update zapret2
    if [[ -d "$ZAPRET_DIR/src/.git" ]]; then
        log_info "Updating zapret2 source..."
        git -C "$ZAPRET_DIR/src" pull --quiet
    else
        log_info "Cloning zapret2..."
        mkdir -p "$ZAPRET_DIR"
        git clone --quiet --depth 1 https://github.com/bol-van/zapret2.git "$ZAPRET_DIR/src"
    fi

    # Build nfqws2
    log_info "Building nfqws2..."
    make -C "$ZAPRET_DIR/src/nfq" clean > /dev/null 2>&1 || true
    make -C "$ZAPRET_DIR/src/nfq" -j"$(nproc)" > /dev/null 2>&1
    mkdir -p "$ZAPRET_BIN"
    cp "$ZAPRET_DIR/src/nfq/nfqws" "$ZAPRET_BIN/nfqws2"
    chmod +x "$ZAPRET_BIN/nfqws2"
    log_info "nfqws2 built: $ZAPRET_BIN/nfqws2"

    # Copy Lua scripts
    if [[ -d "$ZAPRET_DIR/src/nfq/lua" ]]; then
        cp -r "$ZAPRET_DIR/src/nfq/lua" "$ZAPRET_DIR/lua"
        log_info "Lua scripts copied to $ZAPRET_DIR/lua"
    fi

    # Create default DPI args config
    mkdir -p "$ZAPRET_CONF"
    if [[ ! -f "$DPI_ARGS_FILE" ]]; then
        cat > "$DPI_ARGS_FILE" <<'ARGS'
--lua-desync=wssize:wsize=1:scale=6 --payload=tls_client_hello --lua-desync=multidisorder:pos=1,midsld
ARGS
        log_info "Default DPI args written to $DPI_ARGS_FILE"
    else
        log_info "DPI args config already exists"
    fi

    # Create systemd service
    cat > /etc/systemd/system/zapret-nfqws2.service <<SERVICE
[Unit]
Description=Zapret nfqws2 DPI Bypass
After=network.target

[Service]
Type=simple
ExecStartPre=/sbin/iptables -t mangle -I OUTPUT -p tcp --dport 443 -m connbytes --connbytes-dir=original --connbytes-mode=packets --connbytes 1:15 -j NFQUEUE --queue-num ${QUEUE_NUM} --queue-bypass
ExecStart=/bin/sh -c '${ZAPRET_BIN}/nfqws2 --qnum=${QUEUE_NUM} \$(cat ${DPI_ARGS_FILE})'
ExecStopPost=/sbin/iptables -t mangle -D OUTPUT -p tcp --dport 443 -m connbytes --connbytes-dir=original --connbytes-mode=packets --connbytes 1:15 -j NFQUEUE --queue-num ${QUEUE_NUM} --queue-bypass
Restart=on-failure
RestartSec=5
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
SERVICE

    systemctl daemon-reload
    systemctl enable --now zapret-nfqws2
    log_info "zapret-nfqws2 service started"

    # Verify
    sleep 1
    if systemctl is-active --quiet zapret-nfqws2; then
        log_info "nfqws2 is running (queue=$QUEUE_NUM)"
    else
        log_warn "nfqws2 may not have started correctly — check: journalctl -u zapret-nfqws2"
    fi
}
