# 2026-10-09 — Managed restart-free web publication

## Outcome

Can reaffirmed autonomous deployment with preservation of working services.
Proxima UI0e765b8 published on ERG/SHV/SVR without container recreation/restart.
ADM UI362a746 remains live and publicly verified; ADM operations code25ec5ee
pulled without restarting the backend. KLM remains unreachable and pending.

Versioned ADM additions: publish-proxima-web.yml and web-release-metadata.py
(6e85301); local-only image builder4783a41; explicit JSON envelope25ec5ee.
Proxima publisher/tests81fc6e7 retain full private snapshots, atomically publish
web entrypoints after immutable chunks, service worker last, retain stale-client
chunks and prepare a verified overlay tag for future recreation. Backend/version
metadata remains separate; no network, call-home or VPN installer is run.

## Verification

Independent final checks19:48–19:52UTC: ID/Image/StartedAt, raw Config/HostConfig,
all mount fields/network attachments match fresh snapshots; backend93/95/95
files equal; management40/portal8 files per site HTTP200/hash; other running
IDs70/16/11 equal; DNSNOERROR. Later config differences are exclusively peer
profile-fetch bookkeeping6/6/3; other config semantics equal.
ADM active/running since15:32:30UTC, NRestarts0; public index/main SHA matches
the deployed362a746 build. Publisher18 tests, wrapper10, metadata9 and actual
isolated Docker/PWA/recovery/controller-transport rehearsals passed.

## Operation boundaries

SVR op89 FAILED after publisher exit0 due metadata-only failure. Actual release
passed; no retry and no retrospective status correction. Ansible2.14.18 direct
stdin coerced JSON into Python repr. JSON envelope transport and one-level safe
parser were proven by local-controller before/after probes and then committed.

KLM op90 UNREACHABLE with changed0 at first target task. Current DBSSH192.168.2.115
and call-home10.12.12.11 unreachable; no live handshake. Last online sample
2026-10-06T23:00:29Z. Planned192.168.79.121 also timed out. No target mutation,
DB management-setting edit or routing/tunnel change. Do not assert powered off.
Existing op37 remained unchanged; explicit local stale guard is not evidence
that old remote work completed.

## Evidence and next step

Root-private `/var/lib/proxima-web-releases/` on respective targets:
ERG0e765b812905dd7e28affba61f9679fc9312a765-20261009T192708Z-1105327;
SHV...-20261009T192917Z-2400046; SVR...-20261009T193210Z-97174.
The Proxima session note of this same name has full details. Preserve inspect,
config/static backups, payloads and image tags; never print raw secret-bearing
records. Actual client VPN path/Can-device PWA/QR scanning not fully exercised.

Resume KLM only with reachable authoritative management. Continue cosmetic
foundation/page batches; reconcile prior published overlay before a subsequent
hot release instead of resetting image tags or restarting the backend blindly.
Punchlist Unauthorized blocks final comment backfill; local handoffs are current.
