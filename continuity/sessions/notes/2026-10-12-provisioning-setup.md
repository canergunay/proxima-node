# 2026-10-12 — Provisioning/setup (PROX-64 READY_FOR_REVIEW)

ADM **c2abe671701bb3e08ca3a169894c4e6c46279e43** published with Can's
package-specific commit/push/SSH and panel-restart approval. Only ProvisionDialog
and SetupVpnServerDialog changed: two-column desktop provisioning/one-column
mobile, matched footer/error layout, setup heading emphasis and wrapped taken-range
chips. Existing Setup Grid preserved. Registration→provision sequence, bodies,
normalization/password handling, loading/disabled/close/reset/callbacks, polling
and finished-state logic retained. EditServerDialog untouched.

Lean local checks: build437-key parity, two baseline/four isolated-dialog scenarios
(desktop Provision, RUmobile Provision, desktop Setup with scrolled range capture,
RUmobile running Setup), brief independent exact-source QA. Fake subnetsGET,
exact fake setupPOST and operation123/running poll only; disabled close/Escape
callback0 passed. Artifact `adm-provision-20261012-231055` in approved local temp.
No real commands/SSH installation/server creation. Finished/full provisioning
workflow is source-preserved, not dynamically proven. No broad suite.

Fresh preflightcc21806; exact-source/no-active-Ansible/stale37 guards passed.
Canonical staging/swap/panel restart ran once, built index-BVURu9Ej.js matching
local candidate, retainedstatic.prev. One after-check passed exactc2abe67/active
ADM/PID change,32 backend files/72 running IDs/protected ERG Proxima runtime,
canonical_mounts and HTTP200/hash matches for index/3bundles/introduction.md on
loopback5002/publicadm.prxa.net (5 per origin). Private baseline
`/tmp/proxima-adm-provision-c2abe67.json` retained; no retry/site rollout.

PROX-64 stays Ready for review for Can's form/range/output/footer visual
confirmation. Real installation is unnecessary for visual acceptance. Other
review waits/wider phases active, KLM deferred. Next EditServer form and remaining
inventory/dialog views, with proportionate checks.
