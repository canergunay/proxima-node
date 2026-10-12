# 2026-10-12 — Documentation (PROX-61 READY_FOR_REVIEW)

ADM **5b0f931a803615fe4deeae86041ac8a619dbcfb6** published with Can's
package-specific commit/push/SSH and canonical panel-restart approval.
Only `adm/frontend/src/pages/Docs.tsx` changed: wrapped long links/content,
full-width mobile topic selector, readable table column floors and header/footer.
Root renderer fix gives Markdown `pre` the block wrapper rather than detecting
only language-tagged `code`; tagged and untagged fences now preserve whitespace
without nested pre. Inline styling/language classes and exact content preserved.
Fetch/loading/error/slug/scroll/navigation/links/plugins/default safety behavior
unchanged; no actual documentation files edited.

Proportional evidence: initial build437-key parity and two baseline/four targeted
full-App views (en320/1440,ru320,404320). Exact tagged/untagged/inline code text,
two nonnested pre blocks/whitespace, internal link/previous/mobile topic navigation
passed. Screenshot caught a narrow second table column; one CSS correction then
final build/parity and only two affected table views rerun. No broad matrix.
Artifacts: `adm-docs-20261012-202036` and `adm-docs-20261012-202205` in the
approved local temp directory. Short independent QA GREEN; latest source matches
latest table screenshots. RU/404 views precede only the table-width correction,
so they are relevant but not latest-byte-bound evidence. GET-only fixtures;
no document command execution, real API mutations or security/integration proof.

Fresh preflight42fc0b0; exact guard allowed only Docs.tsx+continuity docs, no
active Ansible/stale37 retained. Canonical staged build index-Cyv9Tcv1.js matches
local candidate, swapped static/static.prev and restarted panel once. One after
check passed exact5b0f931/active ADM/PID change,32 backend files/72 running IDs/
protected ERG Proxima runtime (canonical_mounts), retainedstatic.prev and HTTP200/
hash matches for index+3 bundles+introduction.md on loopback5002/publicadm.prxa.net.
Private baseline `/tmp/proxima-adm-docs-5b0f931.json`; no retry/site rollout.

PROX-61 stays Ready for review for Can's visual confirmation of topic selection,
long links/tables and both fence formats. Other review waits retained; broader
phases active; KLM deferred. Next remaining ADM login/provisioning/add forms.
