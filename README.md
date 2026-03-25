## Python script to help manage the VFX workflow in Avid Media Composer

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE.md)

### Installation

Requires Python 3.10+ and [pipx](https://pipx.pypa.io).

```bash
git clone https://github.com/pnardese/vfx_turnover.git
cd vfx_turnover
pipx install -e .
```

The `vfx-turnover` command will be available system-wide without activating a virtual environment.

To update after pulling new changes:
```bash
pipx reinstall vfx-turnover
```

### Supported EDL Formats

- **Avid File_129 EDL** - Standard Avid Media Composer EDL format
- **CMX3600 EDL** - Industry standard CMX3600 format

---

## Workflow Guide

### 1. Initialize Project

Run once at the start of a new project. **This clears any existing project data** — library, shot list, and settings are all reset.

```
vfx-turnover -i
```

The script prompts for:

| Option | Choices | Default |
|--------|---------|---------|
| Project ID | any string | `PID` |
| FPS | `23.976`, `24`, `25`, `29.97`, `30`, `59.94`, `60` | `24` |
| Resolution | any string | `1080` |
| Handles | frames | `10` |

Settings are saved to `~/.config/vfx_turnover/vfx_project.json` and reused by all subsequent commands without prompting.

### 2. Import EDL or AAF

The `-e FILE` command imports an EDL or AAF into the project library and sets it as the active timeline. You can import multiple EDL/AAF files — each is stored as a separate entry in the library. All exports always operate on the active entry.

If you re-import a file with the same filename, the existing library entry is updated in place.

#### Manage the library

Run `-e` without an argument to open the interactive library manager:

```
vfx-turnover -e
```

```
Library (2 entries):
  * 1  timeline_v2.edl     48 shots   /path/to/edls
    2  timeline_v1.edl     45 shots   /path/to/edls

[L] Load (set active)   [R] Remove   [C] Clear all   [Q] Quit
```

The entry marked `*` is the currently active timeline. Use **L** to switch the active entry, **R** to remove one, **C** to clear all.

#### Import from EDL

**Import from EDL**

Create an EDL (File_129 or CMX3600) from the Avid video track containing only shots planned for VFX, simplify timeline by removing transitions, effects and committing groups. In List Options in Avid, check: **Clip Names**, **Source File Name**, and **Markers**.

VFX IDs are generated automatically based on scene numbers: `ProjectID_Scene_num`, where `num` is a 4-digit progressive number like `0010`, `0020`, `0030`, etc. Auto-generation only happens when the EDL has **no markers at all**. If the EDL has markers but some events are missing a VFX ID, the script loads the project with a warning — missing IDs are left empty in the project JSON.

Existing markers on the timeline are imported as existing VFX IDs (found in the EDL as `*LOC` lines). If you add VFX shots in Avid, add markers with their new VFX IDs before re-importing.

Marker comments may include a job description after the VFX ID (e.g. `GDN_033_0010 - REMOVE BACKGROUND`). The script reads only the VFX ID (first word) and stores the job description separately. The job description is included in the exported markers file and in the TAB `Comments` column.

> **Note:** Multicam/MultiGroup clips must be committed in Avid before exporting the EDL — uncommitted clips may produce wrong source timecodes or missing reel names.

![Configuration of the list tool in Avid Media Composer for EDL exporting](imgs/01_create_edl.png)

```
vfx-turnover -e timeline.edl
```

**Import from AAF**

If no EDL is available, you can import the VFX sequence directly from an Avid AAF export. Simplify the timeline in Avid before exporting (remove transitions, effects, commit groups — including multicam/MultiGroup clips), then export the sequence as AAF and run:

```
vfx-turnover -e sequence.aaf
```

The project file is created using the settings from `-i`. The script warns if the AAF fps or resolution does not match the project config.

**VFX ID handling** for AAF import:

- **No markers and no clip notes** → VFX IDs are auto-generated from scene numbers (`ProjectID_Scene_num`, 4-digit counter)
- **Some clips missing both marker and clip note** → script loads with a warning listing the affected clips and timecodes; missing IDs are left empty in the project JSON
- **Clip has marker only, or clip note only** → that ID is used; the other source is ignored
- **Job descriptions** in clip notes or markers (e.g. `GDN_033_0010 - REMOVE BACKGROUND`) are stripped from the VFX ID but preserved and written back to both clip note and marker when exporting
- **Clip has both marker and clip note with different values** → script stops with a mismatch error (checked at export time via `-a`):

```
Error: 2 VFX ID mismatch(es) found — fix the source AAF before exporting:

  [00:58:26:09]  33-2-/01 A
    Clip note : GDN_033_100
    Marker    : GDN_033_105
  [00:59:01:04]  33-4-/01 A
    Clip note : GDN_033_1
    Marker    : GDN_033_130
```

Resolve the mismatches in Avid before re-running.

### 2b. Export AAF with VFX IDs

After importing an AAF with `-e`, export a new AAF with VFX IDs written as clip notes, timeline markers, and clip color:

```
vfx-turnover -a
```

The script prompts for:

| Option | Choices | Default |
|--------|---------|---------|
| AVID user name | any string | `vfx` |
| Marker color | `green`, `red`, `blue`, `cyan`, `magenta`, `yellow`, `black`, `white` | `green` |
| Marker position | `start`, `middle` | `start` |
| Clip color | 32 Avid colors or `none` | `none` |

The output AAF is saved next to the source AAF with `_new` appended (e.g. `sequence_new.aaf`). The project JSON is updated with the clip notes written to the AAF.

---

### 3. Export Markers and Subcaps

Export a markers file and import it into Avid to help keep track of VFX shots.

```
vfx-turnover -m
```

The script prompts for:

| Option | Choices | Default |
|--------|---------|---------|
| AVID user name | any string | `vfx` |
| Track | `TC`, `V1`–`V8` | `V1` |
| Marker color | `green`, `red`, `blue`, `cyan`, `magenta`, `yellow`, `black`, `white` | `green` |
| Marker position | `start`, `middle` | `middle` |

To export only the subcaps file without prompts:

```
vfx-turnover -s
```

### 4. Export Frames

Export markers from Avid as JPGs to use them to build a VFX shots database.

![Export settings for frame extraction at marker's position](imgs/02_export_frames.png)

### 5. Export TAB Text File

Export a TAB-delimited file with VFX IDs info, importable in any database or spreadsheet to build a VFX shot database.

```
vfx-turnover -t
```

The exported file contains one row per shot with the following columns:

| Column | Description |
|--------|-------------|
| `#` | Shot counter |
| `Name` | VFX ID |
| `Thumbnail` | *(empty — for thumbnail reference)* |
| `Comments` | Job description if present (e.g. `- REMOVE BACKGROUND`), otherwise empty |
| `Status` | *(empty)* |
| `Date` | *(empty)* |
| `Duration` | Source clip duration as timecode |
| `Start` | Source start timecode |
| `End` | Source end timecode |
| `Frame Count Duration` | Duration in frames |
| `Pull Handles` | Handle frames configured for the project |
| `Tape` | Source reel / tape name |

#### Merge with ALE

Pass an Avid ALE file as argument to merge the ALE clip metadata into the TAB export:

```
vfx-turnover -t dailies.ALE
```

Each project event is matched to the ALE by reel name (`Tape` column). The output file gets all standard TAB columns plus every additional column found in the ALE (e.g. `Color`, `Creation Date`, `Camera`, `Video`, `Camroll`). Columns already present in the standard TAB (`Name`, `Start`, `End`, `Tape`, `Duration`) are skipped; the ALE `Comments` column is renamed to `ALE Comments` to avoid collision with the TAB `Comments` column.

The output file is saved in the same folder as the EDL, named `<edl_stem>_<ale_stem>_merge.txt`.

The script validates that the ALE FPS matches the project FPS (mismatch aborts) and warns if the `VIDEO_FORMAT` differs from the project resolution. A match summary is printed after export.

### 6. Export PDF Report

Generate a PDF report from any TAB file exported by `-t`, with one card per shot, a thumbnail on the left, and all fields on the right in a 3-column grid.

```bash
tab-to-pdf SCENA_53_EDIT_TAB.txt -t "./53 thumbnails" -o scena_53.pdf
```

| Option | Description |
|--------|-------------|
| `-t DIR` | Folder of thumbnail images. Filenames are matched by VFX ID — handles both `0000 GDN_053_0010.jpg` (Avid frame export format) and plain `GDN_053_0010.jpg`. |
| `-o PDF` | Output path. Defaults to `<TAB_FILE>.pdf` in the same folder. |

Column names are read from the TAB header at runtime, so the command works with plain TAB files and ALE-merged TAB files without any configuration.

Or use the slash command in Claude Code:

```
/vfx-report SCENA_53_EDIT_TAB.txt "./53 thumbnails"
```

### 7. Export ALE Pulls and Pulls EDL

Export an ALE to create pull subclips and a Pulls EDL to cut them into a timeline — both exported in one step using the handle frames set in `-i`.

```
vfx-turnover -p
```

- **ALE file** — drag onto the Avid bin after selecting master clips. Import settings: *Merge events with known sources and automatically create subclips*.
- **Pulls EDL** — import into an Avid bin and relink to pull subclips using Names.

![Import settings](imgs/03_merge_events_ale.png)

![Relink configuration](imgs/04_relink_edl_pulls_v02.png)

### 8. Compare EDL Versions (Changelist)

When the editor delivers a revised EDL, compare it against the loaded project to generate a changelist markers file and TAB file for Avid. Clips are matched by VFX ID (from `*LOC` markers) or by reel + source timecode as fallback.

```
vfx-turnover -c new_timeline.edl
```

Handle frames are read from the project config (set via `-i`). The script prompts for AVID user, track, and marker color, then exports two files next to the new EDL:

- **`_changelist_markers.txt`** — Avid markers file; each changed clip gets a marker with a status label
- **`_changelist_TAB.txt`** — same columns as `-t`, with the change status in the `Status` column

| Status | Label |
|--------|-------|
| New clip | `VFX_ID NEW - NEED TO PULL` |
| Removed clip | `VFX_ID REMOVED` |
| Moved (record TC shift) | `VFX_ID MOVED` |
| Tail trimmed, within handles | `VFX_ID TRIMMED TAIL +7f - NO PULL NEEDED` |
| Tail trimmed, beyond handles | `VFX_ID TRIMMED TAIL +15f - NEED TO PULL` |
| Head trimmed | `VFX_ID TRIMMED HEAD -5f - NO PULL NEEDED` |
| Both ends trimmed | `VFX_ID TRIMMED HEAD & TAIL H:-3f T:+8f - NO PULL NEEDED` |
| Moved and trimmed | `VFX_ID MOVED TRIMMED TAIL +4f - NEED TO PULL` |

Frame deltas use `+` when the clip is extended and `-` when it is reduced. A trim is considered within handles (no new pull needed) when the source content added at each end stays within the handle frames configured in `-i`.

### 9. VFX Cut-ins

When you receive incoming VFX (`.mov` files), import them into Avid, then export the bin in TAB format. Use the TAB file to generate an EDL for cutting the VFX into the timeline. Required bin columns: **Color**, **Name**, **Duration**, **Start**, **End**, **Tape**.

```
vfx-turnover -f avid_bin.txt
```

![Columns to export from Avid bin as TAB text file](imgs/05_vfx_cutins.png)

---

## All Options

| Option | Description |
|--------|-------------|
| `-i` | Initialize project settings — **clears all existing project data** |
| `-e FILE` | Import an EDL or AAF into the library and set it as active |
| `-e` | Open interactive library manager (load active, remove, clear) |
| `-a` | Export a new AAF with VFX ID clip notes, markers and clip color (requires project imported from AAF via `-e`) |
| `-m` | Export markers file for Avid (interactive options) |
| `-s` | Export subcaps file for Avid |
| `-p` | Export ALE and Pulls EDL for creating pulls in Avid bin |
| `-t` | Export a TAB-delimited text file for spreadsheet import |
| `-t dailies.ALE` | Export TAB file merged with ALE clip metadata (matched by reel name) |
| `-f avid_bin.txt` | Export an EDL to cut in final VFX shots (requires Avid bin TAB) |
| `-c new.edl` | Compare new EDL against loaded project and export changelist markers and TAB files |

All exported files are saved in the same folder as the original EDL or AAF. If an output file already exists, the script will ask for confirmation before overwriting.

### tab-to-pdf

A separate command (also included in this package) that generates a PDF report from any TAB file:

```bash
tab-to-pdf TAB_FILE [-t THUMBNAILS_DIR] [-o OUTPUT.pdf]
```

See [step 6](#6-export-pdf-report) for full details.

---

## Claude Code Skill

This repository includes a [Claude Code](https://claude.ai/claude-code) skill at `.claude/skills/vfx-turnover/`. When working in this project, the following slash commands are available:

To make the skills and commands available system-wide (in any Claude Code session, not just this project), copy or symlink them to your global `~/.claude/` folder:

```bash
# Skills (reference + slash command implementations)
cp -r .claude/skills/vfx-turnover ~/.claude/skills/

# Slash commands
for f in .claude/commands/vfx-*.md; do
  ln -sf "$(pwd)/$f" ~/.claude/commands/
done
```

| Command | Description |
|---------|-------------|
| `/vfx-turnover` | Reference for the tool's CLI, project JSON structure, and AAF workflow |
| `/vfx-markers` | Export markers and subcaps (saved defaults) |
| `/vfx-pulls` | Export ALE and Pulls EDL |
| `/vfx-tab` | Export TAB spreadsheet file |
| `/vfx-merge ALE` | Merge an ALE file with project VFX IDs and export an enhanced TAB file |
| `/vfx-ids` | List VFX IDs for all library timelines (active marked with `*`); pass a name or index to filter to one timeline |
| `/vfx-rename OLD NEW` | Rename VFX IDs using a before/after example (applies pattern to all IDs) |
| `/vfx-status` | Show loaded project summary |
| `/vfx-report TAB [DIR]` | Generate a PDF report from a TAB file with optional thumbnails folder |

---

## Settings

Initialized with `-i` and persisted at `~/.config/vfx_turnover/vfx_project.json`.

| Setting | Description | Default |
|---------|-------------|---------|
| Project ID | Project identifier used in VFX IDs | `PID` |
| FPS | Frame rate for timecode calculations | `24` |
| Resolution | Output resolution | `1080` |
| Handles | Extra frames added to pulls | `10` |
