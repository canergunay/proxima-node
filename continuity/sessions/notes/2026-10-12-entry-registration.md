# 2026-10-12 — Entry/registration (PROX-62 READY_FOR_REVIEW)

ADM **cc2180611cd60222d710c4831d30c8204cfaec31** published with Can's
package-specific commit/push/SSH and panel-restart approval. Only Login.tsx and
AddVpnServerDialog.tsx changed: padded dynamic viewport/card, responsive padding,
wrapped errors, desktop name/display-name grid, full-width URL/token fields and
matched footer controls. Auth/setup/registration endpoints, bodies, normalization,
autofill, loading/disabled/reset and callbacks retained. ProvisionDialog untouched.

Lean local evidence: one build/437-key parity, two baseline/four current isolated
themed views (short login error320, RUsetup320, Add1440, Add-error320), brief
independent exact-source QA. Fake POST bodies return rejection only; payload,
clipping/actionability checks pass. Artifact `adm-entry-forms-20261012-210047`
in approved local temp directory. No successful auth, account/server creation,
real token handling or provisioning integration proof.

Initial ERG SSH attempts timed out before deployment; TCP22 probe returned
reachable but SSH did not complete. Can said he was home and requested retry.
Original ERG path then worked; no alternate host/network change used. Fresh
preflight captured5b0f931,32 backend files,72 running IDs, protected Proxima
runtime and ADM PID. Exact-source/no-active-Ansible/stale37 guards passed.
Canonical staging/swap/panel restart ran once, produced index-D79WEvH-.js
matching local candidate and retainedstatic.prev.

One read-only after-check passed exactcc21806/active ADM/PID change,32 backend
files/72 IDs/protected ERG Proxima runtime/canonical_mounts, and HTTP200/hash
matches for index/3bundles/introduction.md on loopback5002/publicadm.prxa.net
(5 per origin). Private baseline `/tmp/proxima-adm-entry-cc21806.json` retained;
no site rollout by this slice.

PROX-62 remains Ready for review for visual confirmation of login/errors and
registration field/footer layout; no real creation is needed to inspect it.
Other review waits/wider phases retained; KLM deferred. Next provisioning/setup/
edit forms with the same proportionate verification approach.
