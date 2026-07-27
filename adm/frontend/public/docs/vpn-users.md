# VPN Users & Access

VPN user accounts — the credentials people type into the ProximaVPN client — are defined once in ADM and pushed down to the Proxima instances they are authorized on. This document covers where accounts live, who owns which field, how access is granted and revoked, and what changed for the Proxima instances themselves.

> **Not to be confused with Device Auth.** Proxima also has a per-device authentication feature for DNS Mode, which decides whether a device on the local network gets VPN routing. That is a different subsystem with its own table (`users`) and is documented in **Device Auth (DNS Mode)**. This page is about `vpn_users` — the accounts used by the ProximaVPN client.

---

## Why central

Each Proxima instance used to keep its own user list. With one site that is fine; with several it means the same person is created by hand on each one, their password drifts apart between sites, and there is nowhere to answer "who has access to what".

Accounts now live in ADM:

```
ADM                                Proxima instances
  vpn_users        ──── push ───→    vpn_users  (read-only replica)
  vpn_user_access                    peers      (unchanged, still local)
```

ADM is the only writer for account identity. The instances hold a replica so that **login never leaves the server**.

---

## Authentication stays local

This is the property that matters most operationally: a user logs in against the Proxima instance they are connecting to, using that instance's own copy of the password hash. ADM is not in the authentication path.

If ADM is down, or unreachable, or being upgraded:

- every existing user can still log in, on every site
- every client can still fetch its profile
- every tunnel keeps running

What you lose while ADM is down is the ability to *change* things — create a user, grant a site, reset a password. Those queue up and apply when it returns.

---

## Who owns what

Both sides legitimately write, so the boundary is explicit:

| ADM owns | The user owns |
|---|---|
| whether the account exists | their own devices (peers) |
| which servers they are authorized on | device names |
| per-server limits (max devices, quota, speed) | their own password |
| LAN access policy | |
| enabled / disabled | |

Peers were never contested — ADM does not touch them. The password is the one field both sides can write, and it is handled specially (see below).

---

## The access matrix

The Users page in ADM is a matrix: one row per person, one column per site.

```
Kullanıcı ⇅        Durum ⇅         ERG ⇅          SHV ⇅
[search    ] ✕     [All      ▾] ✕  [All     ▾] ✕  [All     ▾] ✕

can.ergunay        ● Enabled       ✓  🖧          ✓  🖧
kerem.ergunay      ● Enabled       ✓  🖧          ○  ⊘
```

Each cell has two controls:

- **left** — authorized on this server or not
- **right** — may this person's devices reach that site's LAN

Clicking a name opens the detail dialog for per-server limits. Every column sorts and carries its own filter; the site filters accept several options at once, OR-ed together, so "not authorized" + "LAN blocked" lists everyone who cannot reach that site's LAN by either route.

---

## Per-server, not global

Limits are attached to the **authorization**, not to the person. The same user can have three devices at one site and one at another, LAN access at the office and none at the home server.

This is not a convenience — group ids and quotas are site-local and have no meaning across sites, so a single global value would be wrong wherever it was not set.

---

## LAN access

Whether a user's devices can reach the devices on a site's local network is a per-user-per-site policy, set from the matrix.

It used to be a per-device flag, but nobody ever used that granularity — across both live sites every peer allowed LAN access and no user had devices that disagreed. What was actually needed was "can this person reach that site's LAN", which is what the matrix now answers.

New devices inherit their owner's policy, so a user cannot escape a restriction by creating another device. Changing the policy re-applies it to every device they already have.

Enforcement is an iptables DROP rule per device address, in a dedicated `PROXIMA_LAN` chain. The chain matters: rules placed directly in `FORWARD` were being buried by the interface's own `PostUp` rules on restart, which silently *unblocked* restricted users. The scheduler re-asserts the chain's position every five minutes.

---

## Passwords

**The admin sets them.** Creating a user asks for a password; the response shows a copy-paste block with the address, username and password for each authorized site. ADM stores only a hash and cannot show a password again later — a forgotten one is replaced, not recovered.

**Users may change their own** from the client. This is why the push treats the password differently from every other field: it is only sent when ADM's copy is newer than the last one delivered. Otherwise an admin nudging a peer limit would silently restore the password the user had just replaced.

**An admin reset wins.** Setting a new password in ADM bumps its timestamp, so the next push carries it to every site.

**Changes propagate between sites.** A user who changes their password on one site would otherwise be left with two different passwords. ADM compares when each site last had one set and copies the newest hash to the rest — moving the password without ever learning it. This runs on the scheduler and does nothing when the sites already agree.

**Granting a new site uses the password they actually have.** ADM's stored hash may be the one the admin issued months ago. A new authorization is seeded by copying the live hash from a site the user already has, so their current password works immediately.

---

## Granting and revoking

Granting is a single click in the matrix. The account is created on that instance and the user can log in with the credentials they already use elsewhere.

**Revoking deletes the remote account together with its devices.** This is deliberate and the dialog says so plainly: a WireGuard peer keeps carrying traffic on its own keys after its owner is gone, so leaving the devices behind would revoke the access in name only.

To suspend someone without destroying their devices, disable the account instead.

A revocation issued while a site is unreachable is not lost — it stays queued and applies when the site returns.

---

## Sync

Every change is pushed immediately and the result is reported. A push that fails does not fail the request: an unreachable site must not block editing the central record. The row stays pending, the page shows a badge, and the next sync re-drives it.

A failure keeps the *intent*, which matters most for revocations — a queued removal must still be a removal when the site comes back, not a forgotten one.

---

## Administrators

Two roles:

| | Superadmin | Server admin |
|---|---|---|
| VPN users on own servers | ✓ | ✓ |
| Servers, provisioning, monitoring | ✓ | — |
| Managing administrators | ✓ | — |

A server admin sees only the sites in their scope and only the people on them. Because an account is global while authorization is per-site, they may only change identity fields — password, enabled, deletion — for users who belong exclusively to their own sites. Someone who also appears on a site they cannot see is out of reach.

Roles and scope are read on every request rather than carried in the token, so disabling an operator takes effect immediately. The last superadmin cannot be demoted, disabled or deleted.

---

## What changed on the Proxima instances

The Proxima web UI no longer creates, edits, deletes or shares VPN users — two writers for one record is how records drift. What remains is everything peers need: devices are still grouped by owner, and the owner selector when adding a peer reads from the local replica.

The reversible password store was removed at the same time. It existed so the panel could reveal a password to an admin; with that gone it was a plaintext copy of every user's password sitting in the database for no reason. It is no longer written on any path, and the stored values were purged from the live servers.

---

## Summary

- Accounts are defined in ADM and replicated to the sites they are authorized on
- Login is always local; ADM being down affects management, never access
- ADM owns the account and the authorization; the user owns their devices and their password
- Limits and LAN policy are per-site, because that is the only level at which they mean anything
- Revoking removes the devices too, because otherwise it removes nothing
- Failed pushes keep their intent and retry rather than being lost
