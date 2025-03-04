## Python script to help manage the VFX workflow in Avid Media Composer

### Options:

- load an EDL and create a JSON file with EDL events
```
python vfx_turnover -e timeline.edl
```
- load a json file and create a marker text file for AVID
```
python vfx_turnover -m timeline.json
```
- load a json file and create a subcaps text file for AVID
```
python vfx_turnover -s timeline.json
```
- load a json file and create an ALE for creating pulls AVID bin
```
python vfx_turnover -p timeline.json
```
- load a json file and create an EDL for cutting in pulls AVID bin
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
- load a json file and a TAB bin text file to create an EDL to cut in VFX shots
```
python vfx_turnover -f timeline.json avid_bin.txt
```
