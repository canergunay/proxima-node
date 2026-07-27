# =============================================================
# SVR RB4011 - STAGE 3: call-home management tunnel
# Run after stages 1-2.
#
# THE ERG SIDE IS ALREADY DONE (2026-07-27). Applied there:
#   - the exposed peer IWTTFyTx... was removed from wg0
#   - a fresh keypair + PSK were generated
#   - wg0.json entry "SVR-Mikrotik" moved 10.13.13.5 -> 10.13.13.11
#   - live peer added with allowed-ips 10.13.13.11/32
#   - wg0.json backed up as wg0.json.bak-<timestamp>
#
# GET THE TWO VALUES BELOW FROM ERG (they were never printed to chat):
#   ssh erg
#   sudo cat /root/svr-mikrotik-keys.txt
#
# Note: the wg-easy container on ERG is named "wireguard", NOT "wg-easy".
# =============================================================

# The key is generated on ERG because wg-easy stores each client's private key
# in wg0.json and renders its UI from it. Letting RouterOS generate its own
# would leave the two sides mismatched.
/interface wireguard
set [find name=wg-erg] private-key="<PrivateKey from svr-mikrotik-keys.txt>"

# allowed-address is 10.13.13.0/24 ONLY.
# A peer config downloaded from the wg-easy UI carries ERG's 192.168.1.0/24 and
# 192.168.2.0/24 because WG_ALLOWED_IPS is a global template. That is wrong for
# every site: the first site that uses 192.168.1.0/24 - a very common default -
# loses its own LAN the moment the tunnel comes up.
/interface wireguard peers
add interface=wg-erg name=erg-wg-easy \
    public-key="HV5I02RUipcseDKB1GID1OLeC/C9m60QSr45R72JWQo=" \
    preshared-key="<PresharedKey from svr-mikrotik-keys.txt>" \
    endpoint-address=vpn.ergunay.com endpoint-port=51820 \
    allowed-address=10.13.13.0/24 \
    persistent-keepalive=25s

# No /ip route needed - the 10.13.13.11/24 address from stage 1 is a connected
# route. Do NOT add a DNS setting: the wg-quick "DNS =" directive has no
# RouterOS equivalent, and on a Linux box it would push all DNS through the
# tunnel and make name resolution depend on it.

# ---------- Verify ----------
#   /interface wireguard peers print detail
#     -> last-handshake should be under a minute
#   /ping 10.13.13.1 count=4
#
# From an admin device on 10.13.13.x, WinBox to 192.168.78.1 should now work.
# On ERG:  sudo wg show wg0   -> the 10.13.13.11 peer gets a handshake.

:log warning "STAGE 3 COMPLETE - call-home tunnel configured"
