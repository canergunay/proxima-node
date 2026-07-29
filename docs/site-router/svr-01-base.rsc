# =============================================================
# SVR RB4011 - STAGE 1: identity, LAN, WAN, DHCP, DNS, failsafe
# Run first. Safe to run on a freshly reset router only.
#
# LAN 192.168.78.0/24 | router .1 | APs .31-.39 | Proxima .121 | NAS .122
# WAN = ether5
# =============================================================

/system identity set name=svr-rb4011
/system clock set time-zone-autodetect=no time-zone-name=Europe/Moscow

# NTP is off by default on RouterOS. Without it the clock drifts, ACME refuses
# to issue a certificate, WireGuard handshakes are rejected, and every log
# timestamp is fiction - a class of failure that is very hard to read backwards.
/system ntp client set enabled=yes mode=unicast
/system ntp client servers add address=time.cloudflare.com
/system ntp client servers add address=pool.ntp.org

# ---------- Bridge / LAN ----------
/interface bridge
add name=bridge1

/interface bridge port
add bridge=bridge1 interface=ether1
add bridge=bridge1 interface=ether2
add bridge=bridge1 interface=ether3
add bridge=bridge1 interface=ether4
add bridge=bridge1 interface=ether6
add bridge=bridge1 interface=ether7
add bridge=bridge1 interface=ether8
add bridge=bridge1 interface=ether9
add bridge=bridge1 interface=ether10

/ip address
add address=192.168.78.1/24 interface=bridge1 network=192.168.78.0

/interface list
add name=LAN
/interface list member
add interface=bridge1 list=LAN

# ---------- Call-home tunnel interface (key and peer come in stage 3) ----------
# Created here because the stage-2 firewall rules reference the interface.
# RouterOS generates a throwaway private key now; stage 3 replaces it.
/interface wireguard
add name=wg-erg listen-port=13232 mtu=1420 comment="call-home to ERG wg-easy"

/ip address
add address=10.13.13.11/24 interface=wg-erg network=10.13.13.0 comment="SVR MikroTik on mgmt network"

# ---------- WAN ----------
# Seven Sky already serves SHV/OFC, where the WAN runs a DHCP client and holds
# 46.39.245.211/24 with flag D. The address is static contractually but arrives
# as a DHCP reservation. Expect the same at SVR - this is likely the FINAL
# config, not bench scaffolding.
#
# No name= here: /ip dhcp-client takes no name parameter on this firmware, and
# it does not need one - the entry is identified by its interface. SHV's export
# carries name=client1 because it runs a newer RouterOS where that field exists.
/ip dhcp-client
add interface=ether5 disabled=no use-peer-dns=no add-default-route=yes check-gateway=arp comment="WAN - Seven Sky"

### Only if Seven Sky hands over a manually-configured static block instead:
# /ip dhcp-client remove [find interface=ether5]
# /ip address add address=<WAN_IP>/<PREFIX> interface=ether5 comment="WAN - Seven Sky static"
# /ip route add dst-address=0.0.0.0/0 gateway=<WAN_GW> check-gateway=ping

# ---------- DHCP server ----------
# .10-.30 only. The previous range ran to .250 and therefore included .121 and
# .122 - the Proxima box and the NAS - so a laptop could be handed the address
# the whole site depends on. Everything from .31 up is reserved: .31-.39 access
# points, .121 Proxima, .122 NAS. If a site outgrows 21 leases, extend upward
# from .140, never through the reserved block.
/ip pool
add name=dhcp_pool0 ranges=192.168.78.10-192.168.78.30

/ip dhcp-server
add address-pool=dhcp_pool0 interface=bridge1 name=dhcp1 lease-time=15m authoritative=yes disabled=no

# Proxima is gateway (opt 3) AND resolver (opt 6) - this is what puts LAN
# clients into DNS Mode. SHV never did this: it defines a dns-ofc-proxima
# option and never attaches it, so its LAN bypasses Proxima entirely.
# Short lease so the netwatch failover below actually reaches clients.
/ip dhcp-server network
add address=192.168.78.0/24 gateway=192.168.78.121 dns-server=192.168.78.121 comment="LAN via Proxima (netwatch failsafe -> .1)"

### Static leases - fill in as hardware arrives
# NAS candidate from the SHV lease table: host "FS-SVR", 90:09:D0:91:62:DD
# (Synology OUI, same as the SHV NAS). CONFIRM before trusting it.
# /ip dhcp-server lease add address=192.168.78.122 mac-address=90:09:D0:91:62:DD server=dhcp1 comment="Synology DS725+"
# /ip dhcp-server lease add address=192.168.78.121 mac-address=<M70Q_MAC> server=dhcp1 comment="Proxima box"

# ---------- Netwatch failsafe ----------
# Scripts carry explicit policy AND dont-require-permissions=yes; netwatch only
# calls them. Both are needed: with dont-require-permissions=no, netwatch calls
# the script and nothing happens - no error, no log line, no change. Verified
# on the bench 2026-07-28: running the same script by hand worked, netwatch
# firing it did not. "It works when I run it manually" proves nothing here.
#
# SHV has nothing equivalent: its netwatch pings 192.168.77.1 - the router
# pinging itself, permanently up - and logs "Queue Tree Load High". It can
# never fire.
#
# [find] carries NO address filter, and that is deliberate. Written as
# [find address=192.168.78.0/24] the scripts run, log their message, and change
# nothing: inside a script body "/" starts a command path, so the value is cut
# at 192.168.78.0, the filter matches no record, and `set` on an empty list is
# a silent no-op. Caught on the bench 2026-07-28 - the failsafe looked healthy
# (netwatch status=down, log line present) while doing absolutely nothing.
# There is only ever one DHCP network on this router, so no filter is needed.
# If a second one is ever added, filter by comment - never by an unquoted
# address prefix.
/system script
add name=proxima-dhcp-failover dont-require-permissions=yes policy=read,write,test,policy \
    source="/ip dhcp-server network set [find] gateway=192.168.78.1 dns-server=192.168.78.1; :log warning \"PROXIMA DOWN - DHCP handed back to router\";"
add name=proxima-dhcp-restore dont-require-permissions=yes policy=read,write,test,policy \
    source="/ip dhcp-server network set [find] gateway=192.168.78.121 dns-server=192.168.78.121; :log warning \"PROXIMA UP - DHCP restored to Proxima\";"

/tool netwatch
add comment=proxima-failsafe host=192.168.78.121 interval=30s timeout=3s type=simple disabled=no \
    down-script="/system script run proxima-dhcp-failover" \
    up-script="/system script run proxima-dhcp-restore"
add comment=internet-monitor host=8.8.8.8 interval=30s type=simple disabled=no \
    down-script=":log warning \"WAN DOWN detected\"" \
    up-script=":log warning \"WAN UP recovered\""

# Known limit: this is an ICMP test. If the box is alive but dnsmasq is dead,
# it will not fire. It catches a dead box, not a sick one.

# ---------- DNS ----------
# LAN clients resolve at .121 (Proxima dnsmasq). These entries serve the router
# itself and cover the netwatch-failover window.
/ip dns
set allow-remote-requests=yes servers=8.8.8.8,1.1.1.1

/ip dns static
add name=svr.fs-bc.net   address=192.168.78.121 type=A
add name=svr-p.fs-bc.net address=192.168.78.121 type=A
add name=svr-d.fs-bc.net address=192.168.78.121 type=A
add name=svr-n.fs-bc.net address=192.168.78.122 type=A

# update-time is a second, independent path to a correct clock. The RB4011 has
# no battery-backed RTC: every power loss drops it back to the firmware build
# date until something corrects it. If NTP is blocked or DNS is not up yet, the
# cloud service still sets the time.
/ip cloud
set ddns-enabled=yes ddns-update-interval=10m update-time=yes

# Longer UDP timeouts keep WireGuard/AWG sessions alive (carried from SHV)
/ip firewall connection tracking
set udp-stream-timeout=10m udp-timeout=10m

# ---------- Weekly backup ----------
/system script
add name=weekly-backup-script dont-require-permissions=no policy=read,write,test,policy,password,sensitive \
    source=":local date [/system clock get date]; :local time [/system clock get time]; :local dateFormatted ([:pick \$date 4 6] . \"-\" . [:pick \$date 0 3] . \"-\" . [:pick \$date 7 11]); :local timeFormatted ([:pick \$time 0 2] . \".\" . [:pick \$time 3 5] . \".\" . [:pick \$time 6 8]); :local filename (\"backups/svr-mikrotik-\" . \$dateFormatted . \"-\" . \$timeFormatted . \".backup\"); :if ([/file find name=\$filename] != \"\") do={ /file remove \$filename }; /system backup save name=\$filename"

/system scheduler
add name=weekly-backup interval=1w start-time=03:00:00 \
    policy=read,write,test,policy,password,sensitive \
    on-event="/system script run weekly-backup-script"

:log warning "STAGE 1 COMPLETE - base config applied"
