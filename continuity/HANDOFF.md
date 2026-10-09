# ADM handoff — evidence and boundaries

Reviewed October 4, 2026. This file is a small retrieval aid, not a substitute
for originals and not permission to execute historical work.

## Current product work — cosmetic web batch, 2026-10-09

**Current decision:** Can reaffirmed autonomous rollout preserving the working
current state. Restart-free static publication replaces the earlier recreation
approach. The versioned `playbooks/publish-proxima-web.yml` uses the Proxima
publisher, fresh complete snapshots and safe metadata parser; no installer,
call-home, VPN or service restart. Isolated Docker/PWA/recovery rehearsal and
independent QA passed for ERG canary. Earlier historical HostConfig attribution
remains unresolved; the new method does not modify HostConfig. Final live
publication results follow actual serial execution.

**Subsequent authorized deployment:** release **362a746** is live. Canonical
deploy script staged the new frontend, retained static.prev and restarted ADM;
service active and public HTTP 200. Served index/main-bundle hashes match files.
Proxima release **0e765b8** was pushed but is not released across sites: ERG's
web-only overlay failed runtime preservation. Exact old backend/image and 70
other container IDs were recovered, management/portal/status return 200 and DNS
works, but HostConfig differs from the initial aggregate fingerprint. Field-level
original data is unavailable; hold remaining sites and do not report full runtime
rollback. Source/auth/app builds cannot resolve that runtime evidence gap.

Subsequent read-only investigation proved the protected Config discrepancy is
unique-key Env ordering only, reproducing the exact overlay hash without changing
values; independent QA confirmed. HostConfig remains unexplained: current
settings match retained Compose/daemon source, but complete original inspect was
not saved. Retained-artifact search and36,424 bounded candidates did not reconstruct
the original. No new deployment occurred; Proxima rollout still held. Detailed
source/evidence note is in Proxima continuity/sessions/notes/2026-10-09-hostconfig-readonly-investigation.md.

Can authorized phased presentation-only implementation with separate agents and
an orchestrator. Proxima Punchlist UI parent PROX-32; P1 PROX-36, continuous QA
PROX-37. First ADM patch touches only `sx` in Dashboard/ServerCard/VpnServerCard.
Header/action wrapping, stacked groups, text/chip containment and metric shrink
preserve all state, APIs, permission checks, handlers and polling.

Production build passed before and after changes; locale parity 437 keys passed.
Independent QA accepted after correcting an introduced desktop chip-compression
regression. Fresh synthetic browser remedy evidence: 48 cases, 168 chip samples,
480 actionable button checks; no document overflow or fragmented/clipped labels.
Existing nested-button React warning remains. Full shell/auth and real backend
were excluded; no live infrastructure access or deployment occurred. Next work
is broader visual evidence and small cosmetics-only foundation/page batches.
See `sessions/notes/2026-10-09-web-ui-cosmetics.md` for artifacts and boundaries.

## Source convention

`memory/<name>:L` means the original file under
`C:\Users\caner\.claude\projects\d--Nextcloud-Projects-proxima\memory\`.
`<session>:L` means the original `<session>.jsonl` in that same project store.
Resolve either path with `scripts/continuity.py`. These are mixed historical
containers, attributed through exact cwd/structured path and import-parent
evidence, not through the store's encoded name.

## Verified locally now

- Root/repository: `D:\Nextcloud\Projects\proxima-node`,
  `canergunay/proxima-node`. HEAD `6e8baf3`; its parent is `dd780bc`.
  Initial Git status had only untracked `GOC.md`. All 196 tracked files were
  captured and remain byte-identical. No previous local continuity layout existed.
- ADM is a control plane: Ansible provisioning, node monitoring/alerts,
  site registration, VPN-account distribution and management. It is not the
  site-server data plane or the desktop VPN client. See `README.md:3–5`,
  `CLAUDE.md:3–6,66–95`. `adm/backend`, `adm/frontend`, `agent`, `roles`,
  `playbooks` and `inventory` hold the relevant implementations.
- React 19/Vite 6/MUI 6/i18next are confirmed by
  `adm/frontend/package.json:10–29`; English-default en/tr/ru requirements are
  in `CLAUDE.md:25–30`. No new mobile/formatting rule was inferred from sibling
  client notes. Deployment remains versioned and requires current authorization.
- Source checks confirm `PUSH_TIMEOUT=(5,30)`, a 60-second down-site memory and
  the `SiteGate` implementation (`adm/backend/core/proxima_client.py:33–50,179–218`).
  Pending sync retry runs in the 300-second scheduler loop
  (`adm/backend/core/scheduler.py:35,62–78`). This is source inspection, not a
  new runtime test.
- `vpn_users` and `vpn_user_access` are central account/grant data; site IDs
  differ, so remote identities must not be merged by numeric ID. ADM owns
  grants/limits, while users own their devices and may change their own login
  secret. Source: `adm/backend/core/vpn_user_sync.py:1–20,41–59,67–78,124–130`;
  historical rationale: `memory/adm-central-user-management.md:17–37`.
- Account-management scope and site-panel login access are separate powers:
  `admin_server_scope` versus `admin_server_access` (`adm/backend/core/db.py:76–112`;
  `memory/adm-panel-admins.md:18–26`). Do not conflate ADM operators, VPN users
  or local DNS device-auth users. `adm/frontend/public/docs/user-management.md:5`
  explicitly distinguishes the latter two.
- Direct grants are serialized through `allowed_profiles`
  (`adm/backend/core/vpn_user_sync.py:41–59`); an empty central list is an actual
  push payload, not "leave the site's local grants unchanged."

## Last ADM-focused human request and result

On **September 29 at 19:48:57 UTC**, Can requested fixing the synchronization
error: session `88824aa7-bbbe-47c2-bc5d-d55b7ea5d7d4:3174`, UUID
`a11aa772-568c-4ada-a77f-53238fdff40b`. The original record and its queue/parent
context were reopened during migration. The preceding report at line 3129 said
that a down site such as KLM appeared to prevent other ADM syncs.

The **dated result** is PROX-17, `dd780bc` followed by `6e8baf3`:
`memory/adm-sync-site-gate.md:11–23`. The local Git history and current code
agree on the implementation. Session lines 3412 and 3427 report revision and
deployment results. The deployment output also contains a failed ad-hoc probe
(`StopIteration`), so it is not evidence that every historical check succeeded.
The service environment issue is recorded separately below.

**Corrected diagnosis:** an early code-only explanation claimed the request
exceeded the reverse-proxy timeout and prevented healthy-site updates.
The recorded logs contradicted it: healthy sites did update, there was no NPM
504, and the measured problem was repeated 30-second waits, error messages and
the dialog remaining open. Keep the fix and the corrected explanation separate
(`memory/adm-sync-site-gate.md:18–23`; current `SiteGate` docstring).

Later historical human instructions asked to update KLM first and report before
ERG (`88824aa7-bbbe-47c2-bc5d-d55b7ea5d7d4:3534`). Subsequent "continue" messages
concerned the site-server rollout. They are neither an ADM backlog assignment
nor authorization today. No live tracker connection is available to confirm
PROX-17's current state or the next assigned task.

## Superseded instructions and operational lessons

1. **ADM deployment changed.** `CLAUDE.md:109–123` and the older
   `memory/adm-stale-source-checkout.md:47–49` describe local build + scp and
   claim no Node on the server. Current `adm/deploy.sh:3–18,60–114` builds into
   staging, swaps the UI, restarts and checks the service on the target;
   `adm/Makefile:7–11` invokes it. `memory/MEMORY.md:13` explicitly marks the
   old scp procedure obsolete. Do not execute either during this migration.
2. **Database path comes from the service.** Current `adm/adm.service:13`
   points to `/opt/erg/proxima-node/adm/data/adm.db`. The default in
   `adm/backend/core/config.py:6` points elsewhere. A September 29 ad-hoc probe
   silently read a stale empty database without the service environment
   (`memory/adm-adhoc-python-needs-service-env.md:11–21`). Production file
   existence/content was not checked now.
3. **Permanent userspace was a false implementation claim.** Can chose that
   direction on September 27 (`96ed35d2-52b3-4fbf-aea3-4a5115d1aa12:669`).
   The corrected note explains that `awg-quick` tries the kernel first and the
   environment variable only selects fallback; a later update overwrote newer
   tools. Current copy tasks use `force: false`
   (`playbooks/setup-proxima.yml:127`, `roles/mgmt-tunnel/tasks/main.yml:60`).
   Read the **correction at lines 65–73**, not just the original claim at
   lines 19–26, in `memory/adm-bare-box-callhome-userspace.md`.
4. **Stale source checkout was fixed, not merely documented.** The old "nothing
   calls refresh" observation is superseded by the hourly and startup path in
   `adm/backend/core/scheduler.py:32,42,74,81–108`; historical fix `d748a25`,
   `memory/adm-stale-source-checkout.md:34–45`.
5. **Machine-caller expiry is a distinct failure class.** Source now has renewal
   logic and a 30-day lead time (`adm/backend/core/proxima_client.py:60–112`;
   scheduler lines 43,75,111 onward). The September 20 historical note records
   recovery/alerting work, not today's credential validity. It also corrects a
   wrong sibling commit reference (`memory/adm-site-tokens-expire.md:44–55`).
   Never extract historical credentials to reconnect.
6. **Direct-profile decisions changed.** The August design requested per-device
   minting; the September 5 handoff records Can accepting user/route minting
   (`memory/direct-profiles-design.md:29–37` versus
   `memory/direct-profiles-where-we-left-off.md:56–64`). The latter also labels
   Fast-mode UI behavior as an assistant decision, not Can's approval (30–37).
   These client/server mechanisms are dependencies, not instructions to edit
   sibling workspaces. Original user-message verification for this September
   decision was not independently matched in this migration.

## Open or uncertain — confirm before assigning work

- **Claimed provisioning retry:** the September 27 note identifies no claim-aware
  retry endpoint/UI after asynchronous failure. Current update endpoint still
  calls `start_provision(..., claim=False)`
  (`adm/backend/api/vpn_servers.py:458–488`;
  `memory/adm-bare-box-callhome-userspace.md:41–49`). A comment saying the
  operator can retry is not proof this workflow is implemented.
- **Manual source refresh UI:** the backend endpoint exists
  (`adm/backend/api/vpn_servers.py:502–510`); the historical note says it was
  not connected to the UI. Hourly refresh exists. The UI-gap claim was not
  exhaustively rechecked; treat it as a candidate, not a freshly verified bug.
- **Central Direct-grant drift:** the September 5 handoff reports an empty
  ADM grant list could overwrite a local site grant on the next edit
  (`memory/direct-profiles-where-we-left-off.md:97–101`). The payload mechanism
  remains visible in source; the live rows and whether this was reconciled are
  unknown. Do not repeat the stale note's suggested account change.
- **SHV endpoint/DNS follow-up:** the September 29 note records slow resolution
  of the old public name (`memory/adm-sync-site-gate.md:29–30`). Current ADM DB
  values and today's resolution were not accessed.
- **Control-plane hosting:** the July 31 note says hosting ADM at Can's home
  was accepted temporarily and moving to office/VPS deferred
  (`memory/team-working-method.md:118–128`). This is a historical decision,
  not a verified current infrastructure inventory.
- Company-network documents were split into `bc-network` according to
  `memory/team-working-method.md:88–116`. Keep that project's decisions and
  the site/client backlog with their owners. The shared master plan is a
  dependency at `D:\Nextcloud\Projects\proximavpn\TEMP\master-plan.md`;
  it was not edited or adopted as a live ADM task queue.

## Development entry points

`adm/Makefile` defines build/install/dev/deploy. Frontend `npm run build` runs
`tsc -b && vite build` (`adm/frontend/package.json:5–8`). Backend tests are under
`adm/backend/tests`, including `test_sync_unreachable_site.py`. No application
test, frontend build or deployment ran for this history-only migration. Check
current task scope and dependencies before running product checks later.
