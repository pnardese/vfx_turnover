Export a PDF report from a TAB spreadsheet file with thumbnails.

The user must supply the TAB file and (optionally) the thumbnails folder as arguments.

Examples:
- `/vfx-report SCENA_53_EDIT_TAB.txt`
- `/vfx-report SCENA_53_EDIT_TAB.txt ./53\ thumbnails`
- `/vfx-report SCENA_53_EDIT_TAB.txt "/path/to/53 thumbnails"`

Parse `$ARGUMENTS` to extract:
1. The TAB file path (first argument)
2. The thumbnails folder path (second argument, optional)

Then run:

```bash
printf 'y\n' | tab-to-pdf "<TAB_FILE>" -t "<THUMBNAILS_DIR>"
```

If no thumbnails folder is provided, omit the `-t` flag:

```bash
printf 'y\n' | tab-to-pdf "<TAB_FILE>"
```

Report the output PDF file name and how many thumbnails were matched.
