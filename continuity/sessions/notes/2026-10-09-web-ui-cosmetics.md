# 2026-10-09 — ADM cosmetic web first batch

## Outcome and scope

Can authorized delegated, orchestrated cosmetic web-only renewal of ADM and
Proxima. Punchlist UI PROX-32 parent; P0–P4 PROX-33/36/35/34/37. Master plan
Section 24; detailed portable roadmap in Proxima continuity/WEB-UI-ROADMAP.md.
ADM pre-change tree clean, HEAD a392738. No backend/infrastructure changes.

## Changes and checks

Only local `sx` changed in adm/frontend/src/pages/Dashboard.tsx,
components/ServerCard.tsx and components/VpnServerCard.tsx. Toolbar wrapping,
long-text/chip containment, metric shrink safeguards. Independent QA caught
new desktop chip compression; corrected headers stack at every viewport, with
full-width wrapping, nonshrinking action/status groups. Final scoped QA GREEN.

Actual pre/post npm run build passed; en/tr/ru parity 437 keys passed; scoped
git diff --check passed (line-ending notices only). Browser remedy matrix:
48 cases = eight widths × three locales × exit/VPN tabs; 168 chips with no
character-wide/clipped labels; 144 status/type/state samples 24px high;
480 enabled-button actionability trials passed, no page overflow. Source stable.

## Evidence and boundaries

Initial cross-product browser report: Temp opencode/cosmetic-verification-20261009-171954.
Remedy report and PNG/JSON: Temp opencode/cosmetic-verification-20261009-180804.
Full Temp parent: C:\Users\caner\AppData\Local\Temp\opencode.
Independent reviewer read reports and representative desktop/phone screenshots.
All APIs synthetic; external requests blocked; temporary Vite processes stopped.
Full app shell/auth, live backend and real infrastructure excluded. Existing
exit-card button-inside-button warning remains; do not silently expand scope
into changing interaction semantics. No commit/push/SSH/deployment performed.

## Next

### Subsequent authorized publication

Can authorized commit/push/deploy/SSH. ADM **362a746** deployed with the canonical
`adm/deploy.sh` staging/swap/restart flow. Public adm.prxa.net returns200;
index SHAfe46388a and main bundle SHA0a8fe4b9 match server static output. Service
active; static.prev retained. Proxima **0e765b8** pushed but rollout blocked after
ERG canary runtime fingerprint mismatch. Exact old image/backend restored, other
70 container IDs stable, panel/portal/status200 and DNSNOERROR; HostConfig difference
remains unexplained. Managed SVR/KLM deploy not invoked. Inventory discovery found
pre-existing operation37 still running; no status modification was made.

Broader rendered page/state audit, restrained cosmetic foundations and local
dialog/matrix/monitoring/docs batches. Preserve all APIs, handlers, polling,
permissions, tabs and form behavior. Tracker items remain open for Can's closure.
