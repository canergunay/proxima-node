# 2026-10-10 — ADM Dashboard publication and managed SVR rollout

Can requested incremental publication and explicitly authorized required SSH.
ADM7bd28ef7c309fe46573a886889554597ca26a19d is committed/pushed/live through
the canonical staging/swap/restart deployment. Service active; public index and
three bundles match deployed SHA-256. No backend product-code delta. Previous
UI retained privately under `/var/lib/proxima-adm-web-releases/7bd28ef7c309fe46573a886889554597ca26a19d/`.

Proxima0a8b7ea577245a6c371b8bc9280f0b5db838020f published restart-free on
ERG/SHV/SVR; SVR ADM web_ui_release operation91 DONE. Optional preceding-snapshot
argv and JSON envelope tested with real controller Ansible; syntax check passed.
Metadata9 and wrapper10 tests passed. Initial system-Python wrapper attempt failed
imports before creating an operation; service `adm/backend/venv/bin/python`
succeeded. Current process/environment were read directly; no historical secrets.
Operation37 unchanged, bounded local stale guard only; historical89/90 unchanged.
KLM not attempted.

Actual Linux/Docker repeated-release/rollback and warm service-worker rehearsal,
independent canary/live QA and all-site runtime/backend/static/DNS checks passed.
Details and exact three private snapshots live in Proxima's corresponding note.
Fresh user-requested14:01–14:02UTC checks passed deployment invariants and ADM
public identity/operation status. Alternate existing SSH paths were needed:
SHV direct, ERG through SHV, SVR through SHV→ERG; no network changes.

Later user/runtime configuration differs from publication snapshots. SHV's two
new peers and ERG's one new peer correlate with authenticated self-service logs
and enabled owner accounts. SHV group-slot/client-version and ERG owner/slot
changes are observed but exact attribution remains separate. Preserve current
state; do not claim perpetual byte equality or roll it back to old snapshots.

Next: remaining UI batches, each published incrementally after local acceptance.
Deployment tracker comments were subsequently backfilled successfully to
PROX-32/35/37 after Can reported Connected and fresh reads confirmed access.
No further live deployment or server check in that tracker reconciliation.
No broad all-product/client/device/security claim from this deployment evidence.
