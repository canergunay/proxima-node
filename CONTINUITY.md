# ADM continuity — start here

## Starting from a copied folder

## Active cosmetic web work — 2026-10-09

### Deployment checkpoint — current, 2026-10-09

**Final reachable-site outcome:** ADM UI362a746 public hashes verified. Proxima
UI0e765b8 published restart-free on ERG/SHV/SVR; raw runtime/ID/StartedAt,
backend manifests and network/mount settings match fresh complete snapshots.
All management40/portal8 HTTP hashes per site and DNS checks passed. Later peer
profile-fetch timestamps advanced normally; other config semantics unchanged.

Canonical managed playbook/parser commits6e85301/4783a41/25ec5ee were pulled
without restarting ADM. SVR operation89 FAILED at metadata reporting after
successful publisher exit0; do not rewrite its status or rerun publication.
The native-stdin/Python-repr issue was reproduced and fixed with a JSON envelope.
KLM operation90 UNREACHABLE, changed0; last online2026-10-06T23:00:29Z, no live
call-home handshake. KLM remains pending, no network workaround or site mutation.
Operation37 remains unchanged. Punchlist connector unauthorized; local handoff
is current, tracker backfill pending. See the new restart-free session note.

Can subsequently authorized commit/push/deploy and SSH. ADM **362a746** is
published and deployed via `adm/deploy.sh`; service active, local/public HTTP
200. Public index and main bundle hashes match the deployed build. Previous
static output remains in `adm/backend/static.prev` for rollback. No ADM backend
product-code delta was introduced by this cosmetic release.

Proxima **0e765b8** is pushed but its rollout is blocked. ERG frontend-only canary
recovered the original backend image/files and all 70 other running container
IDs; panel/portal/status HTTP 200 and DNS NOERROR. HostConfig differs from the
initial aggregate snapshot, with no original field-level snapshot to identify
the change. Independent QA recommends holding SHV/SVR/KLM. No managed-site
publication operation was started. ADM inventory discovery also found pre-existing
operation 37 (`enable_singbox`) still marked running; it was not altered or closed.

Can authorized agent-delegated, orchestrated cosmetic changes to ADM and Proxima
web only. Punchlist Proxima UI roadmap: PROX-32, P0–P4 PROX-33/36/35/34/37.
The full portable roadmap lives in Proxima `continuity/WEB-UI-ROADMAP.md`; master
plan Section 24. Maintain this ADM handoff locally rather than importing site
runtime assumptions. Current audit found a clean pre-change tree at `a392738`.

First local ADM batch: presentation-only `sx` in Dashboard, ServerCard and
VpnServerCard. Wrapping actions, stacked card headers, readable long text/chips
and metric shrink safeguards; all handlers/API/polling/permissions retained.
Independent QA first rejected compressed desktop status labels, then accepted
the corrected batch after fresh visual checks. Pre/post production builds passed;
437 en/tr/ru keys matched. Synthetic isolated component checks covered 48 remedy
cases (eight widths, three locales, two server tabs), 168 readable chip samples,
480 successful actionability trials and no page overflow. Full app-shell/auth,
live backend and deployment behavior were not tested. Existing nested-button
console warning remains outside this cosmetic patch. No commit/push/SSH/deploy.

Next: complete evidence-led cross-page review, then page hierarchy/spacing and
dialog/matrix/monitoring/docs cosmetic batches. See the dated
[session note](continuity/sessions/notes/2026-10-09-web-ui-cosmetics.md) and HANDOFF.

Open [the session catalog](continuity/sessions/INDEX.md) to choose a conversation;
[session instructions](continuity/SESSIONS.md) explain native restoration and
cross-agent readable continuation. Project state remains in this file and HANDOFF.

Read [AGENTS.md](AGENTS.md), this file and [HANDOFF.md](continuity/HANDOFF.md).
All required startup context is local. The old archive and absolute paths below
are optional historical references; no old AI installation or sibling workspace
is needed. Extended documentation is already inside
[adm/frontend/public/docs](adm/frontend/public/docs/).

Install Node.js 22.12+ and Python 3.12. For Linux provisioning work, also use a
Linux/WSL environment with Ansible; ordinary UI/backend edits do not require
connecting to managed servers. From this copied root:

```powershell
npm --prefix adm/frontend ci
npm --prefix adm/frontend run build
python -m venv .venv
```

Activate `.venv`, then run:

```powershell
python -m pip install -r adm/backend/requirements.txt pytest
```

Run `python -m pytest` from `adm/backend/`. Frontend development uses
`npm --prefix adm/frontend run dev`: port 3002, `/api` proxy to localhost:5002.
The backend entry is `adm/backend/app.py`; use a separate local test database
configured via `ADM_DB_PATH`, not a production database/service environment.
Source maps: `adm/backend/` API/core, `adm/frontend/src/` UI, `agent/` remote agent,
`roles/` and `playbooks/` provisioning. Deployment is documented by
`adm/deploy.sh` and the correction in HANDOFF; it needs a separate current request.

No fresh-machine build/test is claimed here. Keep current decisions, real check
results and the next task in these local documents as work proceeds.

## Identity and current state

Workspace/Git root: `D:\Nextcloud\Projects\proxima-node`.
Repository: `canergunay/proxima-node`; local HEAD **`6e8baf3`**, September 29,
2026. Verified locally on October 4; no remote fetch or runtime verification.

ADM provisions and monitors exit/DPI nodes and manages Proxima site servers,
central VPN accounts and access synchronization. Python/Flask, SQLite, Ansible,
React 19, TypeScript, MUI 6 and Vite 6. Sources: `CLAUDE.md:3–6,42–62`,
`adm/frontend/package.json`, `adm/backend/core/vpn_user_sync.py`.

Read `continuity/HANDOFF.md` before resuming product work. The last ADM-focused
request was to fix synchronization when a site is unavailable. The local code
contains that fix; historical records report deployment on September 29.
Current production status is unknown. The handoff separates unfinished work,
superseded assumptions, current code and historical observations.

## Optional private original archive — old machine

`C:\Users\caner\AppData\Local\OpenCode\continuity\proxima-node-0ffefe2adcf7`

`owner.json` binds this archive to this workspace. `current.json` selects
snapshot **`20261004T171914672859Z`**. Raw originals live in SHA-256-addressed
`objects/`; manifests and the sanitized SQLite search index live under
`snapshots/<snapshot>/`. The archive has a user+SYSTEM SID allow-list and is
outside the synchronized repository. This is **not an off-site backup**.

**Migration is partial against the full GOC criteria.** All 916 manifested raw
entries are preserved and their archive hashes pass. Twelve original temporary
files disappeared after successful initial capture; their verified archived
bytes survive. Thus 904 sources still match and `verify` intentionally exits 1.
Missing older revisions/origin sessions and unverified cloud resources are
listed in `continuity/MIGRATION.md` and private `verification.json`.

## Retrieval (PowerShell, from this root; Python 3.11+)

```powershell
python scripts/continuity.py search SiteGate --session 88824aa7-bbbe-47c2-bc5d-d55b7ea5d7d4 --limit 5
python scripts/continuity.py open --source 'C:\Users\caner\.claude\projects\d--Nextcloud-Projects-proxima\88824aa7-bbbe-47c2-bc5d-d55b7ea5d7d4.jsonl' --line 3174 --context 1
python scripts/continuity.py humans 88824aa7-bbbe-47c2-bc5d-d55b7ea5d7d4 --latest --limit 10
python scripts/continuity.py resolve 'D:\Nextcloud\Projects\proxima-node\adm\backend\core\proxima_client.py' --limit 5
python scripts/continuity.py locations image --session 96ed35d2-52b3-4fbf-aea3-4a5115d1aa12 --limit 3
python scripts/continuity.py verify
python scripts/continuity_verify.py
```

Search supports SQLite FTS5 expressions. `open` requires an exact original
source path and line, verifies/reopens the raw object and emits sanitized text
with raw location/hash. Context is measured in original source lines.
`locations tool_result` locates raw tool output; `sessions` provides session
source/date/count metadata. `resolve` also uses cwd-backed relative file-history
paths. Missing results exit 1; malformed queries/operation errors exit 2.

`verify` exits 1 for source loss or integrity mismatches. The detailed verifier
currently exits 0 when archive/retrieval checks pass and the **explicitly recorded
12 source losses** are the only source differences. Its success does not mean
full GOC completion. `--record` writes a new verification report; plain retrieval
and verification are read-only. `discover`, `capture`, and `index` are explicit
archive-writing commands, not startup actions.

Redaction is best-effort and deliberately conservative. Structured sensitive
fields are withheld before flattening; multiline documents are sanitized before
line indexing. Never dump raw objects or raw settings into chat or Git.
The full mixed containers are searchable, but results carry scope labels;
`ADM-path-evidence` is path attribution, not a claim that every message under
that cwd is an ADM decision. Parent UUIDs, queue/resume records and raw metadata
are retained; imported/queued copies are not unique human conversations.

## Further reading

- `continuity/HANDOFF.md`: source-backed current/historical/uncertain context.
- `continuity/MIGRATION.md`: measured preservation, checks, limitations and files.
- `CLAUDE.md`: original project instructions, unchanged. Its scp deployment
  instructions are superseded by the checked-in `adm/deploy.sh`; see handoff.
