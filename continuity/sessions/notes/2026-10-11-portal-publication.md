# 2026-10-11 — Managed user portal main-page cosmetic publication

Proxima revision **c8c42c0b9e74b17bcce041a8409b64e75462c1b6** delivered
serially ERG/SHV/ADM-managed SVR with Can's package-specific commit/push/SSH
approval. Managed SVR operation **104 DONE**, canonical web playbook, service
venv and existing bounded stale37 guard. Historical operations retained;
no restart; ADM service/UI not redeployed, UI remains7414433.

Proxima Portal.tsx only: bounded device names/local table, wrapped responsive
route content/actions and dialog title/content/footer presentation. Existing
API/state/polling/auth/validation/grants/QR/copy/download behavior preserved.
Portal build68-key parity/99 main+9 tablet synthetic cases and independent local
source/visual QA passed. Exact config/URL/mockcopy/QR path preservation checked.
No real device/route/password mutation, QR scan or OS clipboard proof.

SVR previous snapshot:
`/var/lib/proxima-web-releases/79e48b2a13152f4b99b748f8af9fa949f34667f3-20261011T184005Z-626678`.
New snapshot:
`/var/lib/proxima-web-releases/c8c42c0b9e74b17bcce041a8409b64e75462c1b6-20261011T190408Z-632330`.

Read-only SVR verification passed raw runtime,95 backend files, config hash
equality,11 other running IDs,69 management+10 portal known HTTP hashes,
canonical overlay, status200 and DNS. ERG/SHV equivalents passed with93/95
backend files and71/16 other IDs. Equality is publication-time evidence only.

PROX-54 DONE, parentPROX-34 active; KLM deferred. Next: portal Login review,
then remaining ADM pages/dialogs. Native-client changes remain unreleased.
