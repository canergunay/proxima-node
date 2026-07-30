# =============================================================
# SVR RB4011 - STAGE 6: site interconnect (hub-and-spoke, hub = SHV)
# Run after stages 1-3. Independent of stages 4-5.
#
# This is what lets someone on ANY site LAN reach the other sites'
# NAS boxes without running a VPN client. Sites never peer with each
# other: every site holds one tunnel to the SHV hub, so bringing up
# site number N is one peer on the hub and this file on the new router.
#
# WHY THE HUB IS SHV AND NOT ERG: the backup flow is
# "site NAS -> central office NAS", so the office is already where the
# traffic converges. ERG is a home line and stays the MANAGEMENT hub only.
#
# WHY THE ENDPOINT IS THE PUBLIC IP EVEN WHILE THIS ROUTER SITS INSIDE
# THE OFFICE: a packet addressed to a router's own public address lands
# in its input chain, whatever interface it arrived on - no dstnat, no
# hairpin rule involved. So this exact line works on the bench today and
# keeps working after the router ships. Nothing to edit at handover.
#
# RE-RUNNABLE. It deletes its own objects first and rebuilds them, so running
# it on a router that is already configured leaves one of each rather than two
# - or, as it did before this was fixed, aborting on the very first line
# ("interface with such name already exists") and applying nothing at all after
# it. An `/import` stops at the first error, so a file that is not idempotent is
# a file you can only ever run once.
#
# THE INTERFACE IS NEVER RECREATED - only created if absent. Everything else is
# removed and rebuilt, but not this. RouterOS firewall rules bind to an
# interface by INTERNAL ID, not by name: delete `bc-shv` and recreate it and
# every rule that referenced it - including rules this file does not manage -
# is left pointing at an ID that no longer exists. Such a rule stays in the
# list looking almost normal; the only sign is an `I` flag and a `;;; no
# interface` line that is easy to read past. Making this file re-runnable by
# remove-and-add did exactly that to the temporary cAP rule, and the access
# points went unreachable while the chain still "looked right".
#
# Keeping the interface also means no tunnel drop at all.
#
# The removals are anchored (`^input: site interconnect`, `^forward: interconnect`)
# so they cannot reach the temporary cAP rule or anything else that happens to
# contain the word. An unanchored `~"interconnect"` already deleted an unrelated
# rule set once, in the file that advertised itself as safe to repeat.
# =============================================================

/ip firewall filter
remove [find comment~"^input: site interconnect"]
remove [find comment~"^forward: interconnect"]
/ip route
remove [find comment~"via SHV hub"]
# The peer is removed explicitly. Deleting a WireGuard interface does NOT
# delete its peers - they survive, and the next `add` fails with "entry with
# this name already exists". `/import` stops at the first error, so everything
# after that line silently never runs.
/interface wireguard peers
remove [find name=shv-hub]
/ip address
remove [find comment="SVR on site interconnect"]

# Created only when missing. MTU matches the hub's bc-wireguard (1280),
# deliberately conservative: once this router is on a real site line the path
# is unknown, and a too-large MTU surfaces as "big files hang, ping works".
# The `set` after it enforces the parameters whether the interface was just
# created or was already there.
/interface wireguard
:if ([:len [find name=bc-shv]] = 0) do={ add name=bc-shv comment="site interconnect to SHV hub" }
set [find name=bc-shv] listen-port=13231 mtu=1280

# THE PRIVATE KEY IS SET EXPLICITLY, not left for RouterOS to generate.
# Get it from ERG (`sudo cat /root/svr-mikrotik-keys.txt`) and paste it in,
# keeping the quotes - same handling as stage 3.
#
# Why it matters: if the router is reset, re-importing this file restores the
# SAME key and the hub needs no change. Let RouterOS generate its own and a
# reset silently rotates it - the interface comes up, the hub still lists the
# peer, and no handshake ever happens. Nothing reports it. That exact failure
# already cost an evening once.
set [find name=bc-shv] private-key="<bc-shv PrivateKey from svr-mikrotik-keys.txt>"

/ip address
add address=10.10.10.10/24 interface=bc-shv comment="SVR on site interconnect"

# allowed-address carries a SUPERNET on purpose. 192.168.64.0/18 covers
# 192.168.64-127, so every future site (79, 80, ...) is already permitted
# here and adding one touches only the hub. Without it each new site would
# mean editing every existing router, and the one that gets forgotten
# becomes a half-working network nobody can explain.
#
# This router's own LAN (192.168.78.0/24) is inside that /18 - harmless,
# because the connected route is more specific and longest-prefix wins,
# so local traffic never enters the tunnel.
/interface wireguard peers
add interface=bc-shv name=shv-hub \
    public-key="ex6oXafY8iShbo6QkVDkcgZUv8a+RWz/Fj2rrsKF12o=" \
    endpoint-address=46.39.245.211 endpoint-port=13231 \
    allowed-address=10.10.10.0/24,192.168.2.0/24,192.168.64.0/18 \
    persistent-keepalive=25s

# 192.168.2.0/24 is the ERG box, reached BY ITS OWN LAN ADDRESS
# (192.168.2.91) rather than a tunnel address. Deploying to ERG from a
# site must not require opening a VPN client.
#
# gateway IS THE INTERFACE, not the hub's address - the right idiom for a
# WireGuard link, and it stays correct whatever the hub is numbered.
#
# It used to be the only thing that worked. The hub sat on 10.10.10.0 until
# 2026-07-30, a network address, and RouterOS refuses to resolve a next-hop to
# one: written as gateway=10.10.10.0 these two routes were accepted, printed,
# and marked Inactive, so traffic quietly took whatever other path existed and
# everything looked fine until you checked the flags. Pointing at the
# interface sidesteps it entirely and is the right idiom for WireGuard
# anyway. From the hub side, gateway=10.10.10.<N> is fine - the asymmetry
# is only about that one .0 address.
/ip route
add dst-address=192.168.2.0/24  gateway=bc-shv comment="ERG via SHV hub"
add dst-address=192.168.64.0/18 gateway=bc-shv comment="other sites via SHV hub"

# ---------- Firewall ----------
# Anchored on the existing final drops by comment, not by rule number:
# numbers shift as rules are added and a place-before=N written today is
# wrong the moment anything else is inserted.
/ip firewall filter
add chain=input action=accept in-interface=bc-shv src-address=10.10.10.0/24 \
    comment="input: site interconnect" \
    place-before=[find comment="input: drop everything else"]
add chain=input action=accept in-interface=bc-shv src-address=192.168.2.0/24 \
    comment="input: site interconnect - ERG LAN" \
    place-before=[find comment="input: drop everything else"]

# Destination filtering, not user filtering. Who may open which share is
# the NAS's decision; the router only decides which MACHINES are reachable
# at all. A site user has no business reaching this site's printers.
#
# The NAS is the ONLY thing the interconnect reaches on this LAN. The router
# itself stays reachable through the input rules above - traffic addressed to
# the router is input, not forward, so it needs no rule here.
#
# An earlier draft also carried `src-address=10.10.10.0/29 -> full LAN` and
# the same for ERG's LAN. Both were removed deliberately. The management
# network was scoped to 10.13.13.0/24 on purpose, and a blanket rule here
# quietly opened a second, wider route to the same place - including the
# cAPs at .31-.39, which are documented as NOT reachable from ERG. Two
# overlapping paths where one is narrow by design and the other wide by
# accident is worse than either, because the wide one is the one nobody
# audits. If remote access to the cAPs is wanted, add it as ONE rule scoped
# to a single host and say so in its comment - deliberate and auditable,
# rather than convenient and invisible.
add chain=forward action=accept in-interface=bc-shv dst-address=192.168.78.122 \
    comment="forward: interconnect - the NAS, and nothing else" \
    place-before=[find comment="forward: drop everything else"]
# Anything else arriving on bc-shv falls through to the chain's own final
# drop. No extra drop rule needed here.

# Reachable by its LAN address from the interconnect and from ERG.
# 10.13.13.0/24 stays in the list: that is the emergency path, and it has
# to keep working exactly when this one does not.
/ip service
set ssh    address=192.168.78.0/24,10.13.13.0/24,10.10.10.0/24,192.168.2.0/24
set winbox address=192.168.78.0/24,10.13.13.0/24,10.10.10.0/24,192.168.2.0/24

# ---------- Verify ----------
#   /ip route print where static
#     -> BOTH must show A (active). An I here means the routes were
#        written with an unusable gateway and nothing below is meaningful.
#   /interface wireguard peers print detail where name=shv-hub
#     -> last-handshake under a minute
#   /ping 192.168.2.91 src-address=192.168.78.1 count=3
#     -> the ERG box, by its LAN address, sourced from this site's LAN
#
# Two things this cannot prove while the router still sits inside the
# office, and both mislead if you forget:
#
#   Pinging 192.168.77.x proves nothing - the WAN is on that subnet, the
#   connected /24 beats the tunnel's /18, and the traffic never leaves
#   ether5. It answers, and it answers for the wrong reason.
#
#   A ping is only a fair probe of the hub's policy while the interconnect
#   block sits ABOVE the office chain's blanket "Allow ICMP Forward". It
#   did not, at first: ping sailed through to hosts that were supposed to
#   be blocked, and the rules looked correct in isolation. Confirm order
#   with `/ip firewall filter export` on the hub and read the drop rule's
#   packet counter - a reply proves reachability, a counter proves which
#   rule decided it.

:log warning "STAGE 6 COMPLETE - site interconnect to SHV hub configured"
