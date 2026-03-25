---
name: vfx-ids
description: List all VFX IDs from the vfx-turnover project library — all timelines or a specific one by name or index.
---

Read `~/.config/vfx_turnover/vfx_project.json` and list VFX IDs from the library.

- No argument → list all timelines, one section each, active marked with `*`
- Argument → match by partial filename or 1-based index, list only that timeline

Table columns: `#`, `VFX ID`, `Job Description`, `Tape`, `Source In`, `Source Out`, `Record In`, `Record Out`.
Events with empty `VFX ID` show `(missing)`. Print shot count per section and a warning if any IDs are missing.
