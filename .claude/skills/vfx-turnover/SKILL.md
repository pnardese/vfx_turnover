---
name: vfx-turnover
description: Reference for working with the vfx-turnover CLI tool and its codebase. Use when adding features, fixing bugs, or understanding the tool's behavior — CLI flags, project JSON structure, VFX ID naming, export formats, and AAF workflow.
---

# vfx-turnover Reference

## Overview

Single-file CLI tool: `vfx_turnover.py`, installed via `pipx install -e .` as `vfx-turnover`.
State persisted at `~/.config/vfx_turnover/vfx_project.json`.

## Installation

Requires Python 3.10+ and [pipx](https://pipx.pypa.io).

```bash
git clone https://github.com/pnardese/vfx_turnover.git
cd vfx_turnover
pipx install -e .
```

After pulling updates:
```bash
pipx reinstall vfx-turnover
```

Dependencies (from `requirements.txt`): `aaf2`, `timecode`, `pandas`.

## CLI Flags

| Flag | Name | Description |
|------|------|-------------|
| `-i` | `--init` | Initialize project settings (ProjectID, fps, resolution, handles). Prompts interactively, preserves existing config values as defaults. |
| `-e FILE` | `--edl` | Import an EDL or AAF file. Detects by extension (`.aaf` → `aaf_to_json`; otherwise → `edl_to_json`). Creates/overwrites project JSON. |
| `-a` | `--aaf_write` | Export a new AAF with VFX IDs as clip notes, markers, and clip color. Requires project imported from an AAF via `-e`. Runs consistency check first. |
| `-m` | `--markers` | Export markers and subcaps files for Avid. Prompts for user, track, color, position. |
| `-s` | `--subcaps` | Export only the subcaps file (no prompts). |
| `-p` | `--pulls` | Export ALE and Pulls EDL for creating pull subclips in Avid. |
| `-t` | `--tab` | Export TAB-delimited spreadsheet file. |
| `-f BIN` | `--final` | Export EDL for cutting final VFX into Avid. Requires an Avid bin TAB file as argument. |
| `-c NEW_EDL` | `--compare` | Compare a new EDL against the loaded project and export changelist markers + TAB files. |

## Project JSON Structure

Path: `~/.config/vfx_turnover/vfx_project.json`

```json
{
    "config": {
        "edl_file": "timeline.edl",           // basename of source EDL/AAF
        "edl_dir": "/path/to/edl",             // absolute dir; all exports go here
        "ProjectID": "GDN",                    // used in VFX ID generation
        "fps": "24",                           // string, one of FPS_CHOICES
        "resolution": "1080",                  // string, stored as-is
        "handles": 10,                         // int, extra frames for pulls
        "markers": {
            "user": "vfx",
            "track": "V1",                     // TC, V1–V8
            "color": "green",
            "position": "start",               // start | middle
            "clip_color": "none"               // -a only; 32 Avid colors or 'none'
        }
    },
    "edl_metadata": {
        "edl_title": "timeline",
        "edl_fcm": "NON-DROP FRAME"
    },
    "events": [ ... ]                          // list of event dicts
}
```

### Event dict fields

Both EDL and AAF imports produce the same event structure:

```json
{
    "type": "event",
    "event_number": "1",
    "reel": "A059_A006_0519W9_001",
    "track": "V",
    "transition": "C",
    "source_start_TC": "00:58:26:09",
    "source_end_TC":   "00:58:30:15",
    "record_start_TC": "01:00:00:00",
    "record_end_TC":   "01:00:04:06",
    "FROM": "33-2-/01 A",           // subclip name (scene-based)
    "LOC": "GDN_033_0010",          // VFX ID from EDL *LOC marker; empty if auto-generated
    "SOURCE": "A059_A006_0519W9_001",
    "VFX ID": "GDN_033_0010",       // final VFX ID used by all exports
    "job_description": "REMOVE BACKGROUND",  // text after VFX ID in marker/clip note
    "clip_note": "GDN_033_0010 REMOVE BACKGROUND",  // raw _COMMENT value (set by -a)
    "color": "none",                // Avid clip color name or 'none' (set by -a)
    "has_clip_note": false,         // AAF import only: was _COMMENT present?
    "has_marker": false             // AAF import only: was EventMobSlot marker present?
}
```

`LOC` is set only for EDL import when a `*LOC` line is found. It drives VFX ID matching in `compare_edls` — auto-generated IDs are NOT used for matching (they shift when clips are added/removed).

## VFX ID Naming

Format: `{ProjectID}_{scene}_{counter}` — e.g. `GDN_033_0010`

- `scene`: 3-digit zero-padded scene number extracted from clip name (first `\d+` match), e.g. clip `33-2-/01 A` → `033`
- `counter`: 4-digit, starts at `0010`, increments by 10 per scene; resets to `0010` on scene change
- Auto-generation only when **no clips** have existing IDs (all-or-nothing)
- If some clips have IDs and others don't → error listing affected clips/TCs

Priority when reading existing IDs (clip note > marker > auto-generated):
```python
vfx_id = clip_note_id or marker_id or generated_id
job_description = clip_note_desc or marker_desc
```

## Output Files

All outputs are saved in `project['config']['edl_dir']`, named from `edl_stem` (`os.path.splitext(edl_file)[0]`):

| Flag | Output file(s) |
|------|---------------|
| `-m` | `<stem>_markers.txt`, `<stem>_subcaps.txt` |
| `-s` | `<stem>_subcaps.txt` |
| `-p` | `<stem>.ALE`, `<stem>_pulls.edl` |
| `-t` | `<stem>_TAB.txt` |
| `-f` | `<stem>_vfx_final.edl` |
| `-c` | next to the NEW edl: `<new_stem>_changelist_markers.txt`, `<new_stem>_changelist_TAB.txt` |
| `-a` | next to source AAF: `<stem>_new.aaf` |

All exports call `confirm_overwrite(path)` and prompt before overwriting.

## Markers File Format

Tab-delimited, one line per event:
```
user\trecord_TC\ttrack\tcolor\tcomment\t1
```
`comment` = `VFX_ID job_description` if job_description present, else just `VFX_ID`.
Position `middle` → TC = `record_start + half_duration`.

## Subcaps File Format
```
<begin subtitles>
REC_START REC_END
VFX_ID

...
<end subtitles>
```

## ALE Pulls Format

Standard Avid ALE with columns: `Name`, `Tracks`, `Start`, `End`, `Tape`.
Source TCs are expanded by `handles` frames on both sides.

## TAB File Columns

`#`, `Name`, `Thumbnail`(empty), `Comments`(job_description), `Status`(empty), `Date`(empty), `Duration`, `Start`, `End`, `Frame Count Duration`, `Handles`, `Tape`

## Changelist (`-c`)

`compare_edls(old_events, new_events, fps_val, handles_val)` returns events with `change_status`:

| Status | Meaning |
|--------|---------|
| `unchanged` | no change |
| `new` | not in old project |
| `removed` | in old but not new |
| `moved` | record TC shifted, source unchanged |
| `trimmed_ok` | source trimmed, within handles → no pull |
| `trimmed_pull` | source trimmed, beyond handles → pull needed |
| `moved_trimmed_ok` | moved + trimmed, within handles |
| `moved_trimmed_pull` | moved + trimmed, beyond handles |

**Matching logic** (order matters):
1. VFX ID match — only if the old event has a `LOC` value (i.e. came from a real marker, not auto-generated)
2. Fallback: `reel + source_start_TC` key match

**Move detection**: `moved = (rec_in_d != src_in_d) OR (rec_out_d != src_out_d)`
Frame deltas: `+` = extended, `-` = reduced. Within-handles check: new source must stay within `old ± handles` on each end.

**Marker label format** (written to changelist_markers.txt):
```
GDN_033_0010 NEW - NEED TO PULL
GDN_033_0020 REMOVED
GDN_033_0030 MOVED
GDN_033_0040 TRIMMED TAIL +7f - NO PULL NEEDED
GDN_033_0050 TRIMMED TAIL +15f - NEED TO PULL
GDN_033_0060 TRIMMED HEAD -5f - NO PULL NEEDED
GDN_033_0070 TRIMMED HEAD & TAIL H:-3f T:+8f - NO PULL NEEDED
GDN_033_0080 MOVED TRIMMED TAIL +4f - NEED TO PULL
```

## AAF Import (`-e sequence.aaf` → `aaf_to_json`)

- Finds main `CompositionMob` with a picture slot
- Sequence start TC from `Timecode` slot (default `01:00:00:00`)
- Iterates `video_slot.segment.components`; advances `timeline_pos` for every component including `Filler`
- Handles `SourceClip`, `Selector` (uses `comp['Selected'].value`; `_COMMENT` lives on the `Selector`), `OperationGroup` (iterates `InputSegments`)
- Source TC from 4-level mob chain: `SubClip → MasterMob → CDCIDescriptor → TapeDescriptor`; sum all `StartTime` offsets + `comp.start`
- Reel name: `TapeDescriptor.name` (with `_001`) → fallback `MasterMob.name` → `subclip.name`
- Reads existing clip notes (`_COMMENT` on `ComponentAttributeList`) and markers (`_ATN_CRM_COM` on `EventMobSlot`) for VFX ID reuse
- Reads existing clip color from `_COLOR_R/G/B`

## AAF Export (`-a` → `json_to_aaf`)

1. `check_aaf_consistency(aaf_file)` — exits if mismatch between clip note ID and marker ID on any clip
2. `prompt_aaf_options` — user, color, position, clip_color
3. Copies source AAF to `<stem>_new.aaf`
4. For each clip:
   - Writes/updates `_COMMENT` in `ComponentAttributeList` (uses `f.create.TaggedValue()`)
   - Writes `_COLOR_R/G/B` if `clip_color != 'none'` (16-bit: 8bit × 256)
   - Preserves existing markers; queues new `DescriptiveMarker` objects
5. Assigns all markers at once: `seq['Components'].value = all_markers`
6. After export, updates `event['clip_note']` and `event['color']` in project JSON

**Clip note write logic**:
- If clip already has a marker in the AAF: always write/update note with marker's VFX ID
- If no existing marker: write only if no clip note exists yet (`has_clip_note == False`)

**Effective VFX ID** in exported AAF: marker's ID takes priority over project JSON's ID.

## Constants

```python
FPS_CHOICES     = ['23.976', '24', '25', '29.97', '30', '59.94', '60']
MARKER_COLORS   = ['green', 'red', 'blue', 'cyan', 'magenta', 'yellow', 'black', 'white']
MARKER_TRACKS   = ['TC', 'V1', 'V2', 'V3', 'V4', 'V5', 'V6', 'V7', 'V8']
MARKER_POSITIONS = ['start', 'middle']
CLIP_COLORS     = ['none'] + list(CLIP_COLOR_MAP.keys())   # 33 entries
```

`MARKER_COLOR_MAP` maps color name → `(color_str, {'red': int, 'green': int, 'blue': int})` (0–65535).
`CLIP_COLOR_MAP` maps color name → `(r16, g16, b16)` (8-bit × 256).

## Key Gotchas

1. **`-a` requires project imported from AAF** — errors if `edl_file` doesn't end in `.aaf`
2. **Multicam/MultiGroup clips must be committed in Avid** before EDL or AAF export — otherwise wrong source TCs or missing reel names
3. **`markers` config key may be missing sub-keys** — always use `.get('key', DEFAULT_CONFIG['markers']['key'])` pattern; the `KeyError` fix is to fall back to `DEFAULT_CONFIG`
4. **Auto-generated VFX IDs are NOT used for changelist matching** — only `LOC`-sourced IDs match by VFX ID; others fall back to reel+TC
5. **`comp.start` not `comp['StartTime'].value`** — the `[]` accessor doesn't work for `StartTime` on `SourceClip`; use `getattr(comp, 'start', 0) or 0`
6. **ALE heading hardcodes `VIDEO_FORMAT 1080`** — not read from project config

## prompt_init_options / DEFAULT_CONFIG

```python
DEFAULT_CONFIG = {
    'ProjectID': 'PID',
    'fps': '24',
    'resolution': '1080',
    'handles': 10,
    'markers': {
        'user': 'vfx',
        'track': 'V1',
        'color': 'green',
        'position': 'start',
        'clip_color': 'none',
    }
}
```

`-i` preserves existing values as defaults when re-initializing. `-e` carries over `config` from existing project file (ProjectID, fps, resolution, handles, markers) so settings survive re-imports.
