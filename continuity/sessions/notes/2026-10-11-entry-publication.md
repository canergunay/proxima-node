# 2026-10-11 — Managed Login / Setup cosmetic publication

Proxima revision **79e48b2a13152f4b99b748f8af9fa949f34667f3** delivered
serially ERG/SHV/ADM-managed SVR with Can's package-specific commit/push/SSH
approval. SVR operation **103 DONE**, canonical `publish-proxima-web.yml`,
service venv and existing bounded stale37 guard. Historical operations retained;
no restarts. ADM service/UI not redeployed; UI remains7414433.

Two Proxima entry pages changed: bounded/padded login card, wrapped alerts/list
messages, responsive wizard title/mobile step circles/connectors/footer. Original
auth/autofill/validation/navigation/write sequence retained. Build715-key parity,
98 synthetic full-App cases and independent local visual/source QA passed.
Only synthetic login rejection; setup/apply mutations prohibited. No real login,
account creation, successful apply or production authorization proof.

Exact SVR previous snapshot:
`/var/lib/proxima-web-releases/636be89ee6258f34742ce18aec0b45bd3ba6de1c-20261011T154108Z-594856`.
New snapshot:
`/var/lib/proxima-web-releases/79e48b2a13152f4b99b748f8af9fa949f34667f3-20261011T184005Z-626678`.

Read-only SVR checks passed protected raw runtime,95 backend files, config hash
equality,11 other running IDs,69 management+9 portal known HTTP file hashes,
canonical overlay, status200/DNS. ERG/SHV passed with93/95 backend files and
71/16 other IDs. Config equality is publication-time evidence only.

PROX-53 DONE; parentPROX-34 active; KLM deferred. Next: user portal presentation
review, then remaining ADM batches. Native-client changes remain separate/unreleased.
