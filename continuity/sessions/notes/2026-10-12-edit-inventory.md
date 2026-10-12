# 2026-10-12 — Edit/inventory (PROX-67 READY_FOR_REVIEW)

ADM **e4b06e28bfdb6d2df8d8d9d78567f16333787aad** published with Can's
package-specific commit/push/SSH and panel-restart approval. Only EditServerDialog
and ServiceInventoryDialog changed: desktop field pairs/mobile stack, full-row
VPN addresses, wrapped alerts/footer, readable inventory metadata/chips and local
700px fixed-column table. Field maps/order/required/reload/changed-only trimmed
body, endpoints/no-op close/callbacks and read-only fetch/observed/missing/
unexpected/null-listening/exposure semantics retained.

Lean evidence: build and437-key parity, two baseline/four isolated views
(exit desktop, VPN Russian mobile rejection, observed inventory desktop and
not-observed inventory Russian mobile), same-view table captures, brief exact-
source QA. Mock URL-only PUT returns rejection; inventory GET mocked. No real
endpoint change, host/service probe or full-App proof. Artifact
`adm-edit-inventory-20261012-233515` in approved local temp directory.
Mobile table intentionally scrolls; input text keeps native horizontal scrolling.

Fresh preflightc2abe67; exact-source/no-active-Ansible/stale37 guards passed.
Canonical staging/swap/approved panel restart ran once. index-oWiQP-PI.js and
the updated shared chunk names match local candidate. One after-check passed
exacte4b06e2/active ADM/PID change,32 backend files/72 running IDs/protected ERG
Proxima runtime/canonical_mounts/static.prev and HTTP200/hash matches for
index/3bundles/introduction.md on loopback5002/publicadm.prxa.net (5 per origin).
Private baseline `/tmp/proxima-adm-edit-inventory-e4b06e2.json` retained;
no retry or site rollout.

PROX-67 stays Ready for review for Can's edit/errors/address/table visual
confirmation. Real endpoint edits or scans are unnecessary for visual acceptance.
Other review waits/wider phases active, KLM deferred. Next bounded operation-
output/update-dialog appearance check, then consolidate human visual acceptance.
