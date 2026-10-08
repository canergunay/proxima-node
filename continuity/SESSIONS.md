# Portable conversations

Open [the session catalog](sessions/INDEX.md) to distinguish saved conversations
by title, original ID, capture time and scope. The catalog is separate from the
current project state in [CONTINUITY.md](../CONTINUITY.md).

## On this computer, before copying the folder

With Python and OpenCode installed, run from the project root:

```powershell
python -B continuity/sessions.py live
python -B continuity/sessions.py save --limit 3
python -B continuity/sessions.py verify
```

`save --session ses_...` selects one conversation. Save uses the installed
OpenCode's native `export --sanitize --pure`, keeps the original session
unchanged, and adds a dated snapshot. It does not make a model request.
That native flag hides all message bodies in version 1.18.34. The utility keeps
its redacted tool/file metadata and restores only selectively guarded visible
user/assistant text from an in-memory export; unsanitized payloads are not saved.
Use the catalog's current snapshot, not older pre-fix metadata-only snapshots.
When deliberately carrying this multi-root conversation into another root,
use `save --from-workspace <source-root> --shared --session <id>`; it is labeled
as a shared workspace discussion, not a project-specific product backlog.

Copy the **whole project folder**, including `continuity/sessions/`. Chat payloads
under `snapshots/` and prepared imports under `restore/` are Git-ignored; this
does not exclude them from an ordinary USB/folder copy. A Git clone/archive alone
does not carry those ignored payloads. Dependency caches can be rebuilt.

## On the new computer

Read AGENTS and CONTINUITY first. List the copies without any AI installation:

```powershell
python -B continuity/sessions.py list
python -B continuity/sessions.py verify
```

For OpenCode, choose the key from the catalog and run:

```powershell
python -B continuity/sessions.py restore <session-key>
```

This prepares a separate thread with new project-qualified IDs, rebases its
workspace metadata to **this folder**, calls native `opencode import`, and prints
the explicit `opencode . --session <new-id>` command. It does not launch a model
or execute the old tools. Pending tools are marked interrupted; previous source
history and external LOCALAPPDATA archives are not needed. `prepare <key>` writes
the import file without importing, for inspection/testing.

For Codex or another agent, open the catalog's `transcript.md` and ask the agent
to continue with this folder's current CONTINUITY. Codex CLI exposes `resume`
for sessions already in its own store, but no native OpenCode-JSON import was
established here. A new cross-provider conversation is therefore a continuation
from the readable record, not a claim of restoring the identical native tab.

## Boundaries

For an agent without native export, write a separate dated/topic-named Markdown
note under `sessions/notes/`: what was requested, outcome, checks actually run,
unresolved items and next step. Run `python -B continuity/sessions.py index` to
include it in the catalog without any AI installation. These notes remain
separate when later OpenCode snapshots refresh the index.

- A snapshot captures messages saved at that time. Newer messages require another
  save; tool processes, unsent input and application window/tab layout do not move.
- Sanitization may omit sensitive text, file payloads and machine-specific data.
  It is not a lossless forensic transcript or a guarantee of a perfect detector.
- OpenCode's native import was tested with the installed version in an isolated
  data/config directory. New provider versions may change their format.
- Snapshot verification checks local relative file paths and SHA-256 only. It
  works even when the original computer, history stores and provider are absent.
- After meaningful work, update the project's CONTINUITY/handoff first. Before
  transfer, refresh session snapshots. Never treat old approvals as fresh access.
