# ADM GOC history migration — measured report

Date: **2026-10-04**. Result: **local preservation and retrieval implemented;
full GOC completion is not claimed**. Older-source and remote-resource gaps
remain. Twelve temporary originals disappeared after they had been preserved;
their archived bytes are intact.

## Identity, instructions and initial state

- Workspace/Git root: `D:\Nextcloud\Projects\proxima-node`.
- Validated repository identity: `canergunay/proxima-node`; local HEAD `6e8baf3`.
  Remote identity was parsed without emitting an authentication-bearing URL.
- Read original `CLAUDE.md`, all **778 lines of GOC.md**, README and applicable
  global/project instructions before migration implementation. No existing
  AGENTS/CONTINUITY/status/handoff layout was found in this workspace.
- Initial Git status: only `?? GOC.md`. Original GOC and CLAUDE were archived and
  remain unchanged. A small new `AGENTS.md` points to the continuity entry point;
  the applicable rule skill was loaded before authoring it.
- Read the Proxima server migration tools/report as references. The new scripts
  are self-contained ADM-local implementations with independent identity, strict
  path boundaries and no dependency on the server archive. That archive and all
  sibling workspaces were not modified.
- Existing OpenCode configuration was inspected through actual JSON parsing and
  an explicit safe-key allow-list only. The global JSONC file parsed as a
  one-key schema document. Claude settings exposed only counts and approved
  key names; no raw settings, credential files or arbitrary key/value strings
  were printed. No global configuration or shared manifest was modified.

## Archive and snapshot

Archive root:
`C:\Users\caner\AppData\Local\OpenCode\continuity\proxima-node-0ffefe2adcf7`

Final measured snapshot: **`20261004T171914672859Z`**.

**916 source entries, 142,090,248 logical bytes.** SHA-256 deduplication gives
**840 distinct objects, 141,296,469 object bytes** for this snapshot. These are
not physical-disk totals: earlier snapshots, indexes and delivery files remain.

- **13 top-level Claude session transcripts**, plus **1 independently
  path-attributed nested transcript** (14 entries in the transcript category).
- **15 parent-session sidecars**; not 15 independent human conversations.
- **17 Codex rollout/import files**, discovered through exact structured paths
  and/or ledger source-path + `session_meta.id` relationships. They overlap
  Claude history and must not be added to claim 30 unique conversations.
- **101 shared historical memory files**, preserved with original provenance.
  Eight ADM-prefixed notes and eight selected related notes were reviewed in
  full through sanitized output, including the shared MEMORY index and the
  contradictory Direct-profile handoff. Other memory was not semantically
  imported into ADM active context.
- **460 session-associated file-history revisions**.
- **111 session-keyed temporary artifacts** (including the 12 now absent at
  their original paths).
- **196 tracked ADM workspace files** as a current checkpoint, not old revisions.
- **1 untracked original workspace artifact: GOC.md**.
- **1 ignored inventory artifact**, attributed by original structured ADM file
  references and preserved privately without printing its contents.

The index has **56,442 JSONL records**, **27,723 document lines**, **1,230
human-classified occurrences**, **1,358 queue records**, **91 queued-command
attachments**, and **1,577 persisted resume records**. Counts include repeated
imports/queues; they are not unique human turns. **4,433 tool-result blocks,
135 image blocks and 8 document blocks** are retained in raw containers.
No JSONL parse errors were recorded. Image/document counts are structural
occurrences, not deduplicated artifacts or an OCR claim.

## Attribution and discovery

- Scanned **72 Claude JSONL files** across project stores and **55 Codex rollout
  files**. Exact cwd/subdirectories and structured file paths, including relative
  paths resolved against recorded cwd, establish attribution. The shared
  `d--Nextcloud-Projects-proxima` folder name alone is never evidence.
- Complete attributable mixed containers are retained. The search index keeps
  mixed context with explicit scope labels; 3,186 records have direct ADM path
  evidence. Path evidence is not semantic ownership. Only reviewed ADM claims
  were promoted into the handoff.
- Session-directory relationships cover sidecars, file-history and temporary
  artifacts. The Codex import ledger uses Windows extended-length paths;
  normalizing `\\?\` was necessary to match exact original sources. The shared
  ledger was read only; `import-provenance.json` is an ADM-local derivative.
- Inspected Claude session-env/todos/sessions/debug buckets for attributable
  session IDs, workspace instruction/artifact locations and desktop alternative
  stores: `claude-code-sessions`, `local-agent-mode-sessions`, `claude-code`,
  `space-memory-copy`, `git-shadow`, `LOCALAPPDATA/Claude-Data`, and local
  OpenCode storage. No extra structured ADM-path candidates were found in those
  probes. This is not forensic decoding of binary caches, browser databases,
  disk images or every possible historical path. Codex archived_sessions was
  absent. No project rename was established.

## Source disappearance: preserved bytes, incomplete current-source check

The first two successful captures (`20261004T170007061074Z` and
`20261004T170339981115Z`) compared source size/mtime and reread SHA-256 after
copying. All then-present files passed stable-source capture.

At capture `20261004T170621504683Z`, **12 Temp/claude files were missing**:
six PNGs, five task-output files and `scratchpad/awg-add-peer.sh`, associated
with sessions `96ed35d2-52b3-4fbf-aea3-4a5115d1aa12` and
`88824aa7-bbbe-47c2-bc5d-d55b7ea5d7d4`. The incomplete capture was retained and
was not made current. This migration contains no source-delete or source-edit
operation; the cause of external disappearance is unknown.

Later snapshots explicitly carry their earlier verified objects forward with
`source_error` and `preserved_from_snapshot` provenance. They are not presented
as freshly read originals. Final result: **916 archive entries match size/hash;
904 original sources still match; 12 original paths are absent**. There are no
changed-content originals among those still present. `continuity.py verify`
therefore truthfully exits **1** (`archive_ok=true`, `ok=false`).

## Security and verification actually performed

Before copying raw data, the archive was restricted to current user SID
`S-1-5-21-1888114584-3208564357-2452934339-1001` and SYSTEM `S-1-5-18`,
FullControl Allow only. The protected root ACL and actual descendant SID rules
were inspected across every descendant present at check time, with
zero unexpected principals (exact counts in verification.json). Newly written delivery/report files inherit this
same restriction.

Canonical evidence:
`<archive>\snapshots\20261004T171914672859Z\verification.json`.

`python scripts/continuity_verify.py --record` passed its bounded assertions:

- Archive sizes/SHA-256 for every raw entry; remaining source sizes/hashes;
  exact disclosure of the 12 absent originals; separate derivative hashes.
- Three real topics in three different original sessions: FTS search, exact
  source/line raw reopen, adjacent context, raw line hash and human chronology:
  - SiteGate: `88824aa7-bbbe-47c2-bc5d-d55b7ea5d7d4:3276`.
  - Userspace call-home: `96ed35d2-52b3-4fbf-aea3-4a5115d1aa12:530`.
  - Direct grants: `b7badd97-87c7-42c0-a6d9-15821cd5f293:362`.
- Human `queued_command` attachments (`humanTurn=true`) remain available;
  task-notification-only records, interruption placeholders, tool-result-only
  envelopes and persisted resume copies are not new human instructions.
  UUID/parent/timestamp/source-line relationships and all raw metadata survive.
- Absolute old-path resolution for `adm/backend/core/proxima_client.py`, with
  13 revision references, including cwd-backed relative-path resolution.
  In the full catalog, **5,727 revision-reference occurrences** resolve to
  preserved objects; unresolved references stay explicitly unresolved.
- Raw image/tool locations are queryable; inline binary bytes remain in the
  original JSONL containers, and standalone files remain SHA-addressed objects.
- Missing search/open/path returns 1; malformed FTS returns 2. Retrieval opens
  SQLite read-only and never executes archived commands.
- Sensitive structured fields, embedded JSON, connection URIs and multiline
  private-key guards were exercised with synthetic markers; document line
  count preservation and sibling-path rejection were asserted.

Redaction is conservative and best-effort, not a proof that every possible
secret can be recognized. No known credential-output incident occurred in this
ADM migration. No raw settings/transcripts or credential values were intentionally
emitted; no historical credentials were used. Authored artifacts are scanned
for high-confidence literal token/private-key patterns during delivery.

The independent verifier's exit 0 means its bounded assertions passed while
recorded source-loss gaps remain. It does **not** override `verify`'s source
failure or establish full GOC completion. No product tests/builds were run.

## Remaining gaps and access needs

- **74 distinct (session, non-null backup-name) pairs** unresolved in the full
  mixed catalog, including **17 ADM-attributed pairs**. There are 848 total
  reference occurrences, 69 ADM-attributed; these are not 848 unique lost files.
  Matching another session's same-named backup is deliberately not substituted.
- **18 origin-session IDs** from the shared memory are outside the attributed
  transcript set. For ADM-focused notes, the missing IDs are
  `e7acb949-02c1-4d41-abba-3f084ff2b34a` and
  `f086960c-878c-4ea4-b2ba-310c03134e49`. The latter covers central users,
  operator access and the setup wizard. Older machine backups or original
  exports are needed; shared-memory gaps are not all ADM-owned history.
- **304 unique unarchived structured local paths**, of which **116 are missing**
  and 188 exist outside the captured set. There are 2,583 occurrences. Many
  are sibling/shared work; no claim of ADM ownership or lost ADM files is made
  from this broad count. Exact source/line/path records are in verification.json.
- **125 frame-link occurrences** preserve cloud references, not cloud bodies,
  attachments or current comments. A current authorized artifact/canvas export
  or connector is required. Local tool text does not prove remote preservation.
- Live Punchlist tasks/attachments, authenticated project identity, GitHub PR
  status, deployed revisions, server databases, backups and runtime grants
  were not queried. Current project-scoped access is required to verify them.
  Historical agent names and authorizations were not adopted.
- This is a same-machine private copy, **not off-site backup**. There is no
  claim that every sentence, possible local store or source artifact was reviewed.

## GOC completion assessment

1. Discovered attributed sources preserved: scoped pass, exhaustive claim partial.
2. Archive hashes pass; current-source verification explicitly partial (12 absent).
3. This migration made no original-source changes; external Temp disappearance
   prevents claiming all originals are still present. GOC and product unchanged.
4. Retrieval/provenance links work; older revisions and remote content incomplete.
5. Search/open/resolve/verify actually exercised: pass within documented scope.
6. Three distinct-session retrieval checks: pass.
7. Source-backed startup/handoff: pass, with unmatched historical claims labeled.
8. Current/historical/superseded/uncertain states separated: pass.
9. Safe output guards and synthetic checks pass; not an exhaustive secret audit.
10. No product, global, sibling, production or account changes: pass for our writes.
11. Small startup pointer and usable commands: pass.
12. Remote/missing resources disclosed rather than claimed recovered: pass.

## Files authored

- `AGENTS.md`
- `CONTINUITY.md`
- `continuity/HANDOFF.md`
- `continuity/MIGRATION.md`
- `scripts/continuity.py`
- `scripts/continuity_audit.py`
- `scripts/continuity_verify.py`

Original history and product files were not edited. No commit, push, fetch,
deployment, SSH, account change, nested agent or global framework was used.
Original sources, GOC and sibling/server archives were never write targets.
Delivery copies of these seven files have their own manifest inside the private
archive and are excluded from the original-source counts above. Safe discovery,
audit and import-provenance metadata are preserved beside them under a separate
`metadata-manifest.json`; `verification.json` records the delivery manifest path.
