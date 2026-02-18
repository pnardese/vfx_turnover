## Python script to help manage the VFX workflow in Avid Media Composer

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

- load an EDL (Avid or CMX3600 format) and create a JSON file with EDL events
```
vfx-turnover -e timeline.edl
```
- load a json file and create a marker text file for AVID (interactive options: user name, track, color, position)
```
vfx-turnover -m timeline.json
```
- load a json file and create a subcaps text file for AVID
```
vfx-turnover -s timeline.json
```
- load a json file and create an ALE for creating pulls in AVID bin
```
vfx-turnover -p timeline.json
```
- load a json file and create an EDL for cutting in pulls
```
vfx-turnover -x timeline.json
```
- load a json file and create a dummy EDL to be used as a reference in AVID
```
vfx-turnover -d timeline.json
```
- load a json file and create a TAB delimited text file for importing it in a spreadsheet
```
vfx-turnover -g timeline.json
```
- load a json file and a source AAF to create a new AAF with VFX ID clip notes on each video clip
```
vfx-turnover -a timeline.json source.aaf
```
- load a json file and a TAB bin text file to create an EDL to cut in VFX shots
```
vfx-turnover -f timeline.json avid_bin.txt
```

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
