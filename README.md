## Python script to help manage the VFX workflow in Avid Media Composer

### Supported EDL Formats

- **Avid FIle_129 EDL** - Standard Avid Media Composer EDL format
- **CMX3600 EDL** - Industry standard CMX3600 format

### Options:

- load an EDL (Avid or CMX3600 format) and create a JSON file with EDL events
```
python vfx_turnover -e timeline.edl
```
- load a json file and create a marker text file for AVID (interactive options: user name, track, color, position)
```
python vfx_turnover -m timeline.json
```
- load a json file and create a subcaps text file for AVID
```
python vfx_turnover -s timeline.json
```
- load a json file and create an ALE for creating pulls in AVID bin
```
python vfx_turnover -p timeline.json
```
- load a json file and create an EDL for cutting in pulls
```
python vfx_turnover -x timeline.json
```
- load a json file and create a dummy EDL to be used as a reference in AVID
```
python vfx_turnover -d timeline.json
```
- load a json file and create a TAB delimited text file for importing it in a spreadsheet
```
python vfx_turnover -g timeline.json
```
- load a json file and a source AAF to create a new AAF with VFX ID clip notes on each video clip
```
python vfx_turnover -a timeline.json source.aaf
```
- load a json file and a TAB bin text file to create an EDL to cut in VFX shots
```
python vfx_turnover -f timeline.json avid_bin.txt
```

### Markers export interactive options (`-m`):

When exporting markers, the script prompts for the following options:

| Option | Choices | Default |
|--------|---------|---------|
| AVID user name | any string | `vfx` |
| Track | `TC`, `V1`–`V8` | `V1` |
| Marker color | `green`, `red`, `blue`, `cyan`, `magenta`, `yellow`, `black`, `white` | `green` |
| Marker position | `start`, `middle` | `start` |
