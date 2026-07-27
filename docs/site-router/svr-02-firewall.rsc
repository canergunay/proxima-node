# =============================================================
# SVR RB4011 - STAGE 2: NAT, firewall, service hardening
# Run after stage 1. Requires bridge1, ether5 and wg-erg to exist.
#
# WARNING: this stage closes the input chain with a default drop. Apply it
# from the LAN side (bridge1), never from a WAN-side connection.
# =============================================================

# ---------- NAT ----------
/ip firewall nat
add chain=srcnat action=masquerade out-interface=ether5 comment="WAN masquerade"

# in-interface is MANDATORY. Without it, VPN UDP leaving the LAN gets hijacked
# back to .121 - the trap already documented from OFC.
add chain=dstnat action=dst-nat protocol=udp dst-port=5555 in-interface=ether5 \
    to-addresses=192.168.78.121 to-ports=5555 comment="ProximaVPN AWG"

# SVR has no NAS on 443 (NAS is .122), so 443 is free here - unlike SHV, which
# had to shift NPM to 5443.
add chain=dstnat action=dst-nat protocol=tcp dst-port=80 in-interface=ether5 \
    to-addresses=192.168.78.121 to-ports=80 comment="NPM HTTP / ACME http-01"
add chain=dstnat action=dst-nat protocol=tcp dst-port=443 in-interface=ether5 \
    to-addresses=192.168.78.121 to-ports=443 comment="NPM HTTPS"

### TODO SEVEN SKY - hairpin NAT, needs the public IP.
# Mandatory: VPN profiles are bare-IP by design, so a phone on the SVR LAN
# dials the public IP and split DNS cannot help it.
# /ip firewall nat
# add chain=dstnat action=dst-nat protocol=udp dst-port=5555 dst-address=<SVR_PUBLIC_IP> \
#     src-address=192.168.78.0/24 to-addresses=192.168.78.121 comment="ProximaVPN hairpin DNAT"
# add chain=srcnat action=src-nat protocol=udp dst-port=5555 dst-address=192.168.78.121 \
#     src-address=192.168.78.0/24 to-addresses=192.168.78.1 comment="ProximaVPN hairpin SNAT"
# add chain=dstnat action=dst-nat protocol=tcp dst-port=443 dst-address=<SVR_PUBLIC_IP> \
#     src-address=192.168.78.0/24 to-addresses=192.168.78.121 comment="NPM hairpin DNAT"
# add chain=srcnat action=src-nat protocol=tcp dst-port=443 dst-address=192.168.78.121 \
#     src-address=192.168.78.0/24 to-addresses=192.168.78.1 comment="NPM hairpin SNAT"

# ---------- Firewall: input ----------
# SHV has no default drop here - its input chain is open to the WAN and only
# /ip service address lists hold the line, with dst-port=2210 accepted from
# anywhere. SVR closes the chain.
/ip firewall filter
add chain=input action=accept connection-state=established,related,untracked comment="input: established"
add chain=input action=drop   connection-state=invalid comment="input: invalid"
add chain=input action=accept protocol=icmp comment="input: ICMP"
add chain=input action=accept in-interface=bridge1 comment="input: LAN trusted"
add chain=input action=accept in-interface=wg-erg src-address=10.13.13.0/24 comment="input: emergency management network"
add chain=input action=accept protocol=udp dst-port=68 in-interface=ether5 comment="input: DHCP client on WAN"
add chain=input action=drop   comment="input: drop everything else"

# ---------- Firewall: forward ----------
# SHV has a bare 'action=accept chain=forward' with no matchers sitting above
# everything else, which makes every rule below it dead - including its own
# final drop. Not reproduced.
add chain=forward action=accept connection-state=established,related,untracked comment="forward: established"
add chain=forward action=drop   connection-state=invalid comment="forward: invalid"
add chain=forward action=accept connection-state=new in-interface=bridge1 comment="forward: LAN outbound"
add chain=forward action=accept connection-state=new connection-nat-state=dstnat in-interface=ether5 comment="forward: published services"
add chain=forward action=drop   comment="forward: drop everything else"

# ---------- Services ----------
/ip service
set telnet disabled=yes
set ftp disabled=yes
set www disabled=yes
set api disabled=yes
set api-ssl disabled=yes
set ssh    address=192.168.78.0/24,10.13.13.0/24
set winbox address=192.168.78.0/24,10.13.13.0/24

/ip neighbor discovery-settings set discover-interface-list=LAN
/tool mac-server set allowed-interface-list=none
/tool mac-server mac-winbox set allowed-interface-list=LAN
/tool bandwidth-server set enabled=no
/ip proxy set enabled=no
/ip socks set enabled=no

:log warning "STAGE 2 COMPLETE - firewall active, input chain closed"
