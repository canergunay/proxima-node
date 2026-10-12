# 2026-10-13 — Update dialog and visual acceptance (PROX-68)

ADM **41a229418eb448aa73c88b7fb3cec0087ef27c1b** published with Can's
package-specific commit/push/SSH and panel-restart approval. Work began late
October12; publication verified October13 at00:03MSK. Only two Dashboard.tsx
sx edits: wrap long update heading and align footer spacing/minimum height.
OutputViewer was already contained and remains unchanged; updateBusy/body/
polling/operation/state/reset/callback/close logic preserved.

Lean evidence: build437-key parity, two baseline/four full-App synthetic states
(pending320, runningRU320, done1440, failed320), brief independent review.
Mock updatePOST{}→op123 and GETpoll only. Busy Close/Escape guards, finished
Close enablement and exact ANSI-stripped log text checked. First harness locator
timed out because Tooltip supplies the accessible name; selecting visible chip
text fixed the harness without product changes. Artifact
`adm-update-output-20261012-235804` in approved local temp directory.
No real site update/provisioning, backend authorization or full workflow proof.

Fresh preflighte4b06e2; exact-source/no-active-Ansible/stale37 guards passed.
Canonical staging/swap/approved panel restart ran once, built index-oxWAp1GS.js
matching local candidate, retainedstatic.prev. One after-check passed exact41a2294/
active ADM/PID change,32 backend files/72 running IDs/protected ERG Proxima
runtime/canonical_mounts and five index/bundle/document hashes on loopback/public.
Private baseline `/tmp/proxima-adm-update-41a2294.json`; no retry/site rollout.

## Human visual acceptance queue

Fresh Punchlist UI/READY_FOR_REVIEW list contains these published cosmetic slices:
- PROX-58 Settings: desktop card hierarchy/mobile errors.
- PROX-59 Admins: identity/scope/panel-access matrix and account/destructive dialogs.
- PROX-60 Details: headings/copy fields/management/slot/tunnel layout.
- PROX-61 Documentation: links/tables/both fence formats/topic navigation.
- PROX-62 Login/registration: narrow/short forms/errors.
- PROX-64 Provisioning/setup: fields/range labels/progress/footer.
- PROX-67 Edit/inventory: field pairs/metadata/local table scrolling.
- PROX-68 Update: heading/footer/visible progress states.

Can's visual confirmation or concrete findings are next. Real destructive or
provisioning actions are unnecessary for cosmetic acceptance. Do not queue
generic additional polish without findings. Parent phases remain active until
their broader acceptance is established; native PROX-2/30 and functional/network
work are separate. All previous review waits retained.
