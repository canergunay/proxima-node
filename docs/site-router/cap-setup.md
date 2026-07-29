# Access point setup — svr-cap-02 … svr-cap-08

Seven units, one procedure each: **plug in → reset → paste.**

`svr-cap-01` is already done (`192.168.78.31`).

---

## Do I need to join each access point's Wi-Fi?

**No. Not at any stage.** You reach the access point over the cable:

```
Laptop ──ethernet──> SVR router ──ethernet──> cAP (ether1)
```

All three sit on the same layer-2 segment, so WinBox finds the access point in
the **Neighbors** tab by MAC address. No IP, no Wi-Fi, no password needed.

The Wi-Fi the access point broadcasts (`Buro-BENCH`) exists only for the final
phone test. It is not part of the setup.

---

## The loop, per unit

1. Power the access point, run a cable from **its ether1** to any LAN port on
   the router (ether1–4 or 6–10)
2. WinBox → **Neighbors** → click the access point's **MAC address** → Connect
   (user `admin`, empty password)
3. Paste the two blocks below in order
4. Tell Claude "cap-0N ready" — adoption gets verified and the lease pinned

**Which one is the new access point?** Unconfigured units show up with identity
`MikroTik` and model `RBcAPGi-5acD2nD`. Ones already done appear under their own
name, `svr-cap-01` and so on, so they cannot be confused.

**The connection drops after the reset.** That is expected. Wait a minute,
refresh Neighbors, reconnect to the same MAC.

---

# cAP 02

**Block 1 — reset:**
```
/system reset-configuration no-defaults=yes skip-backup=yes
```

Reconnect by MAC, then:

**Block 2 — configure:**
```
/system identity set name=svr-cap-02
/interface bridge add name=bridgeLocal
/interface bridge port add bridge=bridgeLocal interface=ether1
/interface bridge port add bridge=bridgeLocal interface=ether2
/ip dhcp-client add interface=bridgeLocal disabled=no
/interface wireless cap set enabled=yes bridge=bridgeLocal interfaces=wlan1,wlan2 discovery-interfaces=bridgeLocal
/system clock set time-zone-name=Europe/Moscow
/ip service set telnet disabled=yes
/ip service set ftp disabled=yes
/ip service set www disabled=yes
```
→ will be pinned to `192.168.78.32`

---

# cAP 03

```
/system reset-configuration no-defaults=yes skip-backup=yes
```
```
/system identity set name=svr-cap-03
/interface bridge add name=bridgeLocal
/interface bridge port add bridge=bridgeLocal interface=ether1
/interface bridge port add bridge=bridgeLocal interface=ether2
/ip dhcp-client add interface=bridgeLocal disabled=no
/interface wireless cap set enabled=yes bridge=bridgeLocal interfaces=wlan1,wlan2 discovery-interfaces=bridgeLocal
/system clock set time-zone-name=Europe/Moscow
/ip service set telnet disabled=yes
/ip service set ftp disabled=yes
/ip service set www disabled=yes
```
→ will be pinned to `192.168.78.33`

---

# cAP 04

```
/system reset-configuration no-defaults=yes skip-backup=yes
```
```
/system identity set name=svr-cap-04
/interface bridge add name=bridgeLocal
/interface bridge port add bridge=bridgeLocal interface=ether1
/interface bridge port add bridge=bridgeLocal interface=ether2
/ip dhcp-client add interface=bridgeLocal disabled=no
/interface wireless cap set enabled=yes bridge=bridgeLocal interfaces=wlan1,wlan2 discovery-interfaces=bridgeLocal
/system clock set time-zone-name=Europe/Moscow
/ip service set telnet disabled=yes
/ip service set ftp disabled=yes
/ip service set www disabled=yes
```
→ will be pinned to `192.168.78.34`

---

# cAP 05

```
/system reset-configuration no-defaults=yes skip-backup=yes
```
```
/system identity set name=svr-cap-05
/interface bridge add name=bridgeLocal
/interface bridge port add bridge=bridgeLocal interface=ether1
/interface bridge port add bridge=bridgeLocal interface=ether2
/ip dhcp-client add interface=bridgeLocal disabled=no
/interface wireless cap set enabled=yes bridge=bridgeLocal interfaces=wlan1,wlan2 discovery-interfaces=bridgeLocal
/system clock set time-zone-name=Europe/Moscow
/ip service set telnet disabled=yes
/ip service set ftp disabled=yes
/ip service set www disabled=yes
```
→ will be pinned to `192.168.78.35`

---

# cAP 06

```
/system reset-configuration no-defaults=yes skip-backup=yes
```
```
/system identity set name=svr-cap-06
/interface bridge add name=bridgeLocal
/interface bridge port add bridge=bridgeLocal interface=ether1
/interface bridge port add bridge=bridgeLocal interface=ether2
/ip dhcp-client add interface=bridgeLocal disabled=no
/interface wireless cap set enabled=yes bridge=bridgeLocal interfaces=wlan1,wlan2 discovery-interfaces=bridgeLocal
/system clock set time-zone-name=Europe/Moscow
/ip service set telnet disabled=yes
/ip service set ftp disabled=yes
/ip service set www disabled=yes
```
→ will be pinned to `192.168.78.36`

---

# cAP 07

```
/system reset-configuration no-defaults=yes skip-backup=yes
```
```
/system identity set name=svr-cap-07
/interface bridge add name=bridgeLocal
/interface bridge port add bridge=bridgeLocal interface=ether1
/interface bridge port add bridge=bridgeLocal interface=ether2
/ip dhcp-client add interface=bridgeLocal disabled=no
/interface wireless cap set enabled=yes bridge=bridgeLocal interfaces=wlan1,wlan2 discovery-interfaces=bridgeLocal
/system clock set time-zone-name=Europe/Moscow
/ip service set telnet disabled=yes
/ip service set ftp disabled=yes
/ip service set www disabled=yes
```
→ will be pinned to `192.168.78.37`

---

# cAP 08

```
/system reset-configuration no-defaults=yes skip-backup=yes
```
```
/system identity set name=svr-cap-08
/interface bridge add name=bridgeLocal
/interface bridge port add bridge=bridgeLocal interface=ether1
/interface bridge port add bridge=bridgeLocal interface=ether2
/ip dhcp-client add interface=bridgeLocal disabled=no
/interface wireless cap set enabled=yes bridge=bridgeLocal interfaces=wlan1,wlan2 discovery-interfaces=bridgeLocal
/system clock set time-zone-name=Europe/Moscow
/ip service set telnet disabled=yes
/ip service set ftp disabled=yes
/ip service set www disabled=yes
```
→ will be pinned to `192.168.78.38`

---

## Address book

| Unit | Address |
|---|---|
| svr-cap-01 | 192.168.78.31 ✅ |
| svr-cap-02 | 192.168.78.32 |
| svr-cap-03 | 192.168.78.33 |
| svr-cap-04 | 192.168.78.34 |
| svr-cap-05 | 192.168.78.35 |
| svr-cap-06 | 192.168.78.36 |
| svr-cap-07 | 192.168.78.37 |
| svr-cap-08 | 192.168.78.38 |

Leases are pinned from the router side. Nothing to do on the access point.

---

## How many can be connected at once?

All of them — the router has 9 LAN ports after the WAN, so eight fit. But going
one at a time is easier: eight devices called `MikroTik` in the Neighbors list
is how you lose track of which one you have already configured.

Better: configure a unit, give it its name, unplug it, plug in the next. Report
each one as it is done and its lease gets pinned — then that unit is ready to be
boxed.

Unplugging removes the unit from `/caps-man radio print` on the router. That is
expected; the configuration lives on the access point itself, not on the router.

---

## Once all eight are done

Handled from the router side — just say when you are ready:

- Verify every lease is pinned
- `/user print` — account and password check
- Backup: `/system backup save` + `/export file=`
- **Last of all:** switch to the real SSIDs (`Buro` / `Buro_5G`), immediately
  before the kit is powered down — never while it is running in the office
