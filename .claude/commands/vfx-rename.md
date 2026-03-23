Rename a VFX ID in the loaded vfx-turnover project using a before/after example.

Arguments: `$ARGUMENTS` — two VFX IDs separated by a space: `OLD_ID NEW_ID`
Example: `/vfx-rename GDN_033_0010 GDN_033_0020`

Steps:
1. Parse `$ARGUMENTS` into `OLD_ID` and `NEW_ID`. If not provided or malformed, read `~/.config/vfx_turnover/vfx_project.json`, display the list of VFX IDs, and ask the user for the OLD_ID and NEW_ID before continuing.
2. Read `~/.config/vfx_turnover/vfx_project.json`.
3. Find every event where `VFX ID == OLD_ID`. For each matching event:
   - Set `VFX ID` to `NEW_ID`
   - If `LOC` equals `OLD_ID`, set `LOC` to `NEW_ID`
   - If `clip_note` starts with `OLD_ID`, replace that prefix with `NEW_ID` (keep the rest of the string unchanged)
4. If no events matched, report the error and stop.
5. Write the updated project back to `~/.config/vfx_turnover/vfx_project.json` (same format, indent=4).
6. Confirm: print how many events were updated, and the old → new ID.
