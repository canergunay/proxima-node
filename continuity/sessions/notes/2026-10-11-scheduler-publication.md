# 2026-10-11 — Managed Scheduled Jobs cosmetic publication

Proxima **c2ef50ea96b1363b4a1a84afacdda5e95069c9a2** published serially on
ERG/SHV/ADM-managed SVR with Can's package-specific commit/push/SSH approval.
SVR operation **101 DONE**, canonical `publish-proxima-web.yml`, service venv
and existing bounded stale37 guard; historical operations retained. No restart.
ADM UI7414433 unchanged. KLM deferred.

Proxima `ScheduledJobs.tsx` presentation only: bounded long names, grouped
parent rows, consistent header/icons, local840px table scroll and nowrap times.
Triggers/payloads/disabled conditions/clock/polling/API unchanged. Build715-key
parity/56 synthetic full-App states and independent local visual/source QA passed.
No real job trigger or live scheduler polling-progression claim.

SVR previous snapshot:
`/var/lib/proxima-web-releases/dba79b2bf1ba3d72b87f2260951e284ca2df1809-20261011T145525Z-583768`.
New snapshot:
`/var/lib/proxima-web-releases/c2ef50ea96b1363b4a1a84afacdda5e95069c9a2-20261011T152258Z-590158`.

Actual read-only SVR verification passed raw runtime,95 backend files,
config hash equality,11 other running IDs,64 management+9 portal known HTTP
file hashes, canonical overlay, status200 and DNS. ERG/SHV checks passed with
93/95 backend files and71/16 other IDs. Config equality is an observation at
publication time. PROX-51 DONE, parentPROX-34 active. Next proposed page:
Latency Audit; native-client work remains separate/unreleased.
