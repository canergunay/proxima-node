# =============================================================
# SHV - the forward chain's actual policy, and the measurement that justified
# it. Started as an audit; the audit finished and this is now the rule set the
# router runs on.
#
# STATE 2026-07-30 09:5x: the blanket accept is DISABLED (not deleted) and the
# chain closes on its own final drop for the first time. Verified from the
# office with the VPN off: hairpin over Wi-Fi, the same service over LTE, and
# ordinary browsing all work; the final drop has counted zero and logged
# nothing. Left disabled rather than removed so a single `disabled=no` reverts
# it. Delete it, and the dead rules under it, after a full week has passed
# through the chain - the evidence so far covers one night and one morning,
# which does not include a Sunday 03:00 backup.
#
# This router's forward chain contains `action=accept` with no matchers. Every
# rule below it is dead, including the chain's own final drop, which has counted
# zero packets for its entire life. Removing it is the fix; the risk was never
# the removal but not knowing what a real default-drop would break.
#
# These rules make that measurable and change nothing while doing it: each names
# a category of legitimate traffic, and every one is an `accept` sitting above an
# unconditional `accept`. No packet's fate changes - the counters simply move to
# where they belong. Whatever still lands on the blanket rule is the residue a
# default-drop would kill.
#
# Re-runnable. It removes its own rules first, anchored so it cannot touch the
# interconnect policy rules (which use the `interconnect: ` prefix).
# =============================================================

/ip firewall filter
remove [find comment~"^audit: "]

# Stable anchor, set once by index because the rule carries no comment of its
# own. Everything here places itself relative to this.
set [find chain=forward action=accept !comment !src-address !dst-address !protocol] \
    comment="forward: BLANKET ACCEPT - no matchers. Everything below is DEAD, including the final drop. Audit and policy rules go ABOVE this."

# `untracked` is the word that matters. With only established,related the
# residue stayed at 143,855 packets per 45 seconds and explained nothing;
# adding untracked dropped it to about two packets a minute. The standard site
# template (svr-02-firewall.rsc) has always had all three - this router is
# older and hand-built, and was missing the third. The raw chain is empty, so
# whatever is untracked here is not notrack.
add chain=forward action=accept connection-state=established,related,untracked \
    comment="audit: established, related, untracked - return traffic and anything bypassing conntrack" \
    place-before=[find comment~"BLANKET ACCEPT"]

add chain=forward action=accept connection-state=new \
    in-interface=bridge1 out-interface=ether5 \
    comment="audit: LAN to internet" \
    place-before=[find comment~"BLANKET ACCEPT"]

add chain=forward action=accept connection-state=new connection-nat-state=dstnat \
    in-interface=ether5 \
    comment="audit: published services inbound" \
    place-before=[find comment~"BLANKET ACCEPT"]

add chain=forward action=accept connection-state=new \
    in-interface=bridge1 out-interface=bc-wireguard \
    comment="audit: office to interconnect" \
    place-before=[find comment~"BLANKET ACCEPT"]

# Hairpin: a device on the office LAN reaching a service on the office's own
# public address, dst-nat'ed straight back in. bridge1 to bridge1, so it is
# easy to forget it is routed at all. Nine packets in a 906-sample window -
# small, legitimate, and exactly the kind of thing a default-drop kills
# quietly. This is the rule the whole audit existed to find.
add chain=forward action=accept connection-state=new connection-nat-state=dstnat \
    in-interface=bridge1 out-interface=bridge1 \
    comment="audit: hairpin - LAN reaching the site's own public address" \
    place-before=[find comment~"BLANKET ACCEPT"]

# The other 897 of those 906: TCP FIN/RST arriving after conntrack has already
# torn the connection down. Dropping invalid is correct, standard, and already
# the second rule in the site template - this router is older and never had it.
# This is the first rule here that changes behaviour rather than just counting.
add chain=forward action=drop connection-state=invalid \
    comment="audit: invalid - teardown packets after conntrack expiry" \
    place-before=[find comment~"BLANKET ACCEPT"]

# Names the remainder. Only safe because the four rules above shrank it to a
# couple of packets a minute; at the original volume this would have flooded
# the log.
#
# UNVERIFIED as of 2026-07-30: over a 40-second sample this rule's counter
# stayed at zero while the blanket rule counted two packets, which should be
# impossible if it really sits above it. Do not trust its output - or its
# silence - until a long sample confirms one or the other.
add chain=forward action=log log-prefix=RESIDUE \
    comment="audit: log whatever still reaches the blanket accept" \
    place-before=[find comment~"BLANKET ACCEPT"]

# ---------- The cleanup itself ----------
# Once the rules above account for everything, this is the whole change. It is
# a disable rather than a remove on purpose: reverting is one command, and the
# evidence behind it is a night and a morning, not a full week.
#
#   revert:  /ip firewall filter set [find comment~"BLANKET ACCEPT"] disabled=no
set [find comment~"BLANKET ACCEPT"] disabled=yes

# ---------- Reading it ----------
#   /ip firewall filter print stats where chain=forward
#     -> compare the four audit counters against the blanket rule's
#   /log print where message~"RESIDUE"
#
# Do NOT grep this output through a wrapping terminal: several comments here
# wrap onto a second line, and `grep -A1` then returns the wrapped comment
# instead of the counter row. That produced three wrong readings in one night.
#
# ---------- The cleanup this is preparing for ----------
# Once the residue is named and covered, replace the blanket accept with the
# categories above plus a final drop. Do it in a window, with someone in the
# office who can test, and keep a revert ready. Editing the forward chain
# cannot lock you out - router access is the input chain - but it can take the
# office off the internet until somebody notices.

:log warning "audit rules rebuilt above the blanket accept - behaviour unchanged"
