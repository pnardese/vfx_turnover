List all VFX IDs from the loaded vfx-turnover project.

Read `~/.config/vfx_turnover/vfx_project.json`. First print the EDL/AAF filename from `config.edl_file`, then display a table with these columns for every event, sorted by VFX ID:

| VFX ID | Job Description | Tape | Source In | Source Out | Record In | Record Out |

Use the following JSON fields:
- VFX ID → `VFX ID`
- Job Description → `job_description`
- Tape → `reel`
- Source In → `source_start_TC`
- Source Out → `source_end_TC`
- Record In → `record_start_TC`
- Record Out → `record_end_TC`

- Events with an empty `VFX ID` must be included with `(missing)` in the VFX ID column.
- If any missing VFX IDs are present, print a warning after the table stating how many events are missing a VFX ID.
