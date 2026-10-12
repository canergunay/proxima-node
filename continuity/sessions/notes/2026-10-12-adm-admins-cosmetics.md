# 2026-10-12 — ADM Admins published (PROX-59 READY_FOR_REVIEW)

ADM revision **14ec9cad2a4a6af3ad5ba96afdcb5bb02270a8c6** committed/pushed
and deployed on ERG with Can's package-specific SSH/publication approval,
including the brief panel-service restart. Proxima site UI remains f260a40.
Awaiting human visual confirmation; publication does not close PROX-59.

Only `adm/frontend/src/pages/Admins.tsx` changed. Baseline 320px header/action
overflow and long scope/site names hid matrix access/action columns. Remedy:
responsive header grid, bounded fixed matrix/pinned username, wrapping chips/
site headings, contained account/delete/revoke text, vertically grouped scope
checkboxes and matched dialog actions. Role/scope and panel access remain
distinct. All handlers/payloads/pending-delete/granted calculations, validation,
sync/state, issued password/copy, Back/Cancel and App menu restrictions preserved.

## Actual local checks

- ADM `npm run build` and437-key en/tr/ru parity passed.
- 112 full-App synthetic cases:16 baseline+96 current; en/tr/ru320/390/768/1440,
  page/add/edit/role/delete/revoke/empty/restricted. GET-only API fixtures prohibit
  account/access/password/sync writes. Actual `admin`/`superadmin` role values
  used; restricted admin has no Admins menu and makes no `/admins` GET.
- Artifact `C:/Users/caner/AppData/Local/Temp/opencode/adm-admins-20261012-191713`.
- Matching English text/input value/type/checked/disabled/button inventories,
  document/chip/JS/forbidden-request/trial reachability and actual-scroll pinned
  identity guards passed. TR/RU current checks are not translated baselines.
- Independent exact-source/visual QA accepted; working and snapshot Admins Git
  object `ed2f0c677514fbae92563cd51786b4bb26126c5b` match. Desktop/mobile/tablet
  and scrolled matrix reviewed. Narrow Russian role selector keeps prior
  ellipsis; extreme names make dialogs tall. No actual write, backend ACL or
  issued-package/clipboard integration proof. Build supplied, not rerun by QA.

## Approved publication and runtime-gate diagnosis

Fresh preflight captured50db405,32 backend files,72 running container IDs,
protected Proxima digest and ADM PID. Source clean except exact expected
canonical untracked static.prev backup. Revision-bound wrapper verified no
active Ansible/stale37 guard, fetched exact origin/main, allowed only Admins.tsx
plus continuity docs, fast-forwarded and ran `adm/deploy.sh --no-pull` once.
Canonical staging produced index-DNTb6Ztb.js (same local candidate name), retained
static.prev and restarted ADM; active/HTTP200 reported.

The aggregate-only runtime verifier then reported differences three times while
backend32/container72 remained equal. Failed calls retained no full inspect;
do not invent retrospective field-level evidence for each call.

Independent read-only diagnosis:
- At16:32:49UTC the protected current digest matched fresh baseline exactly.
- At16:35:52UTC four consecutive inspections returned the other digest. Lifecycle
  fields and all non-Mounts protected fields were identical; mount count was2.
- Reversing only those two complete Mounts objects exactly reproduced the fresh
  preflight digest. This proves order-sensitive hashing of equivalent mount
  metadata explains the alternating observations; no particular Docker-internal
  implementation or Proxima restart is claimed.
- Docker's bounded event query returned no Proxima events in16:20–16:32:49;
  current StartedAt remained2026-10-10. Absence alone is not a restart proof.

Temporary verifier fix (`adm_monitoring_live.py` in the approved local temp
directory): future `mounts-unordered-v1` hashes sort ONLY complete Mounts objects;
duplicates/counts and every other protected field remain strict. Aggregate-only
legacy baselines use bounded Mounts permutations (maximum6) to reconstruct the
EXACT original digest, rather than overwrite/bless a baseline. Unknown schema
and out-of-bound reordered legacy snapshots fail closed. Original private
record `/tmp/proxima-adm-admins-14ec9ca.json` was not replaced.

Independent delivery-test wrote only temporary `adm_runtime_guard_test.py` and
ran `python -B` on it:12 unittest methods PASS. Covered reorder equivalence,
add/remove/duplicate-count/all fixture mount attributes, other protected fields/
State/PID/StartedAt, nested changes, strict Env order, no input mutation, bounded
legacy reconstruction, unknown schemas and import/identity behavior. Tested
guard SHA-256 `d91579772336c8df0a028b3a5d38d1de26adcc0891f866c728c04c91b2352fe7`.
These are guard tests, not real-server tests.

## Final actual read-only result

Corrected verifier passed exact14ec9ca, active ADM/approved PID change,32 backend
files/72 running IDs/protected ERG Proxima runtime, HTTP200/index+3 bundle hashes
on loopback5002 and publicadm.prxa.net, and retained previous static index.
Final runtime comparison was `legacy_exact` against the original fresh baseline.
No redeploy/restart/rollback/config work was used to resolve verification.

PROX-59 remains READY_FOR_REVIEW for Can's header/matrix/scope/dialog visual
confirmation. PROX-58 and native review/input waits are unchanged. Wider phases
active; KLM deferred; next remaining ADM server dialogs/docs. Native changes
remain separate/unreleased. Product code did not change during gate diagnosis.
