# Vendored AmneziaWG files

Where these came from, so nobody has to guess later.

| File | sha256 (first 16) | Source |
|---|---|---|
| `awg` | `1a34b3d16bdc1ea3` | amneziawg-tools v1.0.20210914, Debian 12 build, taken from ERG's `/usr/bin/awg` |
| `awg-quick` | `f4bb0f5d63665ade` | same build; a shell script, no linkage |
| `awg-quick@.service` | `2da3e450b12d14e1` | the unit that ships with those tools |

They are vendored rather than installed from a package because there is no
apt repository for AmneziaWG on Debian, and ERG's own copy was hand-built with
no package trace. 144 KB total, so the repository can carry them.

**`amneziawg-go` is deliberately not here.** It is the userspace
implementation, 5.9 MB, and every exit node already has a working build of it
inside the `amnezia-awg2` container. The role extracts it locally instead —
no repository bloat, no download at provision time, and it is the exact binary
already proven on that host and architecture.

Note the split that cost an hour to find: the `awg` CLI **inside the
container** is musl-linked for Alpine and will not run on a Debian host
(`cannot execute: required file not found`). Only `amneziawg-go` is
statically linked and portable. So the CLI comes from here and the daemon
comes from the container.

Sites need it too — and at a moment when nothing else can provide it. On a
bare box the call-home tunnel comes up *before* the installer builds the
kernel module, and there is no container to take a userspace build from.
`playbooks/setup-proxima.yml` therefore extracts `amneziawg-go` once from the
`proxima-awg-client` image on the ADM host into `cache/` (gitignored) and
pushes it. Found on KLM, 2026-09-27; the earlier sentence here ("sites carry
the module already") described boxes that had been provisioned on plain
WireGuard first.

Two corrections from the same evening:

- **The tunnel is not "userspace permanently".** `awg-quick` tries the kernel
  module first and runs `amneziawg-go` only when `ip link add` fails and
  `/sys/module/amneziawg` is absent; `WG_QUICK_USERSPACE_IMPLEMENTATION`
  names the fallback, it cannot force it. On a site whose module loads the
  call-home is a kernel interface; after a kernel update the module cannot
  follow, the same unit comes up in userspace. That fallback is the recovery
  property, and it is enough.
- **The vendored `awg` is v1.0 and must never overwrite a newer one.** A box
  with the 3.1 module has the 3.1 CLI beside it (the installer builds both
  from one pinned release). Copying v1.0 over it and restarting the unit
  produced `Unable to modify interface: Invalid argument` and took ADM's
  only path to the box down mid-run. Both copy tasks now use `force: false`.
