List all VFX IDs from the vfx-turnover project library.

Read `~/.config/vfx_turnover/vfx_project.json`.

The JSON has this structure:
- `config.active` — filename of the active timeline
- `library` — array of entries, each with `edl_file`, `edl_dir`, and `events`

Each event has: `VFX ID`, `job_description`, `reel`, `source_start_TC`, `source_end_TC`, `record_start_TC`, `record_end_TC`.

## Behaviour

**No argument (`/vfx-ids`):**
List VFX IDs for every timeline in the library, one section per timeline.
Mark the active timeline with `*`.

**With argument (`/vfx-ids <name_or_number>`):**
Match the argument against library entries by:
1. Exact or partial `edl_file` name (case-insensitive)
2. 1-based index number

List VFX IDs only for that timeline.

## Output format

For each timeline section, print a header:

```
* SCENA 53 EDIT.edl  (active)     /path/to/edls
  SCENA 54 EDIT.edl               /path/to/edls
```

Then a table:

| # | VFX ID | Job Description | Tape | Source In | Source Out | Record In | Record Out |
|---|--------|-----------------|------|-----------|------------|-----------|------------|

- Events with an empty `VFX ID` → show `(missing)` in the VFX ID column
- Sort rows by record in timecode (preserve original order)
- Print shot count at the end of each section
- If any missing VFX IDs are present, print a warning after the table
