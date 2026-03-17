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

Before importing any EDL or AAF, initialize the project with your settings:

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

### 2. Import EDL

Create an EDL (File_129 or CMX3600) from the Avid video track containing only shots planned for VFX, simplify timeline by removing transitions, effects and committing groups. In List Options in Avid, check: **Clip Names**, **Source File Name**, and **Markers**.

VFX IDs are generated automatically based on scene numbers: `ProjectID_Scene_num`, where `num` is a 4-digit progressive number like `0010`, `0020`, `0030`, etc. Auto-generation only happens when the EDL has **no markers at all**. If the EDL has markers but some events are missing a VFX ID, the script stops with an error listing the affected events.

Existing markers on the timeline are imported as existing VFX IDs (found in the EDL as `*LOC` lines). If you add VFX shots in Avid, add markers with their new VFX IDs before re-importing.

![Configuration of the list tool in Avid Media Composer for EDL exporting](imgs/01_create_edl.png)

```
vfx-turnover -e timeline.edl
```

### Alternative: Import from AAF

If no EDL is available, you can import the VFX sequence directly from an Avid AAF export. This reads the timeline clips, extracts scene numbers from the Avid clip names, generates VFX IDs, and writes them as clip notes, timeline markers, and clip color into a new AAF — all in one step.

Simplify the timeline in Avid before exporting (remove transitions, effects, commit groups), then export the sequence as AAF and run:

```
vfx-turnover -a sequence.aaf
```

The project file is created using the settings from `-i`. The script then prompts for user, marker color, marker position, and clip color. The output AAF is saved next to the source AAF with `_new` appended.

Before exporting, the script scans the full timeline and checks for inconsistencies: if any clip already has both a clip note and a timeline marker but they carry different VFX IDs, all mismatches are reported and the script exits without writing any file:

```
Warning: 2 VFX ID mismatch(es) found — fix the source AAF before exporting:

  [00:58:26:09]  33-2-/01 A
    Clip note : GDN_033_100
    Marker    : GDN_033_105
  [00:59:01:04]  33-4-/01 A
    Clip note : GDN_033_1
    Marker    : GDN_033_130
```

Resolve the mismatches in Avid before re-running.

> **Note:** VFX IDs are generated from the Avid bin clip names (e.g. `33-2-/01 A` → scene `033`). Source and record timecodes are extracted from the AAF reference chain and match the EDL output for the same sequence.

---

### 3. Export Markers and Subcaps

Export markers and subcaps and import them into Avid to help keep track of VFX shots.

```
vfx-turnover -m
```

Both a markers file and a subcaps file are exported in one step. The script prompts for:

| Option | Choices | Default |
|--------|---------|---------|
| AVID user name | any string | `vfx` |
| Track | `TC`, `V1`–`V8` | `V1` |
| Marker color | `green`, `red`, `blue`, `cyan`, `magenta`, `yellow`, `black`, `white` | `green` |
| Marker position | `start`, `middle` | `middle` |

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
| `Comments` | *(empty)* |
| `Status` | *(empty)* |
| `Date` | *(empty)* |
| `Duration` | Source clip duration as timecode |
| `Start` | Source start timecode |
| `End` | Source end timecode |
| `Frame Count Duration` | Duration in frames |
| `Pull Handles` | Handle frames configured for the project |
| `Tape` | Source reel / tape name |

### 6. Export ALE Pulls and Pulls EDL

Export an ALE to create pull subclips and a Pulls EDL to cut them into a timeline — both exported in one step using the handle frames set in `-i`.

```
vfx-turnover -p
```

- **ALE file** — drag onto the Avid bin after selecting master clips. Import settings: *Merge events with known sources and automatically create subclips*.
- **Pulls EDL** — import into an Avid bin and relink to pull subclips using Names.

![Import settings](imgs/03_merge_events_ale.png)

![Relink configuration](imgs/04_relink_edl_pulls_v02.png)

### 7. Compare EDL Versions (Changelist)

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

### 8. VFX Cut-ins

When you receive incoming VFX (`.mov` files), import them into Avid, then export the bin in TAB format. Use the TAB file to generate an EDL for cutting the VFX into the timeline. Required bin columns: **Color**, **Name**, **Duration**, **Start**, **End**, **Tape**.

```
vfx-turnover -f avid_bin.txt
```

![Columns to export from Avid bin as TAB text file](imgs/05_vfx_cutins.png)

---

## All Options

| Option | Description |
|--------|-------------|
| `-i` | Initialize project settings (Project ID, FPS, resolution, handles) |
| `-e timeline.edl` | Import an EDL and create/update the project file |
| `-a sequence.aaf` | Import an AAF timeline, create project and export a new AAF with VFX ID clip notes, markers and clip color |
| `-m` | Export markers and subcaps for Avid (interactive options) |
| `-p` | Export ALE and Pulls EDL for creating pulls in Avid bin |
| `-t` | Export a TAB-delimited text file for spreadsheet import |
| `-f avid_bin.txt` | Export an EDL to cut in final VFX shots (requires Avid bin TAB) |
| `-c new.edl` | Compare new EDL against loaded project and export changelist markers and TAB files |

All exported files are saved in the same folder as the original EDL.

---

## Settings

Initialized with `-i` and persisted at `~/.config/vfx_turnover/vfx_project.json`.

| Setting | Description | Default |
|---------|-------------|---------|
| Project ID | Project identifier used in VFX IDs | `PID` |
| FPS | Frame rate for timecode calculations | `24` |
| Resolution | Output resolution | `1080` |
| Handles | Extra frames added to pulls | `10` |
