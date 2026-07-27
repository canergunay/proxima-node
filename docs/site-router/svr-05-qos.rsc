# =============================================================
# SVR RB4011 - STAGE 5: QoS
#
# Set for the 200 Mbit Seven Sky line — the same product SHV runs. Safe to run
# on the bench now; it no longer carries placeholder numbers.
#
# CONFIRM ON SITE ANYWAY. The figure comes from the contract, not from a
# measurement, and the two failures are not symmetrical: a ceiling below the
# real rate costs bandwidth and is obvious, while a ceiling at or above it
# costs the entire feature and is invisible — the queue never fills, so
# priority is never consulted and QoS appears configured while doing nothing.
#
# Measure from the Proxima box, several times, at a busy hour:
#   speedtest-cli --simple      (or the Proxima Speed Test page, direct slot)
# If the line does not sustain 200, set both roots to ~95% of what it does
# sustain and rescale limit-at so the children still sum to the root.
#
# If upload is not also 200, change the Upload root on its own.
#
# =============================================================
# Why SHV's QoS does nothing today - three independent faults:
#
#  1. NO ROOT SHAPER. All 7 queues sit on parent=global with no ceiling, so the
#     queue forms at the ISP, not on the router. HTB priority only arbitrates a
#     parent that is actually full -> priority is never consulted. This one is
#     fatal on its own; the other two barely matter next to it.
#  2. Priority-Web is overwritten one line later. mark-connection defaults to
#     passthrough=yes, and the Genel-Web rule below it matches the same
#     tcp/80,443 with no connection-mark filter, so every work-sites connection
#     is re-marked as general web. That queue has been empty since it was written.
#  3. The NAS rule matches src-address=NAS AND dst-port=445,21,5000-5001.
#     Traffic from the NAS carries those as SOURCE ports. Near-zero hits.
#
#  Also: max-limits of 180M/200M against an unknown line, and no default queue,
#  so unclassified traffic is unshaped and starves the classified queues.
#
# CAVEAT before tuning: once DNS Mode is live, most site traffic leaves as
# AWG/UDP to a tunnel endpoint. The router cannot see ports or SNI inside it,
# so it all lands in VPN-Traffic regardless of what it really is. Port-based
# QoS only classifies what bypasses the tunnels. Real per-app shaping would
# have to happen on the Proxima box, inside the tunnel.
# =============================================================

/ip firewall address-list
add address=yandex.ru       list=work-sites comment="Yandex"
add address=yandex.com      list=work-sites
add address=mail.yandex.ru  list=work-sites
add address=disk.yandex.ru  list=work-sites
add address=mail.nic.ru     list=work-sites comment="Mail"
add address=nic.ru          list=work-sites
add address=zoom.us         list=work-sites comment="Video conference"
add address=google.com      list=work-sites comment="Google"
add address=gmail.com       list=work-sites
add address=docs.google.com list=work-sites
add address=telegram.org    list=work-sites comment="Telegram"
add address=whatsapp.com    list=work-sites comment="WhatsApp"
add address=whatsapp.net    list=work-sites
add address=wa.me           list=work-sites
add address=openai.com      list=work-sites comment="ChatGPT"
add address=chat.openai.com list=work-sites
add address=api.openai.com  list=work-sites
add address=1c.ru           list=work-sites comment="1C"

# ---------- Connection classification (first packet only, never overwritten) ----------
# connection-state=new + connection-mark=no-mark + passthrough=no fixes fault 2.
/ip firewall mangle
add chain=prerouting action=accept protocol=udp dst-port=500,4500 comment="QoS: skip IKE/IPsec (VoWiFi)"

add chain=prerouting action=mark-connection connection-state=new connection-mark=no-mark passthrough=no \
    protocol=udp dst-port=3478-3481,8801-8810,19302-19309,5060-5061 new-connection-mark=Kurumsal-VoIP comment="QoS: corporate VoIP"
add chain=prerouting action=mark-connection connection-state=new connection-mark=no-mark passthrough=no \
    protocol=udp dst-port=45395 new-connection-mark=Bireysel-Gorusme comment="QoS: personal calls (3478 taken above)"
# NAS rules precede the web rules, else NAS 5000/5001 lands in Genel-Web
add chain=prerouting action=mark-connection connection-state=new connection-mark=no-mark passthrough=no \
    protocol=tcp dst-address=192.168.78.122 dst-port=445,21,5000-5001 new-connection-mark=NAS-Trafik comment="QoS: to NAS"
add chain=prerouting action=mark-connection connection-state=new connection-mark=no-mark passthrough=no \
    src-address=192.168.78.122 new-connection-mark=NAS-Trafik comment="QoS: from NAS"
add chain=prerouting action=mark-connection connection-state=new connection-mark=no-mark passthrough=no \
    protocol=udp dst-port=1194,1701,4500,500,51820,5555,5556 new-connection-mark=VPN-Traffic comment="QoS: VPN udp"
add chain=prerouting action=mark-connection connection-state=new connection-mark=no-mark passthrough=no \
    protocol=tcp dst-port=1194,1723,500,4500 new-connection-mark=VPN-Traffic comment="QoS: VPN tcp"
add chain=prerouting action=mark-connection connection-state=new connection-mark=no-mark passthrough=no \
    protocol=tcp dst-port=6881-6889,5228-5230 new-connection-mark=Torrent-Cloud comment="QoS: bulk"
add chain=prerouting action=mark-connection connection-state=new connection-mark=no-mark passthrough=no \
    protocol=tcp dst-address-list=work-sites dst-port=80,443 new-connection-mark=Priority-Web comment="QoS: work sites"
add chain=prerouting action=mark-connection connection-state=new connection-mark=no-mark passthrough=no \
    protocol=tcp dst-port=80,443 new-connection-mark=Genel-Web comment="QoS: general web"

# ---------- Packet marking, per direction ----------
# Marked ONLY at the WAN edge, so a packet counts once no matter how many
# internal hops it takes through the Proxima box, and LAN-only traffic
# (client <-> NAS) never consumes the internet shaper.
add chain=prerouting action=mark-packet in-interface=ether5 passthrough=no connection-mark=Kurumsal-VoIP     new-packet-mark=VoIP-Down
add chain=prerouting action=mark-packet in-interface=ether5 passthrough=no connection-mark=Bireysel-Gorusme  new-packet-mark=Calls-Down
add chain=prerouting action=mark-packet in-interface=ether5 passthrough=no connection-mark=Priority-Web      new-packet-mark=PrioWeb-Down
add chain=prerouting action=mark-packet in-interface=ether5 passthrough=no connection-mark=Genel-Web         new-packet-mark=Web-Down
add chain=prerouting action=mark-packet in-interface=ether5 passthrough=no connection-mark=VPN-Traffic       new-packet-mark=VPN-Down
add chain=prerouting action=mark-packet in-interface=ether5 passthrough=no connection-mark=Torrent-Cloud     new-packet-mark=Bulk-Down
add chain=prerouting action=mark-packet in-interface=ether5 passthrough=no connection-mark=NAS-Trafik        new-packet-mark=NAS-Down
add chain=prerouting action=mark-packet in-interface=ether5 passthrough=no connection-mark=no-mark           new-packet-mark=Other-Down

add chain=postrouting action=mark-packet out-interface=ether5 passthrough=no connection-mark=Kurumsal-VoIP    new-packet-mark=VoIP-Up
add chain=postrouting action=mark-packet out-interface=ether5 passthrough=no connection-mark=Bireysel-Gorusme new-packet-mark=Calls-Up
add chain=postrouting action=mark-packet out-interface=ether5 passthrough=no connection-mark=Priority-Web     new-packet-mark=PrioWeb-Up
add chain=postrouting action=mark-packet out-interface=ether5 passthrough=no connection-mark=Genel-Web        new-packet-mark=Web-Up
add chain=postrouting action=mark-packet out-interface=ether5 passthrough=no connection-mark=VPN-Traffic      new-packet-mark=VPN-Up
add chain=postrouting action=mark-packet out-interface=ether5 passthrough=no connection-mark=Torrent-Cloud    new-packet-mark=Bulk-Up
add chain=postrouting action=mark-packet out-interface=ether5 passthrough=no connection-mark=NAS-Trafik       new-packet-mark=NAS-Up
add chain=postrouting action=mark-packet out-interface=ether5 passthrough=no connection-mark=no-mark          new-packet-mark=Other-Up

# ---------- Queue trees ----------
### Set for the 200 Mbit Seven Sky line, the same product SHV runs.
#
# 190M, not 200M, and the 5% is not caution - it is the whole mechanism. HTB
# can only prioritise a parent that is actually full. Set the ceiling at or
# above the real line rate and the queue never fills: packets leave as fast as
# the ISP accepts them, the buffer forms at the ISP where this router has no
# say, and priority is never consulted. QoS would appear configured and do
# nothing, which is harder to notice than QoS that is plainly off.
#
# So the two errors are not symmetrical. Too low costs bandwidth and is
# obvious. Too high costs the entire feature and is invisible.
#
# Still measure on site and correct these two numbers if the line does not
# sustain 200. Everything below is derived from them.
/queue tree
add name=Download parent=global max-limit=190M comment="95% of the 200M line - measure and correct on site"
add name=Upload   parent=global max-limit=190M comment="95% of the 200M line - lower this if upload is not symmetric"

# limit-at values sum to exactly 190M - keep that true if the roots change.
add name=VoIP-D    parent=Download packet-mark=VoIP-Down    priority=1 limit-at=20M max-limit=30M
add name=Calls-D   parent=Download packet-mark=Calls-Down   priority=1 limit-at=20M max-limit=40M
add name=PrioWeb-D parent=Download packet-mark=PrioWeb-Down priority=2 limit-at=40M max-limit=190M
add name=Web-D     parent=Download packet-mark=Web-Down     priority=3 limit-at=50M max-limit=190M
add name=VPN-D     parent=Download packet-mark=VPN-Down     priority=4 limit-at=30M max-limit=190M
add name=Bulk-D    parent=Download packet-mark=Bulk-Down    priority=5 limit-at=10M max-limit=40M
add name=NAS-D     parent=Download packet-mark=NAS-Down     priority=6 limit-at=10M max-limit=190M
add name=Other-D   parent=Download packet-mark=Other-Down   priority=8 limit-at=10M max-limit=190M

add name=VoIP-U    parent=Upload packet-mark=VoIP-Up    priority=1 limit-at=20M max-limit=30M
add name=Calls-U   parent=Upload packet-mark=Calls-Up   priority=1 limit-at=20M max-limit=40M
add name=PrioWeb-U parent=Upload packet-mark=PrioWeb-Up priority=2 limit-at=40M max-limit=190M
add name=Web-U     parent=Upload packet-mark=Web-Up     priority=3 limit-at=50M max-limit=190M
add name=VPN-U     parent=Upload packet-mark=VPN-Up     priority=4 limit-at=30M max-limit=190M
add name=Bulk-U    parent=Upload packet-mark=Bulk-Up    priority=5 limit-at=10M max-limit=40M
add name=NAS-U     parent=Upload packet-mark=NAS-Up     priority=6 limit-at=10M max-limit=190M
add name=Other-U   parent=Upload packet-mark=Other-Up   priority=8 limit-at=10M max-limit=190M

# Verify:  /queue tree print stats   - every queue should show bytes.
# A queue stuck at 0 means its mangle rule never matches - which is exactly
# where SHV's Priority-Web and NAS queues have been sitting all along.

:log warning "STAGE 5 COMPLETE - QoS active"
