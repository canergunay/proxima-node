# proxima-node documentation

Operating Proxima's **server nodes** — the VPN exit servers and DPI bypass
boxes provisioned from this repository.

| | |
|---|---|
| [server-types.md](server-types.md) | What each node type runs, and which playbook builds it |
| [adding-new-server.md](adding-new-server.md) | Provisioning a new node end to end |
| [provider-notes.md](provider-notes.md) | VPS providers — what works from Russia, what to avoid |
| [usage-scenarios.md](usage-scenarios.md) | Day-to-day operational procedures |

---

## Moved: the company network documentation

The Bureau Construction site infrastructure — the standard, the subnet
registry, the MikroTik build runbook and its `.rsc` stage files, the
interconnect and the access matrix — **left this repository on 2026-07-31**.

It is now at
**[bureau-construction/bc-network](https://github.com/bureau-construction/bc-network)**,
with its commit history.

| Was | Now |
|---|---|
| `docs/Proxima Çoklu Sunucu INFRASTRUCTURE.md` | `INFRASTRUCTURE.md` |
| `docs/site-router/` | `site-router/` |

It was moved because the two describe different things for different readers.
This repository is a product: it provisions Proxima's own servers. The other
describes one company's private network — its addresses, its open ports, and who
can reach what. Keeping them together meant a single grant of access handed over
both, in whichever direction you did not intend.
