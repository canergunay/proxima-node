# 2026-10-11 — ADM Settings cosmetics (PROX-58 READY_FOR_REVIEW)

ADM revision **50db4053ca61b81da128f085276b3a12253eb759** committed/pushed
and deployed on ERG with Can's explicit package-specific SSH/release approval,
including the brief panel-service restart. Proxima site UI remains f260a40.

Only `adm/frontend/src/pages/Settings.tsx` changed. Baseline long password
rejection text clipped. Remedy: deliberate unequal desktop language/password
columns within a900px page, single-column narrow layout, header divider/back40px,
bordered cards/responsive padding/headings, wrapped alerts and40px Save action
that fills its mobile card. All password mismatch/request/state/reset/disabled/
loading/back and language/localStorage behavior preserved.

## Actual local verification

- ADM `npm run build` and437-key en/tr/ru parity passed.
- 55 full-App synthetic cases:10baseline+45current, en/tr/ru320/768/1440,
  empty/filled/mismatch/rejected/language. Exact fake-password PUT rejection
  only; mismatch triggerszeroPUT, rejectiononePUT. Language change and
  `adm_lang` storage checked. Matched text/input/control-disabled inventories,
  message-clipping/document/JS/forbidden-request/actionability guards passed.
- Artifact `C:/Users/caner/AppData/Local/Temp/opencode/adm-settings-20261011-234311`.
- Independent bounded-page source/visual QA GREEN. Current Settings Git object
  and baseline HEAD blob match snapshot sources. Supplied build/parity/flow
  results not independently rerun. Whole-App manifests differ beyond Settings,
  so this is not a controlled whole-App regression claim. No real password
  change, successful session or server-side authorization proof.

## Approved canonical publication and actual checks

Fresh preflight captured f1452ce,32 backend source files,72 running container IDs,
protected ERG Proxima runtime and ADM PID. Source clean except exact expected
canonical untracked static.prev backup. Revision-bound wrapper verified no
active Ansible/stale37 guard, fetched exact origin/main, allowed onlySettings.tsx
plus continuitydocs, fast-forwarded and ran `adm/deploy.sh --no-pull`. No retry.

Canonical staging produced index-DJH8cdrt.js (same local candidate name), retained
static.prev, restarted ADM and reportedactive/HTTP200. Fresh read-only checks:
- Exact remote HEAD50db405; active service/PID changed.
- 32 backend source files and72 running container IDs unchanged.
- Protected ERG Proxima raw runtime unchanged.
- Loopback5002/publicadm.prxa.net index+3bundle HTTP200/hash match.
- Previous static index retained; source clean except expected backup.

Private metadata record `/tmp/proxima-adm-settings-50db405.json`; no raw config
output/database rewrite. Historical37 retained. PROX-58 READY_FOR_REVIEW/linked34; broader
phases active; KLM deferred. Next ADM Admins, then remainingdialogs/docs;
native-client work remains separate and unreleased.

## Updated human-review workflow

After publication Can requested READY_FOR_REVIEW for approval/answer/verification
waits. PROX-58 was moved from DONE to that status; publication remains verified.
Awaiting his visual confirmation of desktop card hierarchy, mobile stacking,
labels and errors. No real password change is needed to review this cosmetic
patch. Future batches should distinguish machine QA, publication and human
acceptance. Exact tracker readback confirmed PROX-2/30/58 READY_FOR_REVIEW;
native changes unreleased and LAN-only root cause unconfirmed.
