List all VFX IDs with their tape names from the loaded vfx-turnover project.

Read `~/.config/vfx_turnover/vfx_project.json` and display a table of VFX ID and tape name (source reel) for every event, sorted by VFX ID.

- Events with an empty `VFX ID` must be included in the table with `(missing)` in the VFX ID column.
- If any missing VFX IDs are present, print a warning after the table stating how many events are missing a VFX ID.
