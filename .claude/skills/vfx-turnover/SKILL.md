---
name: vfx-turnover
description: Reference for the vfx-turnover CLI tool. Use when helping a VFX editor run commands, understand workflow steps, troubleshoot exports, or work with VFX IDs — covers all CLI flags, what each export produces, VFX ID naming, and Avid workflow context.
---

# vfx-turnover

CLI tool for managing the VFX workflow in Avid Media Composer. Imports EDL or AAF files, generates VFX IDs, and exports markers, subcaps, pull ALEs, TAB spreadsheets, and AAF clip notes.

Project settings are saved at `~/.config/vfx_turnover/vfx_project.json` and reused across all commands.

---

## Commands

| Flag | What it does |
|------|-------------|
| `-i` | Set up project: Project ID, FPS, resolution, handle frames. **Clears all existing project data** — run once at project start. |
| `-e FILE` | Import an EDL or AAF into the library and set it as the active timeline. Upserts by filename. |
| `-e` | Interactive library manager — list entries, set active, remove, clear. |
| `-m` | Export Avid markers file. Prompts for user name, track, color, and position. |
| `-s` | Export subcaps file (no prompts, uses saved settings). |
| `-p` | Export ALE + Pulls EDL for creating pull subclips in Avid. |
| `-t` | Export TAB spreadsheet with VFX IDs and source timecodes. |
| `-t FILE.ALE` | Same as `-t` but merged with ALE metadata columns (matched by reel/tape name). |
| `-a` | Export new AAF with VFX IDs written as clip notes, markers, and clip color. Requires AAF imported via `-e`. |
| `-f BIN` | Export EDL for cutting final VFX deliveries into Avid. Requires an Avid bin exported as TAB. |
| `-c NEW_EDL` | Compare a revised EDL against the current project and export a changelist. |

---

## Typical Workflow

1. **`-i`** — initialize project settings (clears existing project)
2. **`-e timeline.edl`** — import the VFX EDL or AAF into the library (set as active)
3. **`-e`** — (optional) manage library: switch active entry, remove, clear
4. **`-m`** — export markers → import into Avid to mark VFX shots on timeline
5. **`-s`** — export subcaps → import into Avid as subtitles
6. **`-p`** — export ALE + Pulls EDL → create pull subclips in Avid bin
7. **`-t`** — export TAB → import into spreadsheet/database
8. **`-a`** — (AAF workflow only) write VFX IDs back to AAF as clip notes

---

## EDL/AAF Library

The project stores a **library** of imported EDL/AAF files. One entry is always the active timeline — all exports operate on it.

- **`-e FILE`** — adds or updates the entry in the library, sets it as active immediately
- **`-e`** (no arg) — interactive manager: shows numbered list with `*` on the active entry; options L/R/C/Q

Project JSON structure:
```json
{
  "config": { "active": "timeline.edl", "ProjectID": "GDN", "fps": "24", ... },
  "library": [
    { "edl_file": "timeline.edl", "edl_dir": "/path", "edl_metadata": {}, "events": [...] },
    { "edl_file": "timeline_v2.edl", "edl_dir": "/path", "edl_metadata": {}, "events": [...] }
  ]
}
```

`get_active_entry(project)` returns the active library entry dict (matched by `config.active`, fallback to first, fallback to `{}`).

## VFX ID Format

`{ProjectID}_{scene}_{counter}` — e.g. `GDN_033_0010`

- **ProjectID**: set via `-i` (e.g. `GDN`)
- **scene**: 3-digit scene number extracted from clip name (e.g. clip `33-2-/01 A` → `033`)
- **counter**: 4-digit, starts at `0010`, increments by `10` per scene, resets on scene change

IDs are auto-generated only when the EDL/AAF has no existing markers or clip notes. If some clips already have IDs and others don't, the import warns and leaves the missing ones empty.

When importing an AAF: clip note ID takes priority over marker ID.

---

## Output Files

All files are saved in the same folder as the source EDL or AAF.

| Command | Output file(s) |
|---------|---------------|
| `-m` | `<stem>_markers.txt` |
| `-s` | `<stem>_subcaps.txt` |
| `-p` | `<stem>.ALE`, `<stem>_pulls.edl` |
| `-t` | `<stem>_TAB.txt` |
| `-t FILE.ALE` | `<stem>_<ale_stem>_merge.txt` |
| `-f` | `<stem>_vfx_final.edl` |
| `-c` | `<new_stem>_changelist_markers.txt`, `<new_stem>_changelist_TAB.txt` (next to the new EDL) |
| `-a` | `<stem>_new.aaf` (next to source AAF) |

If an output file already exists, the tool asks before overwriting.

---

## PDF Report (`tab-to-pdf`)

Generates a PDF from any TAB spreadsheet exported by `-t`. Each VFX ID gets a card with the thumbnail on the left and all fields on the right in a 3-column grid.

```bash
tab-to-pdf <TAB_FILE> [-t <thumbnails_dir>] [-o <output.pdf>]
```

- **`-t DIR`** — folder of thumbnail images; matched by VFX ID in filename (handles `0000 GDN_053_0010.jpg` or plain `GDN_053_0010.jpg`)
- **`-o PDF`** — output path; defaults to `<TAB_FILE>.pdf` in the same folder
- Column names are read from the TAB header at runtime — works with plain and ALE-merged TAB files

Slash command: `/vfx-report <TAB_FILE> [<thumbnails_dir>]`

---

## TAB File Columns

`#`, `Name` (VFX ID), `Thumbnail`, `Comments` (job description), `Status`, `Date`, `Duration`, `Start`, `End`, `Frame Count Duration`, `Handles`, `Tape`

When merged with an ALE (`-t FILE.ALE`): all ALE columns are appended except those already present (`Name`, `Start`, `End`, `Tape`, `Duration`). ALE `Comments` is renamed `ALE Comments`.

---

## ALE Merge (`-t FILE.ALE`)

Matches each project shot to an ALE row by **reel/tape name** only. Validates that the ALE FPS matches the project FPS (mismatch aborts). Resolution mismatch prints a warning but continues. Reports matched and unmatched shot counts after export.

---

## Changelist (`-c`)

Compares a revised EDL against the current loaded project. Shots are matched by VFX ID (if the original EDL had markers) or by reel + source timecode as fallback.

| Change status | Meaning |
|--------------|---------|
| `new` | Shot not in previous version — needs pull |
| `removed` | Shot removed from cut |
| `moved` | Record timecode shifted, source unchanged |
| `trimmed_ok` | Source trimmed, but within handle frames — no new pull |
| `trimmed_pull` | Source trimmed beyond handles — new pull needed |
| `moved_trimmed_ok` | Moved and trimmed within handles |
| `moved_trimmed_pull` | Moved and trimmed, needs pull |
| `unchanged` | No change |

Exports a markers file and TAB file next to the new EDL.

---

## AAF Export (`-a`)

Copies the source AAF and writes VFX IDs as:
- **Clip notes** (`_COMMENT`) — visible in Avid bin
- **Timeline markers** — visible on the Avid timeline
- **Clip color** — optional Avid clip color (32 colors available)

Prompts for: Avid user name, marker color, marker position (`start` / `middle`), clip color.

Requires the project to have been imported from an AAF via `-e`. If a clip already has a marker in the AAF, the note is always updated to match. Reports an error if clip note and marker IDs disagree on any clip — fix the mismatch in Avid before re-running.

---

## Marker Settings

Prompted interactively by `-m` and `-a`, then saved as project defaults:

| Setting | Options | Default |
|---------|---------|---------|
| User name | any string | `vfx` |
| Track | `TC`, `V1`–`V8` | `V1` |
| Color | `green`, `red`, `blue`, `cyan`, `magenta`, `yellow`, `black`, `white` | `green` |
| Position | `start`, `middle` | `start` |
| Clip color (`-a` only) | 32 Avid colors or `none` | `none` |

---

## Important Workflow Notes

- **Commit multicam and MultiGroup clips in Avid before exporting EDL or AAF** — uncommitted clips produce wrong source timecodes or missing reel names.
- **`-a` requires the project to have been imported from an AAF** (`-e sequence.aaf`). It won't work on EDL-imported projects.
- **Auto-generated VFX IDs are not used for changelist matching** — only IDs that came from real EDL markers (`*LOC` lines) are matched by ID; others fall back to reel + source timecode.
- **FPS must match** when merging an ALE — the tool aborts if the ALE FPS differs from the project FPS.
