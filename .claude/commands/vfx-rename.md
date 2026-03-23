Rename VFX IDs in the loaded vfx-turnover project using a before/after example. The example defines a transformation that is applied to ALL VFX IDs in the project, unless the user explicitly states the change is only for specific IDs.

Arguments: `$ARGUMENTS` — two VFX IDs separated by a space: `OLD_ID NEW_ID`
Example: `/vfx-rename gdn_053_0010_BG GDN_053_0010`

Steps:
1. Parse `$ARGUMENTS` into `OLD_ID` and `NEW_ID`. If not provided or malformed, read `~/.config/vfx_turnover/vfx_project.json`, display the list of VFX IDs, and ask the user for the OLD_ID and NEW_ID before continuing.
2. Read `~/.config/vfx_turnover/vfx_project.json`.
3. Infer the transformation by comparing OLD_ID and NEW_ID segment by segment (split on `_`):
   - For each segment position, record what changed (e.g. case, value, removed/added segments).
   - Example: `gdn_053_0010_BG` → `GDN_053_0010` means: uppercase all segments, drop the last segment `_BG`.
4. Apply that same transformation to every VFX ID in the project. For each event:
   - Derive the new VFX ID by applying the inferred transformation to the event's current `VFX ID`.
   - If `LOC` equals the current `VFX ID`, update `LOC` to the new value.
   - If `clip_note` starts with the current `VFX ID`, replace that prefix with the new value (keep the rest unchanged).
   - If an event's VFX ID has a different structure (e.g. different number of segments) and the transformation cannot be applied unambiguously, skip it and warn.
5. If no events were updated, report the error and stop.
6. Write the updated project back to `~/.config/vfx_turnover/vfx_project.json` (same format, indent=4).
7. Print a table of every old → new ID change made, and the total count of updated events.
