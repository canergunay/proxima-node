# 2026-10-11 — ADM VPN Users cosmetics (PROX-57 DONE)

ADM revision **f1452cea863daeffa6bd81bcc950c6550754df42** committed/pushed
and deployed on ERG with Can's explicit package-specific SSH/release approval,
including the brief panel-service restart. Proxima site UI remains f260a40.

Three source files: `VpnUsersTab.tsx`, `VpnUserDialog.tsx`,
`ConfirmRevokeDialog.tsx` in `adm/frontend/src/components`. Baseline long user/
site names widened the matrix and clipped dialog site/profile/revoke text.
Remedy: bounded wrapping names/headers, pinned first identity column with scroll
padding, matched toolbar controls, wrapped errors/dialog labels and footers,
XS pending badge below full-width site label, responsive card indentation and
bounded max-peers field. First draft mobile pending badge compressed its site
label; corrected before final evidence/QA.

Original role/superadmin restrictions, sorting/filter semantics, grant/LAN/
profile/revoke handlers, field/password validation, normalization/null/empty
payloads, sync/deferred behavior, issued onboarding/copy and cancel callbacks
preserved. No backend or ACL change.

## Actual local verification

- Final ADM `npm run build` and437-key en/tr/ru parity passed.
- 112 full-App synthetic cases:16baseline+96current, en/tr/ru320/390/768/1440,
  page/search/filter/add-invalid/edit/revoke/empty/scoped. GET-only API fixtures
  prohibit account/access/password/sync writes. Scoped role has no sync-status
  request/button. Search/sort and status/site filters exercised locally.
- Artifact `C:/Users/caner/AppData/Local/Temp/opencode/adm-users-20261011-231557`.
- Matched English text/input value/type/checked/disabled/button inventories;
  chip/document/JS/forbidden-request/trial-actionability guards passed. Actual
  horizontal-scroll bounding-box checks and captures confirm pinned identity.
- Independent local source/visual QA GREEN. SHA-256 manifest matches all3 exact
  current files. Desktop/tablet/dialog and mobile scrolled matrix reviewed.
  Build supplied, not rerun by reviewer. Initial mobile screenshot does not show
  below-fold pending badge; corrected source is exact-bound to evidence.
- No real account/grant/LAN/route/revoke/ACL integration proof. Issued package/
  copy, cancellation and mutations preserved by source review, not exercised.

## Approved canonical deployment and live verification

Fresh preflight captured e011eae,32 backend files,72 running container IDs,
protected ERG Proxima runtime and ADM PID. Tracked source clean; only expected
canonical untracked `adm/backend/static.prev/` backup allowed. Revision-bound
wrapper verified no active Ansible/existing stale37 guard, fetched exactapproved
origin/main and allowed only3 frontend files+continuity docs, fast-forwarded,
then ran `adm/deploy.sh --no-pull`. UTF-8 output clean; no deployment retry.

Canonical staging build produced `index-Bbr8pbnT.js` (same local candidate name),
swapped static/static.prev, restarted ADM and reported active/HTTP200. Actual
read-only verification passed:
- Exact remote HEAD f1452ce; service active and PID changed.
- 32 backend source files unchanged.
- 72 running container IDs and protected ERG Proxima runtime unchanged.
- HTTP200/index+3 bundle hashes match on loopback5002 and public adm.prxa.net.
- Previous static index retained; source clean except expected backup.

Root-private metadata record `/tmp/proxima-adm-users-f1452ce.json`; no raw config
output or database rewrite. Historical operation37 retained. PROX-57 DONE/linked34,
wider phases active; KLM deferred. Next ADM Settings, then Admins/remaining
dialogs/docs. Native-client changes remain separate and unreleased.
