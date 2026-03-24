# TODO: `-t` TAB Export — Extended with ALE Merge

## Goal

Extend the existing `-t` flag to accept an optional ALE file argument:

- `vfx-turnover -t` — standard TAB export (current behaviour, unchanged)
- `vfx-turnover -t 15_VIDEO.ALE` — merge ALE with project VFX IDs, export enhanced TAB

---

## ALE File Structure (reference: `15_VIDEO.ALE`)

```
Heading
FIELD_DELIM    TABS
VIDEO_FORMAT   1080
AUDIO_FORMAT   48khz
FPS            24

Column
Color    Name    Creation Date    Duration    Drive    Comments    IN-OUT    Camera    Mark IN    End    Mark OUT    Tracks    Start    Tape    Video    Camroll    Source File    Data

Data
         A056_A001_0519VW    5/20/23 7:15:14 PM    00:01:38:06    Progetti    ...    10:48:23:11    ...    V    10:46:45:05    A056_A001_0519VW_001    Avid DNx SQ (HD1080p)    A056_A001_0519VW    ...
```

Key columns used for matching:
- `Tape` — reel name **with** `_001` suffix (matches `event['reel']` directly)
- `Start` — source start TC (matches `event['source_start_TC']`)

---

## Implementation Steps

### 1. Change `-t` argparse entry

Current:
```python
parser.add_argument('-t', '--tab', action='store_true', help='Export TAB file...')
```

New (`nargs='?'` makes the argument optional):
```python
parser.add_argument(
    '-t', '--tab',
    nargs='?',
    const=True,      # value when -t is given with no argument
    metavar='ALE',
    help='Export TAB spreadsheet. Optionally pass an ALE file to merge ALE columns.'
)
```

### 2. Update handler in `main()`

```python
if args.tab is not None:
    if args.tab is True:
        # standard export — unchanged
        export_google_tab(PROJECT_FILE, os.path.join(edl_dir, edl_stem + '_TAB.txt'))
    else:
        # ALE merge
        ale_stem = os.path.splitext(os.path.basename(args.tab))[0]
        out_path = os.path.join(edl_dir, f"{edl_stem}_{ale_stem}_merge.txt")
        merge_ale_tab(PROJECT_FILE, args.tab, out_path)
```

### 3. `parse_ale(ale_file_path) -> dict`

Parse the three ALE sections:

```python
{
    'heading': {'FIELD_DELIM': 'TABS', 'VIDEO_FORMAT': '1080', 'FPS': '24', ...},
    'columns': ['Color', 'Name', 'Creation Date', 'Duration', ...],
    'rows': [
        {'Color': '', 'Name': 'A056_A001_0519VW', 'Tape': 'A056_A001_0519VW_001', 'Start': '10:46:45:05', ...},
        ...
    ]
}
```

Parsing rules:
- Read file, split on blank lines to delimit the three sections
- `Heading`: lines between `Heading` and next blank — each line is `key\tvalue`
- `Column`: single tab-delimited line after `Column` → list of column names
- `Data`: tab-delimited rows after `Data` → zip each row with column names into dicts

Abort with clear error if `Tape` or `Start` columns are missing.

### 4. ALE consistency check

- Compare `ale['heading']['FPS']` with project `fps` → **mismatch: error + abort**
- Compare `ale['heading']['VIDEO_FORMAT']` with project `resolution` → mismatch: warning only
- Print ALE heading summary on load (FPS, VIDEO_FORMAT, row count)

### 5. Build ALE lookup index

```python
ale_index = {}
for row in ale['rows']:
    key = (row['Tape'], row['Start'])
    if key in ale_index:
        print(f"  Warning: duplicate ALE entry for {key}, keeping first")
    else:
        ale_index[key] = row
```

### 6. `merge_ale_tab(json_file_path, ale_file_path, output_path)`

Determine extra ALE columns to append — all ALE columns **except** those already
covered by the standard TAB columns:

| ALE column | Action | Reason |
|------------|--------|--------|
| `Name`     | skip   | redundant with `VFX ID` |
| `Start`    | skip   | already in TAB as `Start` |
| `End`      | skip   | already in TAB as `End` |
| `Tape`     | skip   | already in TAB as `Tape` |
| `Duration` | skip   | already computed in TAB |
| `Comments` | rename to `ALE Comments` | avoid collision with TAB `Comments` (job_description) |
| all others | include as-is | `Color`, `Creation Date`, `Drive`, `IN-OUT`, `Camera`, `Mark IN`, `Mark OUT`, `Tracks`, `Video`, `Camroll`, `Source File`, `Data` |

Output heading row:
```
#  Name  Thumbnail  Comments  Status  Date  Duration  Start  End  Frame Count Duration  Handles  Tape  [extra ALE columns...]
```

For each project event:
1. Look up `ale_index[(event['reel'], event['source_start_TC'])]`
2. If matched → append ALE values for each extra column
3. If not matched → append empty strings; print per-event warning

### 7. Output file path

```
<edl_stem>_<ale_stem>_merge.txt
```

Example: `VFX_48.edl` + `15_VIDEO.ALE` → `VFX_48_15_VIDEO_merge.txt`

Saved in `edl_dir`. Call `confirm_overwrite()` before writing.

### 8. Summary output

```
  Merged TAB: VFX_48_15_VIDEO_merge.txt
  Matched:    42 / 45 events
  Unmatched:  3 events (no ALE row — ALE columns left empty)
  ALE rows not used: 12
```

---

## Edge Cases

| Case | Behaviour |
|------|-----------|
| FPS mismatch | Error + abort |
| Resolution mismatch | Warning only |
| Event not found in ALE | Empty ALE columns; warn per event |
| ALE row with no matching event | Count and report in summary |
| Duplicate `(Tape, Start)` in ALE | Warn; keep first |
| Missing `Tape` or `Start` column | Error + abort |

---

## Files to Modify

- `vfx_turnover.py` — change `-t` argparse entry; add `parse_ale()`, `merge_ale_tab()`; update handler in `main()`
- `README.md` — document the new `-t ALE` variant
