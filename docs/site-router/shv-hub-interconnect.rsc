# =============================================================
# SHV RB4011 - HUB side of the site interconnect: POLICY
# The office router is the hub. Every site holds one tunnel to it and
# none to each other, so bringing up site number N is one peer here plus
# the site's own stage-6 file - and no existing router is touched.
#
# Re-runnable: it drops its own rules first and rebuilds them, so running
# it twice leaves the same five... seven rules, not fourteen. Per-site
# peers are NOT in here (see the end of the file) - rebuilding policy must
# never take a site's tunnel down with it.
#
# ADDITIVE towards everything else. It removes nothing pre-existing.
# That is deliberate: this chain carries a bare `action=accept` with no
# matchers near the bottom, which leaves every rule below it dead -
# including its own final drop. Cleaning that up is a separate job for a
# maintenance window with someone in the office. Until then, rules that
# must actually bite have to sit ABOVE it.
# =============================================================

# ---------- Ordering ----------
# Three ways to place these rules were tried; two of them are accepted by
# RouterOS and do nothing at all:
#
#   place-before=0,1,2,3,4          each N is resolved against the list as
#                                   it stands at that moment, so the rules
#                                   interleave with the existing ones
#                                   instead of stacking
#   move [find ...] destination=N   silent no-op
#   move numbers=[find ...] dest=N  silent no-op - this chain's print
#                                   numbers are not sequential, so every
#                                   move resolved to its own slot
#
# What works is add + place-before against ONE stable anchor: each insert
# lands immediately before it, so the adds stack in written order.
#
# The anchor is "Allow ICMP Forward", not the Turkcell rule above it: that
# comment contains a slash (UDP 500/4500) and an unquoted slash inside a
# find expression truncates the match silently - the same trap already
# documented from the netwatch failsafe, which looked healthy and did
# nothing for weeks.
#
# Residual: the Turkcell rule (udp 500/4500, any->any) therefore stays
# above this block, so a site can reach any office host on those two
# ports. IKE only, and it goes away with the bare-accept cleanup.

/ip firewall filter
# Anchored with ^ on purpose. A bare ~"interconnect" also matches the audit
# rule commented "audit: office to interconnect", so re-running this file -
# the one thing it advertises as safe - would silently delete part of a
# different rule set.
remove [find comment~"^interconnect: "]

add chain=forward action=accept in-interface=bc-wireguard \
    connection-state=established,related \
    comment="interconnect: established" \
    place-before=[find comment="Allow ICMP Forward"]

# The ERG box (.2) and the admin's own peer (.3), named as a range rather
# than a /29 with room for four more addresses nobody would notice being
# added. Site routers live at .10+ and are outside it. Without this rule ERG
# loses the office Proxima box at 192.168.77.121 and the deploy path closes.
add chain=forward action=accept in-interface=bc-wireguard \
    src-address=10.10.10.2-10.10.10.3 \
    comment="interconnect: ERG box and admin peer - deploy path, named hosts only" \
    place-before=[find comment="Allow ICMP Forward"]

add chain=forward action=accept in-interface=bc-wireguard \
    src-address=192.168.2.0/24 \
    comment="interconnect: ERG LAN, full" \
    place-before=[find comment="Allow ICMP Forward"]

# 192.168.77.10 is the office Synology. Sites get this and nothing else.
# This filters DESTINATIONS, not people: which shares a person may open is
# the Synology's decision and stays there. The router only decides which
# machines are reachable at all, which is why a site can reach the NAS and
# not the office printers.
add chain=forward action=accept in-interface=bc-wireguard \
    dst-address=192.168.77.10 \
    comment="interconnect: sites reach the NAS only" \
    place-before=[find comment="Allow ICMP Forward"]

add chain=forward action=drop in-interface=bc-wireguard \
    dst-address=192.168.77.0/24 \
    comment="interconnect: sites reach nothing else on the office LAN" \
    place-before=[find comment="Allow ICMP Forward"]

# Deploying to ERG from a site must not require opening a VPN client, so
# the box is reachable by its own LAN address rather than a tunnel one.
# Scoped to the single host: the rest of that LAN is a home network and
# was explicitly left out of scope.
add chain=forward action=accept in-interface=bc-wireguard \
    dst-address=192.168.2.91 \
    comment="interconnect: sites reach the ERG box only" \
    place-before=[find comment="Allow ICMP Forward"]

add chain=forward action=drop in-interface=bc-wireguard \
    dst-address=192.168.2.0/24 \
    comment="interconnect: sites reach nothing else on the ERG LAN" \
    place-before=[find comment="Allow ICMP Forward"]

# Site-to-site traffic (192.168.78.x -> a future 192.168.79.x) transits
# this hub and is deliberately not policed here: the DESTINATION site's
# own router is the enforcement point, exactly as this office is for
# itself. One place per destination, so the rule and the thing it
# protects stay together.

# ---------- NAT: site-bound traffic keeps its real source ----------
# This chain ends in a matcher-less `masquerade out-interface=bc-wireguard`,
# which rewrote EVERY packet leaving the tunnel to this router's own
# 10.10.10.0. Two things followed from that, one merely annoying and one fatal:
#
#   - source-based rules on a spoke could never match, because every packet
#     arrived from the same address whoever sent it
#   - a reply addressed BACK to 10.10.10.0 could not be forwarded across the
#     tunnel by the spoke, so nothing behind a site router was reachable from
#     here at all. Requests arrived and were accepted; replies vanished with no
#     drop counter anywhere. The hub could reach a site's ROUTER and nothing
#     behind it.
#
# The fourth time this router's legacy .0 address caused a silent failure. The
# proper fix is to give it a normal host address; this rule is the narrow one
# that does not touch a working production address.
#
# Scoped to the site range, so office->internet (out ether5) and office->ERG
# (192.168.2.x, outside the /18) keep masquerading exactly as before.
/ip firewall nat
remove [find comment~"sites keep their real source"]
add chain=srcnat action=accept dst-address=192.168.64.0/18 \
    out-interface=bc-wireguard \
    comment="srcnat: sites keep their real source - must precede the blanket masquerade" \
    place-before=[find comment~"blanket masquerade"]

# The anchor exists because `[find out-interface=bc-wireguard]` returns nothing
# in the NAT chain - it is accepted and matches no rule, so place-before gets an
# empty value and the add fails with "no such item". The blanket masquerade was
# given a comment once, by index, purely so this file never has to guess an
# index again.

# ---------- Adding site number N ----------
# Not part of this file - run it once, by hand, when the site's router is
# built. Everything else already permits 192.168.64.0/18, so no existing
# router needs touching:
#
#   /interface wireguard peers
#   add interface=bc-wireguard name=<site>-site \
#       public-key="<from the new router>" \
#       allowed-address=10.10.10.<N>/32,192.168.<LAN>.0/24 \
#       persistent-keepalive=25s
#   /ip route
#   add dst-address=192.168.<LAN>.0/24 gateway=10.10.10.<N> \
#       comment="<site> site via interconnect"
#
# No endpoint-address on this side: the site dials the hub, never the
# reverse. That is what makes a site behind CGNAT or a renumbering ISP
# work with no DSTNAT and nothing to update when its address changes.
#
# The site side uses gateway=bc-shv rather than this hub's address. That is
# the right idiom for a WireGuard link regardless, but it also used to be the
# only thing that worked: this hub sat on 10.10.10.0 until 2026-07-30, and
# RouterOS refuses a network address as a next-hop, leaving such routes
# Inactive without complaint. The hub is 10.10.10.1 now. From here, pointing
# at 10.10.10.<N> is fine and always was.

:log warning "HUB INTERCONNECT POLICY applied"
