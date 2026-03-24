Merge an ALE file with the loaded vfx-turnover project VFX IDs and export an enhanced TAB file.

The user must supply the ALE file path as the argument to this command (e.g. `/vfx-merge dailies.ALE`).

Run the following command, confirming any overwrite:

```bash
printf 'y\n' | vfx-turnover -t $ARGUMENTS
```

Report the output file name, the match count, and any warnings about unmatched events.
