# 2026-10-11 — Managed ProximaVPN page publication

Can explicitly approved this cosmetic package's commit/push/SSH and serial
ERG → SHV → ADM-managed SVR publication. Proxima revision
**dba79b2bf1ba3d72b87f2260951e284ca2df1809** is live on all three sites.
SVR operation **100 DONE**, through canonical `publish-proxima-web.yml` and
ADM service venv. Existing bounded stale37 concurrency guard used; historical
operations retained. ADM service/UI not redeployed; UI remains7414433.

Proxima-only source: responsive server grids and mobile/desktop peer presentation
in `frontend/src/pages/ProximaVPN.tsx`; no protocol/config/QR/permission behavior
changes. Production build/715-key parity,55 synthetic full-App cases and
independent local source/visual QA passed. No live peer mutation tests.

SVR exact previous snapshot:
`/var/lib/proxima-web-releases/be32c04ce45881a147801289b6e6ad7fa6ddeffc-20261011T135009Z-571152`.
New snapshot:
`/var/lib/proxima-web-releases/dba79b2bf1ba3d72b87f2260951e284ca2df1809-20261011T145525Z-583768`.

Actual read-only live SVR verification passed: protected raw runtime unchanged,
95 backend files, config equal fresh baseline,11 other running IDs unchanged,
62 management+9 portal known HTTP file hashes, canonical overlay, status200 and
DNS. ERG/SHV equivalents passed with93/95 backend files and71/16 other IDs.
No restart on any site. Config equality is publication-time evidence only.

PROX-49 DONE, parentPROX-34 remains active. KLM deferred; no router/network
change. Native client work remains separate and unreleased. Next: select the
next remaining web page/dialog batch from the roadmap.
