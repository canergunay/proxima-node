# =============================================================
# SVR RB4011 - STAGE 4: CAPsMAN for cAP ac (RBcAPGi-5acD2nD)
# Run after stages 1-2. Requires <TODO_WIFI_PSK> to be filled in below.
#
# PRE-FLIGHT: confirm the router uses the legacy wireless driver, not wifi-qcom:
#   /system package print      -> "wireless" should be enabled
# If this router ships with wifi-qcom-ac instead, STOP - this whole file is the
# wrong stack and the commands do not exist.
#
# SVR uses ONE stack. SHV runs legacy /caps-man and the new /interface wifi
# capsman side by side with 14 stale cap interfaces; that duplication is the
# most confusing thing in its config and is not reproduced.
#
# WPA3 is not available here - the legacy stack is WPA2-PSK only. SHV's ax
# units run wpa2-psk,wpa3-psk. Accepted consequence of the cAP ac purchase.
# =============================================================

### FILL THIS IN BEFORE RUNNING
:global wifipsk "<TODO_WIFI_PSK>"

### BENCH vs SITE - read this.
# This router is built inside the office, where "Buro" and "Buro_5G" are the
# LIVE office networks. If the cAPs broadcast those names here, office phones
# and laptops associate with a network that routes nowhere.
#
# So the bench uses temporary names. Everything that matters is still tested:
# the cAPs adopt into CAPsMAN, get provisioned, take the channel plan, and a
# phone can actually associate using the real passphrase.
#
# The names below are the ONLY thing that changes before shipping. See the
# "BEFORE SHIPPING" block at the end of this file.
:global ssid24 "Buro-BENCH"
:global ssid5  "Buro-BENCH-5G"

# The RB4011's own radios stay off - the cAPs provide all coverage. SHV has
# them running standalone as SSID "Buro" AND registered to caps-man, a
# contradictory double role.
/interface wireless set [find] disabled=yes

/caps-man manager
set enabled=yes
/caps-man manager interface
add disabled=no interface=bridge1

# 2.4 GHz: 20 MHz, channels 1/6/11 - the three non-overlapping ones.
# 5 GHz: 20 MHz on UNII-1 -> FOUR clean channels (36/40/44/48), no DFS.
#   With up to 8 cAPs this beats 40 MHz. 40 MHz doubles per-client throughput
#   but leaves only two non-DFS channels, so APs 3+ share spectrum and every
#   client on both pays. Steel container walls give excellent isolation, so
#   reusing four channels across non-adjacent containers costs almost nothing.
#   DFS (52-140) would add channels but brings a 60s silent CAC at boot and
#   lets a radar event move an AP mid-workday.
/caps-man channel
add name=ch-2ghz band=2ghz-b/g/n control-channel-width=20mhz extension-channel=disabled frequency=2412,2437,2462
add name=ch-5ghz band=5ghz-a/n/ac control-channel-width=20mhz extension-channel=disabled frequency=5180,5200,5220,5240

/caps-man security
add name=svr-security authentication-types=wpa2-psk encryption=aes-ccm group-encryption=aes-ccm \
    passphrase=$wifipsk

# local-forwarding=yes: each cAP bridges client traffic locally instead of
# tunnelling it back to the router. Less CPU on the RB4011, better throughput.
/caps-man datapath
add name=svr-datapath bridge=bridge1 client-to-client-forwarding=yes local-forwarding=yes

# The final SSIDs match the office deliberately, so staff moving between sites
# join automatically. Sviridova and the office never overlap physically, so the
# names cannot collide once this router is on site.
#
# THAT MAKES THE PASSPHRASE NON-OPTIONAL: same SSID must mean same passphrase.
# If SVR's differs from the office's, every phone that has ever joined "Buro"
# will auto-connect at the site, fail authentication and retry - which reads to
# the user as "the Wi-Fi is broken", not "wrong password". Set $wifipsk above to
# the office's existing passphrase, not a new one.
/caps-man configuration
add name=svr-2ghz channel=ch-2ghz datapath=svr-datapath security=svr-security \
    ssid=$ssid24 mode=ap country=russia installation=indoor
add name=svr-5ghz channel=ch-5ghz datapath=svr-datapath security=svr-security \
    ssid=$ssid5 mode=ap country=russia installation=indoor

# Radios match by capability, so any number of cAPs provision themselves with
# no per-unit config. name-format=identity means radios appear as
# "svr-cap-01-1" rather than cap1..capN - with 8 units that is the difference
# between a readable radio list and SHV's cap1..cap20 soup.
/caps-man provisioning
add action=create-dynamic-enabled hw-supported-modes=gn master-configuration=svr-2ghz name-format=identity comment="2.4 GHz radios"
add action=create-dynamic-enabled hw-supported-modes=ac master-configuration=svr-5ghz name-format=identity comment="5 GHz radios"

# Roaming assist: kick clients below -85 dBm so they re-associate to a closer
# cAP. Left DISABLED - tune after a coverage walk. Too aggressive a threshold
# on a site with thin coverage locks people out entirely.
/caps-man access-list
add action=reject signal-range=-120..-85 disabled=yes comment="enable after site survey"
add action=accept signal-range=-84..120  disabled=yes comment="enable after site survey"

:global wifipsk
:global ssid24
:global ssid5
:log warning "STAGE 4 COMPLETE - CAPsMAN ready on BENCH SSIDs"

# =============================================================
# BEFORE SHIPPING - switch to the real SSIDs.
#
# Run these two lines once the router is ready to be boxed, or on site. Do NOT
# run them while the router is still powered up inside the office: the moment
# they take effect the cAPs start advertising the same names as the office
# network, and nearby devices will associate with the wrong one.
#
#   /caps-man configuration set [find name=svr-2ghz] ssid=Buro
#   /caps-man configuration set [find name=svr-5ghz] ssid=Buro_5G
#
# Confirm, then power the kit down:
#   /caps-man configuration print where name~"svr-"
#
# Nothing else changes. The passphrase, channels, datapath and provisioning
# were all proven on the bench with the temporary names.
# =============================================================

# =============================================================
# PER-cAP: run ON EACH cAP ac, not on the RB4011.
# Reset the unit first (hold reset until the LED flashes, or
# /system reset-configuration no-defaults=yes skip-backup=yes), then paste,
# changing NN per unit (01, 02, 03 ...):
#
#   /system identity set name=svr-cap-NN
#   /interface bridge add name=bridgeLocal
#   /interface bridge port add bridge=bridgeLocal interface=ether1
#   /interface bridge port add bridge=bridgeLocal interface=ether2
#   /ip dhcp-client add interface=bridgeLocal disabled=no
#   /interface wireless cap set enabled=yes bridge=bridgeLocal \
#       interfaces=wlan1,wlan2 discovery-interfaces=bridgeLocal
#   /system clock set time-zone-name=Europe/Moscow
#   /ip service set telnet disabled=yes
#   /ip service set ftp disabled=yes
#   /ip service set www disabled=yes
#
# Both ether ports go in the bridge: each cAP ships with its own power adapter
# so PoE is not needed, but ether2 lets one cAP pass Ethernet to the next
# container instead of running a second cable to the rack. A daisy chain shares
# one uplink and a mid-chain failure takes out everything downstream - fine for
# 2-3 units, not for a long run.
#
# PORT BUDGET: the RB4011 has 9 LAN ports after WAN. 8 cAPs + Proxima box + NAS
# is already 10 devices, before printers or PCs. A LAN switch is required at
# this scale, or the cAPs must be chained.
#
# Discovery is L2 broadcast on bridge1, so no manager address is needed while
# the cAP is on the same segment. Verify on the RB4011:
#   /caps-man radio print               - every radio listed and provisioned
#   /caps-man registration-table print  - clients per radio, with signal
#
# Then pin each lease (APs live at .31-.39):
#   /ip dhcp-server lease make-static [find host-name="svr-cap-NN"]
#   /ip dhcp-server lease set [find host-name="svr-cap-NN"] address=192.168.78.3N comment="cAP ac NN"
# =============================================================
