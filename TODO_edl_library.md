# TODO: EDL/AAF Library

## Goal

Track multiple EDL/AAF imports in the project file. One entry is always "active" — all exports and changelists operate on it.

- **`-e FILE`** — import EDL/AAF into the library (adds if new, updates in place if already present) and **immediately set as the active timeline**
- **`-e` (no argument)** — interactive library manager: select active, remove entry, clear all

---

## JSON Schema Change

### Current schema (flat)
```json
{
  "config": {
    "edl_file": "timeline.edl",
    "edl_dir": "/path/to",
    "ProjectID": "GDN",
    "fps": "24",
    "resolution": "1080",
    "handles": 10,
    "markers": { ... }
  },
  "edl_metadata": { ... },
  "events": [ ... ]
}
```

### New schema (library)
```json
{
  "config": {
    "active": "timeline.edl",
    "ProjectID": "GDN",
    "fps": "24",
    "resolution": "1080",
    "handles": 10,
    "markers": { ... }
  },
  "library": [
    {
      "edl_file": "timeline.edl",
      "edl_dir": "/path/to",
      "edl_metadata": { ... },
      "events": [ ... ]
    },
    {
      "edl_file": "timeline_v2.edl",
      "edl_dir": "/path/to",
      "edl_metadata": { ... },
      "events": [ ... ]
    }
  ]
}
```

- `config.active` — basename of the currently active EDL/AAF
- `edl_file`, `edl_dir`, `edl_metadata`, `events` move into each library entry
- `config` retains only project-wide settings (ProjectID, fps, resolution, handles, markers)

---

## Migration

Not required. Old format project files are not supported — delete `~/.config/vfx_turnover/vfx_project.json` and re-initialise with `-i`.

---

## New Helper: `get_active_entry(project) -> dict`

Returns the library entry whose `edl_file` matches `config['active']`. Falls back to first entry if `active` is missing or not found.

```python
def get_active_entry(project: dict) -> dict:
    active = project['config'].get('active')
    for entry in project.get('library', []):
        if entry['edl_file'] == active:
            return entry
    entries = project.get('library', [])
    return entries[0] if entries else {}
```

---

## `load_project()` Update

- After migration, call `get_active_entry(project)` and print `entry['edl_file']`
- Globals `fps`, `handles`, `ProjectID` still come from `config` (unchanged)

---

## `-e` Argparse Change

Current:
```python
parser.add_argument('-e', '--edl', metavar='FILE', help='...')
```

New (optional argument, same `nargs='?'` pattern as `-t`):
```python
parser.add_argument('-e', '--edl', nargs='?', const=True, metavar='FILE', help='...')
```

---

## `-e FILE` Handler Update

```python
if isinstance(args.edl, str):
    # import file into library
    input_file = args.edl
    input_dir = os.path.dirname(os.path.abspath(input_file))
    file_data = aaf_to_json(input_file) if input_file.lower().endswith('.aaf') else edl_to_json(input_file)
    new_entry = {
        'edl_file':    os.path.basename(input_file),
        'edl_dir':     input_dir,
        'edl_metadata': file_data['edl_metadata'],
        'events':       file_data['events'],
    }
    # add or update in place
    library = project.get('library', [])
    for i, entry in enumerate(library):
        if entry['edl_file'] == new_entry['edl_file']:
            library[i] = new_entry
            break
    else:
        library.append(new_entry)
    project['library'] = library
    project['config']['active'] = new_entry['edl_file']
    save_project(project)
    print(f"Imported: {new_entry['edl_file']}  ({len(new_entry['events'])} events)")
    print(f"Active:   {new_entry['edl_file']}")
```

---

## `-e` (no argument) — Interactive Library Manager

```python
elif args.edl is True:
    project = load_project()
    library_manager(project)
```

### `library_manager(project)`

Loop displaying the library and offering options:

```
Library (2 entries):
  * 1  timeline.edl        45 shots   /path/to
    2  timeline_v2.edl     48 shots   /path/to/v2

[L] Load (set active)   [R] Remove   [C] Clear all   [Q] Quit
```

- **L** — prompt for entry number → set `config['active']` → save
- **R** — prompt for entry number → remove from list → if removed entry was active, set active to first remaining (or clear)
- **C** — confirm → clear `library` list and `config['active']`
- **Q** — exit

Print updated library after each action.

---

## Export Functions Update

All export functions that load `PROJECT_FILE` themselves need to call `get_active_entry()` to read `edl_dir` and `events`. Current pattern:

```python
# current (breaks with new schema)
json_file['config']['edl_dir']
json_file['events']
```

New pattern after loading JSON:
```python
entry = get_active_entry(json_file)
entry['edl_dir']
entry['events']
entry['edl_metadata']
```

Functions to update:
- `export_google_tab`
- `merge_ale_tab`
- `export_ale_pulls`
- `export_pulls_edl`
- `json_to_markers`
- `json_to_subcaps`
- `export_final_vfx_edl`
- `json_to_aaf`
- `check_aaf_consistency`

Also update all `main()` export handlers that read `project['config']['edl_dir']` and `project['config']['edl_file']` — replace with `get_active_entry(project)`.

---

## `-c` (Changelist) Update

`old_events` currently comes from `project['events']`. Change to:

```python
old_events = get_active_entry(project)['events']
```

---

## `-a` (AAF Export) Update

Currently checks `project['config']['edl_file']` for `.aaf` extension. Change to:

```python
entry = get_active_entry(project)
aaf_file = os.path.join(entry['edl_dir'], entry['edl_file'])
```

---

## `-i` (Init) Update

**`-i` clears the entire project file** — library, active entry, and all settings — then prompts for fresh settings. This is the "start a new project" operation.

New `-i` behaviour:
1. Prompt for ProjectID, fps, resolution, handles (no defaults from existing file — file is being wiped)
2. Write a fresh project JSON with empty library and no active entry:
```json
{
  "config": {
    "active": null,
    "ProjectID": "...",
    "fps": "...",
    "resolution": "...",
    "handles": 10,
    "markers": { ... }
  },
  "library": []
}
```
3. Print confirmation

Remove the current behaviour of reading the old config as defaults.

---

## `vfx-status` Skill Update

Currently reads `config['edl_file']`. Update to read `config['active']` and show library count.

---

## Files to Modify

- `vfx_turnover.py` — all changes above
- `README.md` — document new `-e` behaviour and library concept
- `.claude/skills/vfx-turnover/SKILL.md` — update `-e` description

---

## Out of Scope

- Per-entry overrides of fps/handles/ProjectID (all entries share project-wide settings)
- Exporting from multiple library entries in one command
- Library stored separately from the project JSON
