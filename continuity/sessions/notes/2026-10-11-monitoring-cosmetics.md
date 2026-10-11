# 2026-10-11 — ADM Monitoring cosmetics (PROX-56 DONE)

ADM revision **e011eaeb8c4dd7ba8dd9fa22d5e0ca9f0f815c2b** committed/pushed
and deployed on ERG with Can's explicit SSH/release approval, including the
brief ADM panel-service restart. Proxima site UI remains f260a40; no site rollout.

Only `adm/frontend/src/components/MonitoringTab.tsx` changed. Baseline filters
clipped long names and history server names displaced messages; threshold fields
wrapped accidentally. Remedy: chart surfaces and1/2/3-column grids, wrapped
bounded series chips, wrapping time/actions rows, deliberate credential2-column
and threshold2-mobile/4-desktop grids,900px local history table with bounded
time/server/type columns and full wrapping messages.

All metrics/calculations/axis formatters/range hours/peak tooltip/colors/dashes/
filter-highlighting/isolation logic, settings payload/token masking, APIs/effects,
permissions and Telegram-test behavior preserved.

## Actual local verification

- ADM `npm run build` passed; en/tr/ru parity passed437 keys.
- 98 synthetic real-App cases:14baseline+84current, en/tr/ru320/390/768/1440,
  page/settings/history/hidden/isolated/range/empty. Nine series per group test
  existing ninth-series dash reuse. Hide51/isolate30 curves and168-hour GET
  verified. Threshold95 typed without saving. GET-only fixtures prohibit writes
  and Telegram tests. Inputs/buttons/non-chart text/series stroke+dash inventories
  match; document/chip/error/trial-reachability guards passed.
- Artifact `C:/Users/caner/AppData/Local/Temp/opencode/adm-monitoring-20261011-223509`.
- Harness fixes: flat SVG curve has zero geometric height, so wait for attachment;
  responsive graph width changes generated axis tick density, so compare non-chart
  text separately while retaining series-style guards. No product logic changed
  to satisfy those harness issues.
- Independent source/visual QA GREEN; current manifest hash and baseline Git blob
  match exact sources. Desktop/mobile/tablet reviewed. Tablet third chart leaves
  an intentional empty grid position. History requires local scrolling; initial
  mobile screenshots do not show every off-screen column. Build supplied, not
  rerun by reviewer. No live metrics/config-save/Telegram/authorization proof.

## Authorized publication and actual live verification

Fresh preflight captured live7414433,32 backend files,72 running Docker IDs,
protected Proxima runtime and ADM PID. Initial source-clean check classified
only `?? adm/backend/static.prev/`, the canonical generated rollback backup;
tracked source was clean. Only that exact expected artifact was allowed.

Revision-bound wrapper fetched/verified exact origin/main, allowed only the one
frontend file plus continuity docs since7414433, verified existing concurrency
guard/no active Ansible, retained stale37, then fast-forwarded and ran canonical
`adm/deploy.sh --no-pull`. Deployment output wrapper subsequently failed locally
on cp1252 encoding of a checkmark. It did not prove remote failure and deployment
was NOT rerun. UTF-8 read-only verification confirmed:

- Exact remote HEAD e011eae; ADM active and PID changed (approved restart).
- 32 ADM backend source files equal preflight manifest.
- 72 running Docker container IDs and protected ERG Proxima runtime unchanged.
- HTTP200 and matching served/local hashes for index+3 bundles on both loopback
  port5002 and public `https://adm.prxa.net`.
- `static.prev/index.html` retained; source clean except that expected backup.

Private metadata record: `/tmp/proxima-adm-monitoring-e011eae.json` (hashes/IDs,
root-private, no raw configuration). No real alert save/test or database rewrite.
KLM deferred. PROX-56 DONE/linked34; wider phases remain active. Next: ADM VPN
Users table/dialog/permission presentation review, preserving all grants/ACLs.
