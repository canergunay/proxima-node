# SVR site router — build log

MikroTik RB4011iGS+5HacQ2HnD, serial-tracked as `svr-rb4011`.
Built on the bench at the office (SHV), 2026-07-27 → 2026-07-29.

---

## Final verified state

Captured live from the router 2026-07-29 19:00, over the management tunnel.

| | |
|---|---|
| RouterOS | 7.22.2 (stable), ARM, `wireless` package present |
| Identity | `svr-rb4011` |
| LAN | `192.168.78.1/24` on `bridge1` (ether1–4, 6–10) |
| WAN | `ether5`, DHCP client, currently `192.168.77.165` (office) |
| Management | `10.13.13.11/24` on `wg-erg`, tunnel up |
| DHCP pool | `192.168.78.10–30`, 15 min lease |
| Users | `can` (full), `admin` deleted |
| SSH key | ERG's `id_rsa_mikrotik` imported for `can` |
| device-mode | `scheduler=yes`, `romon=yes` |

### Stages applied

| Stage | Status |
|---|---|
| 1 — base | ✅ complete (see "the reset" below) |
| 2 — firewall | ✅ 12 filter rules, 6 NAT rules |
| 3 — call-home tunnel | ✅ verified from both ends |
| 4 — CAPsMAN | ⬜ not re-applied since the reset |
| 5 — QoS | ⏸ deliberately parked until the line is measured |

### What is proven working

- **Call-home tunnel** — handshake confirmed from both sides; ERG pings
  `10.13.13.11` at ~6.5 ms. Survived a cold reboot unaided.
- **Netwatch failsafe, both directions** — verified by test *and* in production:
  after the reboot, `proxima-dhcp-failover` fired on its own
  (`run-count=1`, `18:59:11`) and DHCP now hands out `.1` because `.121` does
  not exist yet. The restore direction was proven earlier by temporarily adding
  `192.168.78.121` to the router: netwatch went `up`, `proxima-dhcp-restore`
  ran, DHCP returned to `.121`.
- **Reboot survival** — cold power cycle: NTP corrected the clock within a
  minute, the WireGuard tunnel re-established itself, all config persisted.
- **CAPsMAN with a real access point** — `svr-cap-01` adopted, both radios
  provisioned (2.4 GHz ch 1, 5 GHz ch 44), a phone and a laptop associated and
  received `192.168.78.x` with gateway and DNS pointing at `.121`. This is the
  DNS Mode handoff SHV never actually implemented.

---

## Bugs found and fixed

All four were **silent** — the configuration looked healthy while doing nothing.
All four are now corrected in the stage files, so no future site inherits them.

### 1. `/ip dhcp-client` has no settable `name`

`name=wan1` was rejected outright (`expected end of command`). SHV's export
contains `name=client1` because RouterOS *displays* an auto-assigned name — it
just cannot be set. Fixed by removing the parameter; the entry is identified by
its interface.

### 2. `[find address=...]` silently matches nothing inside a script

The netwatch failover script read
`/ip dhcp-server network set [find address=192.168.78.0/24] ...`.
Inside a script body `/` starts a command path, so the value is cut at
`192.168.78.0`, the filter matches no record, and `set` on an empty list is a
**silent no-op** — while the `:log` line after it still runs.

The result: netwatch reported `status=down`, the log showed
`PROXIMA DOWN — DHCP handed back to router`, and DHCP never changed. Everything
looked correct. Typing the same filter **quoted** at the terminal works, which
is why manual testing was misleading.

Fixed by dropping the filter entirely — there is only ever one DHCP network on
this router. If a second is ever added, filter by comment, never by an unquoted
address prefix.

### 3. Netwatch cannot run a script without `dont-require-permissions=yes`

`policy=read,write,test,policy` on the script is **not sufficient**. With
`dont-require-permissions=no`, netwatch calls the script and nothing happens:
no error, no log line, `run-count` does not increment.

The same script run by hand worked perfectly — so *"I tested it manually and it
worked" proves nothing here*. Verification must read `run-count` and
`last-started`, not the log.

Netwatch also only fires on a **state change**. To re-test while already `down`,
disable and re-enable the entry.

### 4. `/system scheduler add` is blocked by device-mode

On a fresh RB4011, RouterOS 7 refuses `/system scheduler add` with
`not allowed by device-mode`. Stage 1 stops there and everything below it is
skipped. Unlocking requires **physical** confirmation — power cycle or reset
button — so it cannot be automated or done remotely.

Now README **step 2b**, before the wipe.

---

## The reset, 2026-07-29

The router was reset mid-build. Nothing was lost: the staged files reproduced it
in about twenty minutes, and the rebuild was **better** than the original,
because bugs 2 and 3 had been fixed in the files rather than patched live.

The rebuild exposed two further failure modes:

- **Stage 1 stopped right after creating `wg-erg`**, so the WAN client, DHCP
  server, netwatch and DNS never applied. Diagnosed from ERG, then completed
  remotely with `svr-01-remainder.rsc`.
- **A WireGuard handshake succeeds with no IP address on the interface.** The
  peer showed a healthy handshake while nothing was reachable — because
  `10.13.13.11/24` was missing. Handshake is pure crypto; data needs an address.
  This is now the fourth item in the README's troubleshooting list.

---

## Operational knowledge worth keeping

**The RB4011 has no battery-backed clock.** Every power loss returns it to the
firmware build date. WireGuard stamps each handshake and ERG rejects one older
than the newest it has seen from that peer — so a backwards clock kills the
management tunnel until NTP corrects it. Two independent recovery paths are
configured: NTP (`time.cloudflare.com`, `pool.ntp.org`) and
`/ip cloud update-time=yes`. Verified self-healing within a minute of the WAN
coming up. If it ever does not, the manual recovery is on the ERG side —
remove and re-add the peer to clear the stored timestamp.

**The peer endpoint is a hostname and resolves once.** If DNS is unconfigured
when the peer is created, RouterOS caches the failure and never retries. Fix
DNS, then bounce the peer with disable/enable.

**Netwatch waits 5 minutes after boot** before its first probe
(`status=unknown`). Normal — it avoids flapping while the network settles.

**WinBox from the WAN side will never work**, by design: the input chain drops
everything arriving on `ether5`, and `/ip service` restricts `winbox` and `ssh`
to `192.168.78.0/24` and `10.13.13.0/24`. A timeout there looks exactly like a
rejected password. There is no login lockout in RouterOS by default.

**Access from ERG** — `ssh svr-mt` from ERG resolves to `10.13.13.11` using
`~/.ssh/id_rsa_mikrotik`. Works from anywhere ERG can reach, and will keep
working at the site: the tunnel address does not depend on Seven Sky's IP.

---

## What remains

**On the bench**

- Re-apply stage 4 (CAPsMAN) — wiped by the reset
- Set the Wi-Fi passphrase (office passphrase; SSIDs match the office)
- Configure access points `svr-cap-02` … `08` and pin leases `.32`–`.38`
- `/system backup save` + `/export file=` and pull both off the router
- **Last action before power-down:** switch SSIDs from `Buro-BENCH` /
  `Buro-BENCH-5G` to `Buro` / `Buro_5G` (README step 8a)

**At the site, needs Seven Sky**

- Confirm delivery matches SHV — a static address handed out over DHCP
- Hairpin NAT (commented block in stage 2) — needs the public IP
- Stage 5 QoS — only after the line rate is measured
- Static leases for the Proxima box and NAS

**Open decision**

Extending the management tunnel to carry `192.168.78.0/24` would let the site
LAN be managed from ERG — required for Claude to configure the access points
directly, and roughly what ADM will need for central site management. It widens
what Section 11 deliberately kept narrow, so it is a deliberate choice, not a
default.
