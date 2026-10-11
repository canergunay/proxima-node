# 2026-10-11 — Managed Portal Login cosmetic publication

Proxima revision **f260a40209b8677222a3760255a7c7088158512f** delivered
serially ERG/SHV/ADM-managed SVR with Can's package-specific commit/push/SSH
approval. SVR operation **105 DONE**, canonical web playbook, service venv and
existing bounded stale37 guard. Historical operations retained; no restarts.
ADM service/UI not redeployed; UI remains7414433.

Portal Login.tsx presentation only: wrapped alert text, padded dynamic viewport,
bounded 380px card, responsive padding/border and heading emphasis. Credential,
token, password toggle/autofill and error handling preserved. Portal build,
68-key parity, 77 full-App synthetic cases and independent local QA passed.
Fake login rejection/pending states only; no successful or real login proof.

SVR previous snapshot:
`/var/lib/proxima-web-releases/c8c42c0b9e74b17bcce041a8409b64e75462c1b6-20261011T190408Z-632330`.
New snapshot:
`/var/lib/proxima-web-releases/f260a40209b8677222a3760255a7c7088158512f-20261011T192133Z-636759`.

Read-only SVR verification passed protected raw runtime, 95 backend files,
config hash equality, 11 other running IDs, 69 management+11 portal known HTTP
file hashes, canonical overlay, status200 and DNS. ERG/SHV equivalents passed
with 93/95 backend files and 71/16 other IDs. Equality is publication-time
evidence only.

PROX-55 DONE; parentPROX-34 active; KLM deferred. Next remaining ADM page/dialog
batches, starting Monitoring review. Native-client changes remain unreleased.
