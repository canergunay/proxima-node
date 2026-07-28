# SVR site router — build guide (MikroTik RB4011)

This builds the router for a new site, on a bench, before anything ships.
Everything is copy-and-paste. You do not need to know RouterOS.

Work through it top to bottom. Do not skip ahead: several steps close doors
behind you, and the order is what keeps you from being locked out.

**Time:** about 90 minutes, plus whatever the firmware update takes.

---

## 0. What you need before you start

| | |
|---|---|
| The router | MikroTik RB4011, still in the box or freshly reset |
| A laptop | Windows, with an Ethernet port or a USB-Ethernet adapter |
| One Ethernet cable | Laptop to router. Not Wi-Fi. Not through a switch. |
| WinBox | Download from https://mikrotik.com/download |
| The five `.rsc` files | The ones sitting next to this file |
| Two secrets from ERG | See step 6. Get them before you begin. |
| The Wi-Fi password | Your choice. You will type it into a file in step 7. |

**Why the direct cable matters.** Step 3 wipes the router completely: no IP
address, no password, no network. The only way back in is WinBox connecting to
the router's MAC address over a directly attached cable. Through a switch or
over Wi-Fi that does not work, and the router stays unreachable until somebody
presses the physical reset button.

---

## 1. Connect to the router for the first time

1. Plug the cable into **ether1** on the router and into your laptop.
2. Plug in the router's power. Wait about a minute for it to boot.
3. Open WinBox.
4. Click the **Neighbors** tab. Your router appears in the list after a few
   seconds.
5. Click the **MAC Address** row — not the IP address. The MAC looks like
   `48:A9:8A:...`. Clicking the MAC is what makes this work later, when the
   router has no IP at all.
6. Login: `admin`. Password: empty. Click **Connect**.

If nothing appears in Neighbors: check the cable is in ether1, turn off your
laptop's Wi-Fi, and click refresh.

---

## 2. Update the firmware

Do this **before** the reset. It needs internet, and after the reset the router
has none.

Give the router internet temporarily: put a cable with a working internet
connection into **ether5**.

Open **New Terminal** in WinBox and paste these one at a time:

```
/system package update check-for-updates
```

Wait until it prints a version. Then:

```
/system package update install
```

The router reboots. Reconnect (Neighbors → MAC), then:

```
/system routerboard upgrade
```

Then:

```
/system reboot
```

Reconnect, and check the version:

```
/system resource print
```

**Target: 7.22.1** — what the other sites run. A different version is not
fatal, but tell Can before continuing. Matching versions is what stops one site
behaving differently from another for no visible reason.

While you are here, check the wireless driver:

```
/system package print
```

Look for a line saying `wireless`. If you see `wifi-qcom` or `wifi-qcom-ac`
instead, **stop and tell Can.** Step 7 is written for the older driver and none
of its commands exist on the new one.

---

## 3. Wipe the router

This removes everything, including the default configuration MikroTik ships
with — which would otherwise fight every setting you are about to apply.

```
/system reset-configuration no-defaults=yes skip-backup=yes
```

The router reboots and your connection drops. **This is expected.**

Wait a minute, then reconnect: **Neighbors → click the MAC address → Connect**.
Username `admin`, no password.

The router now has no IP address at all. Only the MAC connection works.

---

## 4. Give your laptop a fixed address

Do this before loading anything. The router is about to start handing out DHCP
addresses, and it deliberately points those clients at a machine that does not
exist yet. With a fixed address you are unaffected.

Windows: Settings → Network → Ethernet → IP assignment → Edit → Manual → IPv4
on.

| Field | Value |
|---|---|
| IP address | `192.168.78.5` |
| Subnet mask | `255.255.255.0` |
| Gateway | `192.168.78.1` |
| Preferred DNS | `8.8.8.8` |

Save. This adapter will have no internet until the router's WAN is up. That is
fine — everything below is local.

---

## 5. Load stages 1 and 2

### Upload the files

In WinBox, click **Files** in the left menu. Drag all five `.rsc` files from
your laptop into that window. They appear in the list.

### Stage 1 — addresses, DHCP, DNS, clock, failsafe

Open **New Terminal** and paste:

```
/import svr-01-base.rsc
```

It prints a line per command and ends with `STAGE 1 COMPLETE`.

**If it stops with an error**, it names the line that failed, and nothing after
that line was applied. Fix the line and run the same file again — the earlier
commands will complain that things already exist, which is harmless.

The router is now at `192.168.78.1`. Check:

```
/ip address print
```

You should see `192.168.78.1/24` on `bridge1` and `10.13.13.11/24` on `wg-erg`.

Confirm the clock is right — certificates and tunnels both depend on it:

```
/system clock print
```

### Stage 2 — firewall

**Read this before running it.** This stage closes the router to everything
except the LAN and the management tunnel. Run from the WAN side and you lock
yourself out. You are on the LAN side (ether1), so you are fine.

```
/import svr-02-firewall.rsc
```

Ends with `STAGE 2 COMPLETE`.

Check you are still connected, and that the rules are in:

```
/ip firewall filter print
```

The last rule of the `input` chain must be `drop`. If WinBox disconnects and
will not come back, connect by MAC again — that path is deliberately left open
from the LAN.

---

## 6. Stage 3 — the management tunnel

This is what lets the router be reached after it ships, without depending on
anything at the site being configured correctly.

### Get the two secrets

They live on ERG and nowhere else:

```
ssh erg
sudo cat /root/svr-mikrotik-keys.txt
```

You get a **PrivateKey** and a **PresharedKey**. Do not paste them into chat.

### Put them in the file

Edit `svr-03-wireguard.rsc` on your laptop with Notepad, replace the two
placeholders, save, then drag the file into WinBox again and overwrite.

| Placeholder | Replace with |
|---|---|
| `<PrivateKey from svr-mikrotik-keys.txt>` | the PrivateKey value |
| `<PresharedKey from svr-mikrotik-keys.txt>` | the PresharedKey value |

Keep the quotation marks around them.

### Run it

```
/import svr-03-wireguard.rsc
```

### Check it worked

```
/interface wireguard peers print detail
```

Look at `last-handshake`. It should be a few seconds old, and should keep
resetting. Then:

```
/ping 10.13.13.1 count=4
```

Four replies means the tunnel is up and the router is remotely manageable.

**No handshake?** Almost always one of three things, in this order: a character
lost while pasting the keys; the router has no internet yet (`/ping 8.8.8.8`);
the connection blocks outbound UDP 51820.

---

## 6a. Stage 6 — the site interconnect

This is the tunnel that lets people at this site reach the other sites'
NAS boxes without running a VPN client on their laptop. It is separate
from stage 3: that one is for *managing* the router, this one is for
*users*. Neither depends on the other.

**Two sides, and the other side comes first.** The office router (the
hub) has to be told about this router before this file will do anything.
Send Can the public key created by the first command below, wait for
confirmation, then continue.

```
/import svr-06-interconnect.rsc
```

Now read out the public key and send it to Can:

```
/interface wireguard print detail where name=bc-shv
```

### Check it worked

First, and this is the one people skip:

```
/ip route print where static
```

Both routes must show **A** for active. An **I** means inactive — the
route is listed, looks correct, and does nothing. Stop and tell Can if
you see one.

```
/interface wireguard peers print detail where name=shv-hub
```

`last-handshake` should be a few seconds old.

```
/ping 192.168.2.91 src-address=192.168.78.1 count=3
```

Three replies means a machine on this site's network can reach the
server at the Moscow house. That is the real test.

**What this does not prove, while the router is still in the office:**
pinging anything on `192.168.77.x` from here tells you nothing. This
router's WAN cable is plugged into that same network, so the traffic
goes out the WAN and never touches the tunnel. It answers, and it
answers for the wrong reason.

---

## 7. Stage 4 — Wi-Fi

Only if this site has MikroTik cAP access points.

Edit `svr-04-capsman.rsc`, replace `<TODO_WIFI_PSK>` with the Wi-Fi password,
save, upload again, then:

```
/import svr-04-capsman.rsc
```

Plug the access points into any LAN port. They take their configuration from
the router automatically — give them two or three minutes, then:

```
/caps-man remote-cap print
```

Each access point should be listed.

---

## 8. Stage 5 — traffic shaping

This is set for the site's 200 Mbit line, the same product the other office
runs, so you can run it on the bench:

```
/import svr-05-qos.rsc
```

Ends with `STAGE 5 COMPLETE`.

**Confirm the line on site anyway.** The number comes from the contract, not
from a measurement. If the line turns out slower, the ceiling has to come down
— and if upload is not also 200 Mbit, its ceiling is a separate number. Both
are two lines at the top of the queue section.

Getting it wrong is not symmetrical. Too low and you lose bandwidth, which
somebody notices. Too high and the shaper never engages at all: the queue
never fills, priority is never consulted, and QoS looks configured while doing
nothing. That is the one to be careful about.

Once the site is live, check every queue is actually being used:

```
/queue tree print stats
```

A queue sitting at zero bytes means its rule never matches anything — which is
exactly the state two of the other office's queues have been in since they
were written.

---

## 9. Save the result

```
/system backup save name=svr-baseline
/export file=svr-baseline
```

In WinBox → Files, drag both files onto your laptop and keep them. The
`.backup` restores the router exactly; the `.rsc` export is readable and shows
what was set.

---

## 10. After the router: the Proxima box

The box is installed remotely from ADM — nothing on it is built by hand. Once
the router is in place and the box is plugged into it, ADM's "Set up new
server" does the rest, and the install log is shown while it runs.

One part of the box does need a person, and only once the site's line is live:
the reverse proxy's certificates and its four service names. That is a
separate short guide, [npm-setup.md](npm-setup.md).

---

## 11. What is left for the site

These need the real internet line and cannot be done on the bench:

- **Confirming the line rate**, and correcting stage 5's two ceilings if the
  200 Mbit does not hold.
- **Hairpin NAT** — the commented block at the end of stage 2. Without it a
  phone *inside* the site cannot reach the VPN on the site's public address.
  VPN profiles use a bare IP by design, so DNS cannot paper over it.
- **Static leases** for the Proxima box and the NAS. Until those are set they
  take whatever DHCP offers, and the addresses below are intended rather than
  guaranteed.

---

## The site's addresses

| Address | What |
|---|---|
| `192.168.78.1` | the router |
| `192.168.78.10-30` | DHCP pool, general devices |
| `192.168.78.31-39` | access points, fixed leases |
| `192.168.78.121` | the Proxima box |
| `192.168.78.122` | the NAS |
| `10.13.13.11` | the router, on the management tunnel |

The DHCP pool stops at `.30` on purpose. Everything above is reserved, and a
pool running past `.121` would let a laptop take the address the whole site
depends on.

---

## What is reachable from the internet

| Port | Goes to | For |
|---|---|---|
| UDP 5555 | `.121` | ProximaVPN (AmneziaWG) |
| UDP 5556 | `.121` | sing-box wg2 |
| TCP 8443 | `.121` | sing-box VLESS/Reality |
| TCP 80 | `.121` | certificate issuance |
| TCP 443 | `.121` | the site's web services |

Nothing else. The router itself accepts connections only from the LAN and from
the management tunnel.

---

## Names

Static DNS entries on the router, so they work inside the site whether or not
anything external is set up:

| Name | Points at |
|---|---|
| `svr.fs-bc.net` | NAS web interface |
| `svr-p.fs-bc.net` | Proxima panel |
| `svr-d.fs-bc.net` | dashboard |
| `svr-n.fs-bc.net` | NAS, direct file access |

**The VPN has no name and must not be given one.** A DNS record would tell
anyone examining the domain that a VPN exists here and where it is. Clients use
the site's bare IP. This is a deliberate decision, not an oversight.

---

## If you get locked out

1. **WinBox by MAC** — Neighbors tab, direct cable. Works with no IP at all.
2. Failing that, hold the physical **reset button** while powering on until the
   LED flashes. The router returns to defaults and you start again from step 1.
   Nothing is lost: everything is in these files.
