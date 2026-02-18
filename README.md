## Python script to help manage the VFX workflow in Avid Media Composer

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

### Installation

Requires Python 3.10+ and [pipx](https://pipx.pypa.io).

```bash
git clone https://github.com/pnardese/vfx_turnover.git
cd vfx_turnover
pipx install -e .
```

The `vfx-turnover` command will be available system-wide without activating a virtual environment.

To update after pulling new changes:
```bash
pipx reinstall vfx-turnover
```

### Supported EDL Formats

- **Avid FIle_129 EDL** - Standard Avid Media Composer EDL format
- **CMX3600 EDL** - Industry standard CMX3600 format

### Options:

- import an EDL (Avid or CMX3600 format) and create a project file
```
vfx-turnover -e timeline.edl
```
- export a marker text file for AVID (interactive options: user name, track, color, position)
```
vfx-turnover -m
```
- export a subcaps text file for AVID
```
vfx-turnover -s
```
- export an ALE for creating pulls in AVID bin
```
vfx-turnover -p
```
- export an EDL for cutting in pulls
```
vfx-turnover -x
```
- export a dummy EDL to be used as a reference in AVID
```
vfx-turnover -d
```
- export a TAB delimited text file for importing it in a spreadsheet
```
vfx-turnover -g
```
- export an AAF with VFX ID clip notes, requires a source AAF
```
vfx-turnover -a source.aaf
```
- export an EDL to cut in final VFX shots, requires an AVID bin (TAB)
```
vfx-turnover -f avid_bin.txt
```

All exported files are saved in the same folder as the original EDL.

### Parameters file

The script persists project-specific settings in:

```
~/.config/vfx_turnover/vfx_project.json
```

This file is created automatically on first run and stores parameters such as the project name and other configuration values, so they don't need to be re-entered each session.

### Markers export interactive options (`-m`):

When exporting markers, the script prompts for the following options:

| Option | Choices | Default |
|--------|---------|---------|
| AVID user name | any string | `vfx` |
| Track | `TC`, `V1`–`V8` | `V1` |
| Marker color | `green`, `red`, `blue`, `cyan`, `magenta`, `yellow`, `black`, `white` | `green` |
| Marker position | `start`, `middle` | `start` |
