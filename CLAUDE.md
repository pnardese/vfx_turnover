# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

`vfx_turnover.py` is a CLI tool for managing the VFX workflow in Avid Media Composer.
It imports EDL files (Avid File_129 or CMX3600), persists project state, and exports
various files: markers, subcaps, ALE pulls, EDLs, AAF with clip notes, and spreadsheet TABs.

## Environment

- Python 3.12, managed via pyenv
- Dependencies: `pandas`, `pyaaf2`, `timecode`
- Installed system-wide via `pipx install -e .` — command is `vfx-turnover`
- Local `.venv` also present for development

## Key Files

- `vfx_turnover.py` — single-file script, all logic here
- `pyproject.toml` — package metadata and entry point
- Project state persisted at `~/.config/vfx_turnover/vfx_project.json`

## Architecture

- `edl_to_json()` — parses EDL into internal JSON structure
- `load_project()` / `save_project()` — read/write persistent project file; set globals `FilmID`, `fps`, `handles`
- `main()` — CLI entry point via argparse
- Each export function (`json_to_markers`, `export_ale_pulls`, `json_to_aaf`, etc.) reads from the project file and writes output next to the original EDL

## AAF Reference

@/Users/enzo/Documents/dev/python/opetimelineio/CLAUDE.md

## Web App Integration Notes

The companion web app lives at `~/Documents/dev/web-vfx-turnover/web_vfx_turnover/index.html`.
It is a single-file static React app (no build step, no server) that reimplements all CLI
exports as in-browser JavaScript. All exports use the same pattern: generate text content,
download via Blob + ObjectURL.

### `-f` (export_final_vfx_edl)
Can be ported to JavaScript. The only dependency is `pandas.read_csv` for TSV parsing,
which is trivial to replace with a split-by-tab parser. The web app already loads the
Avid bin TAB file (`binData` state). This export is a straightforward JS addition.

### `-n` (json_to_aaf — AAF clip notes)
**Cannot run in the browser.** Requires `pyaaf2`, a C extension that reads/writes binary
Microsoft Structured Storage (AAF) format. No JS equivalent exists. Pyodide won't work
because of the compiled C extension.

**Planned approach: Flask microservice (local)**
- Small Flask API runs locally alongside the web app
- Endpoint: `POST /export-aaf` — accepts multipart (source AAF + JSON VFX IDs), returns modified AAF
- Web app adds an AAF upload zone and calls the local endpoint; all other exports remain client-side
- Web app should gracefully degrade when the server is not running (show an informative message)
- The Flask server is only required for this one feature
