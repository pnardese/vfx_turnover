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

@.claude/skills/pyaaf2/SKILL.md




