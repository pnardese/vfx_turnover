import re
import json
import argparse
import os
import sys
import shutil
import time
import uuid
import aaf2
from timecode import Timecode
from pandas import read_csv

def create_string(separator: str, *args: str) -> str:
    string=""   
    for i in args:
        if i == args[-1]:
            string += i
        else:
            string += i + separator
    return string

PROJECT_DIR = os.path.join(os.path.expanduser('~'), '.config', 'vfx_turnover')
PROJECT_FILE = os.path.join(PROJECT_DIR, 'vfx_project.json')

FPS_CHOICES = ['23.976', '24', '25', '29.97', '30', '59.94', '60']

DEFAULT_CONFIG = {
    'ProjectID': 'PID',
    'fps': '24',
    'resolution': '1080',
    'handles': 10,
    'markers': {
        'user': 'vfx',
        'track': 'V1',
        'color': 'green',
        'position': 'start',
        'clip_color': 'none',
    }
}

def load_project():
    """Load project file, set globals, return data dict."""
    global ProjectID, fps, handles
    if not os.path.exists(PROJECT_FILE):
        print(f"Error: No project file found. Run -e first to import an EDL or AAF.", file=sys.stderr)
        sys.exit(1)
    with open(PROJECT_FILE) as f:
        project = json.load(f)
    cfg = project['config']
    ProjectID = cfg['ProjectID']
    fps = cfg['fps']
    handles = cfg['handles']
    print(f"EDL: {cfg['edl_file']}")
    return project

def save_project(project):
    """Write project dict to project file."""
    os.makedirs(PROJECT_DIR, exist_ok=True)
    with open(PROJECT_FILE, 'w') as f:
        json.dump(project, f, indent=4)


def confirm_overwrite(path: str) -> bool:
    """Return True if OK to write path — either it doesn't exist, or the user confirms."""
    if not os.path.exists(path):
        return True
    answer = input(f"  {os.path.basename(path)} already exists. Overwrite? [y/N]: ").strip().lower()
    return answer in ('y', 'yes')


def edl_to_json(edl_file: str):
    """Reads an EDL file, parses it, and returns the data as a dict."""
    
    def parse_edl_line(line: str) -> dict:
        """Parses a single line of an EDL and extracts relevant information."""
        match = re.match(r'(\d+)\s+(\w+)\s+(\w+)\s+(\w+)\s+(\d{2}:\d{2}:\d{2}:\d{2})\s+(\d{2}:\d{2}:\d{2}:\d{2})\s+(\d{2}:\d{2}:\d{2}:\d{2})\s+(\d{2}:\d{2}:\d{2}:\d{2})?', line)   # Define regex pattern
        if match:
            event_num, reel, track, transition, src_start, src_end, rec_start, rec_end = match.groups() # Unpack match groups
            return {
                "type": "event",  # Added type indicator
                "event_number": str(event_num), # Convert event number to string
                "reel": reel,   # Reel number
                "track": track, # Track number
                "transition": transition,   # Transition type
                "source_start_TC": src_start,   # Source start timecode
                "source_end_TC": src_end,   # Source end timecode
                "record_start_TC": rec_start,   # Record start timecode
                "record_end_TC": rec_end,   # Record end timecode
                "FROM": "",
                "LOC": "",
                "SOURCE": "",
                "VFX ID": "",
                "job_description": "",
                "clip_note": "",
                "color": "",
            }
        else:
            return None
        
    edl_data = {
        "edl_metadata": {
        "edl_title": "",
        "edl_fcm": "",
        },
        "events": [],  # List to hold parsed event lines
    }
    try:
        with open(edl_file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                elif line.startswith("TITLE:"):
                    edl_data["edl_metadata"]["edl_title"] = line.strip("TITLE:").strip()
                elif line.startswith("FCM:"):
                    edl_data["edl_metadata"]["edl_fcm"] = line.strip("FCM:").strip()
                elif re.match(r'^\d+\s+\w+\s+\w+\s+\w+\s+(\d{2}:\d{2}:\d{2}:\d{2})+\s+(\d{2}:\d{2}:\d{2}:\d{2})+\s+(\d{2}:\d{2}:\d{2}:\d{2})+\s+(\d{2}:\d{2}:\d{2}:\d{2})$', line):
                    parsed_line = parse_edl_line(line)
                    if parsed_line:
                        edl_data["events"].append(parsed_line)
                        last_event = edl_data["events"][-1]
                elif line.startswith("*FROM") or line.startswith("* FROM"):
                    from_index = line.find("FROM")
                    last_event["FROM"] = line[from_index + 4:].strip()
                elif line.startswith("*LOC:") or line.startswith("* LOC:"):
                    loc_index = line.find("LOC:")
                    loc_value = line[loc_index + 4:].strip()
                    last_event["LOC"] = loc_value
                    # LOC format: <timecode> <color> <VFX_ID> [job description...]
                    loc_parts = loc_value.split()
                    last_event["VFX ID"] = loc_parts[2] if len(loc_parts) > 2 else ""
                    last_event["job_description"] = ' '.join(loc_parts[3:]) if len(loc_parts) > 3 else ""
                elif line.startswith("*SOURCE") or line.startswith("* SOURCE"):
                    source_index = line.find("SOURCE")
                    source_value = line[source_index + 6:].strip()
                    if source_value.upper().startswith("FILE:"):
                        source_value = source_value[5:].strip()
                    last_event["SOURCE"] = source_value
                    if source_value and len(source_value) > len(last_event["reel"]):
                        last_event["reel"] = source_value
                else:
                    print(f"Skipping unparsable line: {line}")

    except FileNotFoundError:
        print(f"Error: EDL file not found: {edl_file}")
        sys.exit(1)

    # Post-parse: assign VFX IDs
    has_any_loc = any(e.get('LOC') for e in edl_data['events'])
    if not has_any_loc:
        # No LOC markers at all — auto-generate VFX IDs for every event
        last_scene = 0
        VFX_counter = 10
        for event in edl_data['events']:
            scene_clip_raw = event["FROM"].strip("*FROM CLIP NAME:").strip()
            m = re.search(r'\d+', scene_clip_raw)
            scene_clip = m.group().rjust(3, "0") if m else "000"
            if scene_clip == last_scene:
                VFX_counter += 10
            else:
                VFX_counter = 10
            event["VFX ID"] = create_string("_", ProjectID, scene_clip, str(VFX_counter).rjust(4, "0"))
            last_scene = scene_clip
    else:
        # EDL has LOC markers — warn about any event missing one, leave VFX ID empty
        missing = [e for e in edl_data['events'] if not e.get('LOC')]
        if missing:
            print(f"Warning: EDL has markers but {len(missing)} event(s) are missing a VFX ID:", file=sys.stderr)
            for e in missing:
                print(f"  Event {e['event_number']} ({e.get('reel', '')})", file=sys.stderr)
            print("Missing VFX IDs will be empty in the project.", file=sys.stderr)

    return edl_data


def prompt_init_options(config):
    """Prompt for project initialization settings."""
    project_id  = input(f"\nProject ID [default: {config.get('ProjectID', DEFAULT_CONFIG['ProjectID'])}]: ").strip() or config.get('ProjectID', DEFAULT_CONFIG['ProjectID'])
    fps_val     = prompt_choice("FPS:", FPS_CHOICES, config.get('fps', DEFAULT_CONFIG['fps']))
    resolution  = input(f"Resolution [default: {config.get('resolution', DEFAULT_CONFIG['resolution'])}]: ").strip() or config.get('resolution', DEFAULT_CONFIG['resolution'])
    raw         = input(f"Handles in frames [default: {config.get('handles', DEFAULT_CONFIG['handles'])}]: ").strip()
    handles_val = int(raw) if raw else config.get('handles', DEFAULT_CONFIG['handles'])
    return project_id, fps_val, resolution, handles_val


MARKER_TRACKS = ['TC', 'V1', 'V2', 'V3', 'V4', 'V5', 'V6', 'V7', 'V8']
MARKER_COLORS = ['green', 'red', 'blue', 'cyan', 'magenta', 'yellow', 'black', 'white']
MARKER_POSITIONS = ['start', 'middle']

# Maps color name → (Avid string, RGB dict for CommentMarkerColor 16-bit).
# Green values confirmed from VFX_48_markers.aaf reference.
MARKER_COLOR_MAP = {
    'green':   ('Green',   {'red': 13107, 'green': 52428, 'blue': 13107}),
    'red':     ('Red',     {'red': 52428, 'green': 13107, 'blue': 13107}),
    'blue':    ('Blue',    {'red': 13107, 'green': 13107, 'blue': 52428}),
    'cyan':    ('Cyan',    {'red': 13107, 'green': 52428, 'blue': 52428}),
    'magenta': ('Magenta', {'red': 52428, 'green': 13107, 'blue': 52428}),
    'yellow':  ('Yellow',  {'red': 52428, 'green': 52428, 'blue': 13107}),
    'black':   ('Black',   {'red': 0,     'green': 0,     'blue': 0}),
    'white':   ('White',   {'red': 65535, 'green': 65535, 'blue': 65535}),
}

# Maps Avid clip color name → (r16, g16, b16) stored in _COLOR_R/G/B TaggedValues.
# Values are 8-bit × 256. Extracted from VFX_48.Colore.aaf reference file.
CLIP_COLOR_MAP = {
    'dark blue':     (14592, 11776, 38144),
    'steel blue':    (15104, 25344, 37888),
    'dark green':    (16896, 32768, 13824),
    'cyan':          (16896, 54272, 62464),
    'teal':          (17920, 39168, 36864),
    'blue':          (22528, 17920, 58624),
    'dark grey':     (22784, 22784, 22784),
    'sky blue':      (23040, 38912, 58112),
    'green':         (25856, 50432, 21248),
    'dark purple':   (32256, 12544, 26880),
    'dark brown':    (32256, 20992, 13568),
    'olive':         (32256, 32768, 14336),
    'dark red':      (32768,  9216,  9216),
    'purple':        (36608,     0, 45824),
    'mint':          (43520, 65280, 49920),
    'crimson':       (48896,     0, 26112),
    'sand':          (48896, 43264, 36608),
    'light grey':    (48896, 48896, 48896),
    'violet':        (49408, 19200, 41216),
    'yellow-olive':  (49408, 50176, 22016),
    'brown':         (49664, 32256, 20992),
    'medium red':    (51200, 14592, 14592),
    'beige':         (56064, 55296, 47104),
    'light red':     (56832, 25600, 29696),
    'gold':          (58368, 50688,     0),
    'lavender':      (58880, 48640, 65280),
    'magenta':       (61440, 12800, 58880),
    'yellow-green':  (61952, 65280, 16384),
    'orange':        (62720, 33280, 12544),
    'pink':          (64000, 48640, 48640),
    'rose':          (65280,     0, 29440),
    'light orange':  (65280, 50176, 32768),
}
CLIP_COLORS = ['none'] + list(CLIP_COLOR_MAP.keys())


def prompt_choice(prompt: str, choices: list, default: str) -> str:
    """Prompt user to pick from a numbered list. Press Enter for default."""
    print(f"\n{prompt}")
    for i, choice in enumerate(choices, 1):
        marker = '*' if choice == default else ' '
        print(f"  {marker} {i}) {choice}")
    while True:
        raw = input(f"Choice [default: {default}]: ").strip()
        if not raw:
            return default
        if raw.isdigit() and 1 <= int(raw) <= len(choices):
            return choices[int(raw) - 1]
        if raw.lower() in [c.lower() for c in choices]:
            return next(c for c in choices if c.lower() == raw.lower())
        print(f"  Invalid choice. Enter 1-{len(choices)} or a value from the list.")


def prompt_markers_options(config) -> tuple:
    """Interactive prompts for markers export options."""
    dm = DEFAULT_CONFIG['markers']
    m  = config.get('markers', {})
    user     = input(f"\nAVID user name [default: {m.get('user', dm['user'])}]: ").strip() or m.get('user', dm['user'])
    track    = prompt_choice("Track:",           MARKER_TRACKS,    m.get('track',    dm['track']))
    color    = prompt_choice("Marker color:",    MARKER_COLORS,    m.get('color',    dm['color']))
    position = prompt_choice("Marker position:", MARKER_POSITIONS, m.get('position', dm['position']))
    print()
    return user, track, color, position


def _rgb_to_ansi256(r: int, g: int, b: int) -> int:
    """Return the nearest xterm 256-colour palette index for an sRGB colour."""
    levels = [0, 95, 135, 175, 215, 255]
    def snap(v): return min(range(6), key=lambda i: abs(levels[i] - v))
    ri, gi, bi = snap(r), snap(g), snap(b)
    cube_idx = 16 + 36 * ri + 6 * gi + bi
    d_cube = (r - levels[ri]) ** 2 + (g - levels[gi]) ** 2 + (b - levels[bi]) ** 2
    gray = round(r * 0.299 + g * 0.587 + b * 0.114)
    gray_idx = 232 + min(23, max(0, round((max(8, min(238, gray)) - 8) / 10)))
    gray_val = 8 + (gray_idx - 232) * 10
    d_gray = (r - gray_val) ** 2 + (g - gray_val) ** 2 + (b - gray_val) ** 2
    return gray_idx if d_gray < d_cube else cube_idx


def prompt_clip_color(default: str) -> str:
    """Prompt for clip color using a 4-column grid with ANSI color patches."""
    is_tty = sys.stdout.isatty() and os.environ.get('TERM', 'dumb') != 'dumb' and not os.environ.get('NO_COLOR')
    use_truecolor = is_tty and os.environ.get('COLORTERM', '').lower() in ('truecolor', '24bit')
    cols = 4
    col_width = max(len(n) for n in CLIP_COLORS) + 1  # pad names to uniform width

    def make_patch(name: str) -> str:
        if not is_tty:
            return '--' if name == 'none' else '  '
        if name == 'none':
            return '\033[2m--\033[0m'
        r16, g16, b16 = CLIP_COLOR_MAP[name]
        r, g, b = r16 // 256, g16 // 256, b16 // 256
        if use_truecolor:
            return f'\033[48;2;{r};{g};{b}m  \033[0m'
        return f'\033[48;5;{_rgb_to_ansi256(r, g, b)}m  \033[0m'

    print("\nClip color:")
    for row_start in range(0, len(CLIP_COLORS), cols):
        row_items = CLIP_COLORS[row_start:row_start + cols]
        line = ''
        for idx, name in enumerate(row_items):
            num = row_start + idx + 1
            marker = '*' if name == default else ' '
            patch = make_patch(name)
            line += f' {marker}{num:>2}) {patch} {name:<{col_width}}'
        print(line)

    while True:
        raw = input(f"\nChoice [default: {default}]: ").strip()
        if not raw:
            return default
        if raw.isdigit() and 1 <= int(raw) <= len(CLIP_COLORS):
            return CLIP_COLORS[int(raw) - 1]
        if raw.lower() in [c.lower() for c in CLIP_COLORS]:
            return next(c for c in CLIP_COLORS if c.lower() == raw.lower())
        print(f"  Invalid. Enter 1-{len(CLIP_COLORS)} or a color name.")


def prompt_aaf_options(config) -> tuple:
    """Interactive prompts for AAF clip notes export options (marker + clip color)."""
    dm = DEFAULT_CONFIG['markers']
    m  = config.get('markers', {})
    user       = input(f"\nAVID user name [default: {m.get('user', dm['user'])}]: ").strip() or m.get('user', dm['user'])
    color      = prompt_choice("Marker color:",    MARKER_COLORS,    m.get('color',      dm['color']))
    position   = prompt_choice("Marker position:", MARKER_POSITIONS, m.get('position',   dm['position']))
    clip_color = prompt_clip_color(m.get('clip_color', dm['clip_color']))
    print()
    return user, color, position, clip_color


def json_to_markers(json_file_path: str, markers_file_path: str, user: str = 'vfx', track_number: str = 'V1', marker_color: str = 'green', position: str = 'start'):
    """Reads a JSON file and export a markers file for AVID."""

    with open(json_file_path) as input_file:
        json_file = json.load(input_file) # Load JSON file

    if not confirm_overwrite(markers_file_path):
        return
    try:
        with open(markers_file_path, 'w') as output_file: # Open markers file
            for i in range(len(json_file['events'])): # Loop through JSON file
                if position == 'middle':
                    rec_start = Timecode(fps, json_file['events'][i]['record_start_TC'])
                    rec_end = Timecode(fps, json_file['events'][i]['record_end_TC'])
                    half_duration = (rec_end.frames - rec_start.frames) // 2
                    marker_tc = str(rec_start + half_duration)
                else:
                    marker_tc = json_file['events'][i]['record_start_TC']
                vfx_id = json_file['events'][i]['VFX ID']
                job_desc = json_file['events'][i].get('job_description', '')
                comment = f"{vfx_id} {job_desc}".strip() if job_desc else vfx_id
                markers_file_line = create_string('\t', user, marker_tc, track_number, marker_color, comment, '1') # Define markers file line
                # markers_file_line = user + '\t' + json_file['events'][i]['record_start_TC'] + '\t' + track_number + '\t' + marker_color + '\t' + \
                # json_file['events'][i]['VFX ID'] + '\t' + '1' + '\n' # Define markers file line
                output_file.write(markers_file_line + '\n') # Write line to markers file
        print(f"  Markers:  {os.path.basename(markers_file_path)}")
    except Exception as e:
        print(f"Error writing {markers_file_path}: {e}")    # Print error message


def json_to_subcaps(json_file_path: str, sub_file_path: str):
    """Reads a JSON file and export a subcap file for AVID."""
    
    with open(json_file_path) as input_file:
        json_file = json.load(input_file) # Load JSON file

    if not confirm_overwrite(sub_file_path):
        return
    try:
        with open(sub_file_path, 'w') as output_file:
            sub_file_line = '<begin subtitles>\n' # Define start of subcaps file
            output_file.write(sub_file_line)
            for i in range(len(json_file['events'])): # Loop through JSON file
                sub_file_line = create_string(' ', json_file['events'][i]['record_start_TC'], json_file['events'][i]['record_end_TC']) # Define subcaps file line
                # sub_file_line = json_file['events'][i]['record_start_TC'] + ' ' + json_file['events'][i]['record_end_TC'] + '\n' # Define subcaps file line
                output_file.write(sub_file_line + '\n') # Write line to subcaps file
                sub_file_line = json_file['events'][i]['VFX ID']  + '\n'# Define subcaps file line
                output_file.write(sub_file_line + '\n') # Write line to subcaps file
            sub_file_line = '<end subtitles>\n' # Define end of subcaps file
            output_file.write(sub_file_line) # Write line to subcaps file
        print(f"  Subcaps:  {os.path.basename(sub_file_path)}")
    except Exception as e:
        print(f"Error writing {sub_file_path}: {e}")    # Print error message


def export_ale_pulls(json_file_path: str, ale_pulls_file_path: str):
    """Export an ALE for creating pulls in AVID. 24 fps"""
    heading = 'Heading\n\
FIELD_DELIM' + '\t' +'TABS\n\
VIDEO_FORMAT' + '\t' + '1080\n\
AUDIO_FORMAT' + '\t' + '48khz\n\
FPS' + '\t' + fps + '\n\
\n\
Column\n\
Name' + '\t' + 'Tracks' + '\t' + 'Start' + '\t' + 'End' + '\t' + 'Tape\n\
Data\n\
\n' # Define ALE heading

    # handles_TC = Timecode(fps, '00:00:00:' + str(handles))
    with open(json_file_path) as input_file:
        json_file = json.load(input_file) # Load JSON file
    
    if not confirm_overwrite(ale_pulls_file_path):
        return
    try:
        with open(ale_pulls_file_path, 'w') as output_file:
            output_file.write(heading) # Write heading to ALE file
            for i in range(len(json_file['events'])):
                new_source_start_TC = Timecode(fps, json_file['events'][i]['source_start_TC']) - handles # Define new source start timecode with handles
                # new_source_end_TC = Timecode(fps, json_file['events'][i]['source_end_TC']) + handles - 1 # Define new source end timecode with handles
                new_source_end_TC = Timecode(fps, json_file['events'][i]['source_end_TC']) + handles # Define new source end timecode with handles

                # print(Timecode(fps, json_file['events'][i]['source_end_TC']) + handles_TC.frame_number)
                # print(new_source_end_TC)
                sub_file_line = create_string('\t', json_file['events'][i]['VFX ID'], 'V', str(new_source_start_TC), str(new_source_end_TC), json_file['events'][i]['reel']) # Define ALE file line
                # sub_file_line = json_file['events'][i]['VFX ID'] + '\t' + 'V' + '\t' + str(new_source_start_TC) + '\t' + str(new_source_end_TC) + \
                # '\t' + json_file['events'][i]['reel'] + '\n' # Define ALE file line
                output_file.write(sub_file_line + '\n') # Write line to ALE file
            print(f"  ALE:       {os.path.basename(ale_pulls_file_path)}")
    except Exception as e:  # Catch exception
        print(f"Error writing {ale_pulls_file_path}: {e}")      # Print error message


def export_pulls_edl(json_file_path: str, edl_pulls_file_path: str):
    """Export an EDL for cutting in pulls in AVID."""
    with open(json_file_path) as input_file:
        json_file = json.load(input_file) # Load JSON file
    
    if not confirm_overwrite(edl_pulls_file_path):
        return
    try:
        with open(edl_pulls_file_path, 'w') as output_file: # Open EDL file
            heading = 'TITLE: ' + os.path.splitext(os.path.basename(edl_pulls_file_path))[0]+ '\n'\
            'FCM: NON-DROP FRAME\n' # Define EDL heading
            output_file.write(heading) # Write heading to EDL file
            for i in range(len(json_file['events'])): # Loop through JSON file
                edl_pulls_file_line = create_string(
                    ' ', 
                    json_file['events'][i]['event_number'], 
                    json_file['events'][i]['VFX ID'], 
                    json_file['events'][i]['track'], 
                    json_file['events'][i]['transition'], 
                    json_file['events'][i]['source_start_TC'], 
                    json_file['events'][i]['source_end_TC'],
                    # str(Timecode(fps, json_file['events'][i]['source_end_TC']) - 1), # per gestire i consolidati senza maniglie...
                    json_file['events'][i]['record_start_TC'], 
                    json_file['events'][i]['record_end_TC'],
                )
                # edl_pulls_file_line = json_file['events'][i]['event_number'] + ' ' + json_file['events'][i]['VFX ID'] + ' ' + json_file['events'][i]['track'] + ' ' + \
                # json_file['events'][i]['transition'] + ' ' + json_file['events'][i]['source_start_TC'] + ' ' + json_file['events'][i]['source_end_TC'] + ' ' + \
                # json_file['events'][i]['record_start_TC'] + ' ' + json_file['events'][i]['record_end_TC'] # Define EDL file line
                output_file.write(edl_pulls_file_line + '\n') # Write line to EDL file
            print(f"  Pulls EDL: {os.path.basename(edl_pulls_file_path)}")
    except Exception as e:  # Catch exception
        print(f"Error writing {edl_pulls_file_path}: {e}")  # Print error message


def export_google_tab(json_file_path: str, google_file_path: str):
    """Export a TAB file to import into a Spreadsheet."""
    
    with open(json_file_path) as input_file:    # Open JSON file
        json_file = json.load(input_file)   # Load JSON file
    if not confirm_overwrite(google_file_path):
        return
    try:
        with open(google_file_path, 'w') as output_file:    # Open TAB file
            heading = '#' + '\t' + 'Name' + '\t' + 'Thumbnail' + '\t' + 'Comments' + '\t' + 'Status' + '\t' + 'Date' + '\t' + 'Duration' + '\t' + 'Start' + '\t' +\
            'End' + '\t' + 'Frame Count Duration' + '\t' + 'Handles' + '\t' + 'Tape'   # Define TAB heading
            output_file.write(heading + '\n')   # Write heading to TAB file
            counter = 1  # Define counter of events in JSON file
            for i in range(len(json_file['events'])):   # Loop through JSON file
                start_TC = Timecode(fps, json_file['events'][i]['source_start_TC']) # Define start timecode
                end_TC = Timecode(fps, json_file['events'][i]['source_end_TC']) # Define end timecode
                duration = end_TC - start_TC    # Define duration
                number_of_frames = duration.frames  # Define number of frames
                google_file_line = create_string(
                    '\t',
                    str(counter),
                    json_file['events'][i]['VFX ID'],
                    '',
                    json_file['events'][i].get('job_description', ''),
                    '',
                    '',
                    str(duration),
                    json_file['events'][i]['source_start_TC'],
                    json_file['events'][i]['source_end_TC'],
                    # str(Timecode(fps, json_file['events'][i]['source_end_TC']) - 1), # per gestire i consolidati senza maniglie...
                    str(number_of_frames),
                    str(handles),
                    json_file['events'][i]['reel'],
                )
                # google_file_line = str(counter) + '\t' +  json_file['events'][i]['VFX ID'] + '\t' + '\t' + '\t' + '\t' + '\t' + str(duration) + '\t' + json_file['events'][i]['source_start_TC'] + '\t' +\
                # json_file['events'][i]['source_end_TC'] + '\t' + str(number_of_frames) + '\t' + json_file['events'][i]['reel']  # Define TAB file line
                output_file.write(google_file_line + '\n')  # Write line to TAB file
                counter += 1    # Increment counter
            print(f"Succesfully exported TAB file: {google_file_path}")   # Print success message
    except Exception as e:  # Catch exception
        print(f"Error writing {google_file_path}: {e}")  # Print error message


def parse_ale(ale_file_path: str) -> dict:
    """Parse an Avid ALE file into heading, columns, and rows."""
    with open(ale_file_path, 'r') as f:
        lines = [l.rstrip('\n\r') for l in f.readlines()]

    heading = {}
    columns = []
    rows = []
    section = None

    for line in lines:
        stripped = line.strip()
        if stripped == 'Heading':
            section = 'heading'
            continue
        elif stripped == 'Column':
            section = 'column'
            continue
        elif stripped == 'Data':
            section = 'data'
            continue

        if section == 'heading':
            if '\t' in line:
                key, _, value = line.partition('\t')
                heading[key.strip()] = value.strip()
        elif section == 'column':
            if stripped:
                columns = line.split('\t')
        elif section == 'data':
            if stripped:
                values = line.split('\t')
                while len(values) < len(columns):
                    values.append('')
                rows.append(dict(zip(columns, values)))

    return {'heading': heading, 'columns': columns, 'rows': rows}


def merge_ale_tab(json_file_path: str, ale_file_path: str, output_path: str):
    """Export a TAB file merging project VFX IDs with ALE metadata columns."""
    with open(json_file_path) as f:
        project = json.load(f)

    ale = parse_ale(ale_file_path)
    ale_fps = ale['heading'].get('FPS', '')
    ale_res = ale['heading'].get('VIDEO_FORMAT', '')

    print(f"  ALE: {os.path.basename(ale_file_path)}  FPS: {ale_fps}  Format: {ale_res}  Clips: {len(ale['rows'])}")

    if ale_fps != fps:
        print(f"Error: ALE FPS ({ale_fps}) does not match project FPS ({fps}). Aborting.", file=sys.stderr)
        return

    resolution = project['config'].get('resolution', DEFAULT_CONFIG['resolution'])
    if ale_res != resolution:
        print(f"  Warning: ALE VIDEO_FORMAT ({ale_res}) does not match project resolution ({resolution})")

    if 'Tape' not in ale['columns']:
        print("Error: ALE file missing required 'Tape' column. Aborting.", file=sys.stderr)
        return

    # Build lookup index: Tape -> row
    ale_index = {}
    for row in ale['rows']:
        key = row.get('Tape', '')
        if key in ale_index:
            print(f"  Warning: duplicate ALE entry for Tape={key}, keeping first")
        else:
            ale_index[key] = row

    # Extra ALE columns: all except those already present in standard TAB
    SKIP_ALE_COLS = {'Name', 'Start', 'End', 'Tape', 'Duration'}
    extra_cols = [c for c in ale['columns'] if c not in SKIP_ALE_COLS]

    def col_header(c):
        return 'ALE Comments' if c == 'Comments' else c

    if not confirm_overwrite(output_path):
        return

    matched = 0
    unmatched = 0

    try:
        with open(output_path, 'w') as out:
            std_header = '#\tName\tThumbnail\tComments\tStatus\tDate\tDuration\tStart\tEnd\tFrame Count Duration\tHandles\tTape'
            ale_header = '\t'.join(col_header(c) for c in extra_cols)
            out.write(std_header + ('\t' + ale_header if ale_header else '') + '\n')

            counter = 1
            for event in project['events']:
                start_TC = Timecode(fps, event['source_start_TC'])
                end_TC   = Timecode(fps, event['source_end_TC'])
                duration = end_TC - start_TC

                std_values = create_string(
                    '\t',
                    str(counter),
                    event['VFX ID'],
                    '',
                    event.get('job_description', ''),
                    '',
                    '',
                    str(duration),
                    event['source_start_TC'],
                    event['source_end_TC'],
                    str(duration.frames),
                    str(handles),
                    event['reel'],
                )

                ale_row = ale_index.get(event['reel'])
                if ale_row:
                    matched += 1
                    ale_values = '\t'.join(ale_row.get(c, '') for c in extra_cols)
                else:
                    unmatched += 1
                    print(f"  Warning: no ALE match for {event['VFX ID']} (reel: {event['reel']})")
                    ale_values = '\t' * (len(extra_cols) - 1) if extra_cols else ''

                out.write(std_values + ('\t' + ale_values if extra_cols else '') + '\n')
                counter += 1

        print(f"  Merged TAB: {os.path.basename(output_path)}")
        print(f"  Matched:    {matched} / {matched + unmatched} events")
        if unmatched:
            print(f"  Unmatched:  {unmatched} events (no ALE row — ALE columns left empty)")
        used_keys = {e['reel'] for e in project['events']}
        unused = sum(1 for k in ale_index if k not in used_keys)
        if unused:
            print(f"  ALE rows not used: {unused}")

    except Exception as e:
        print(f"Error writing {output_path}: {e}")


def compare_edls(old_events: list, new_events: list, fps_val: str, handles_val: int) -> list:
    """Compare two EDL event lists and return annotated changelist.

    Matching order: VFX ID first, then reel+source_start_TC fallback for no-ID events.

    Each returned event has 'change_status' set to one of:
      unchanged, new, removed, moved,
      trimmed_ok, trimmed_pull,
      moved_trimmed_ok, moved_trimmed_pull

    Trimmed events also carry 'head_trimmed' / 'tail_trimmed' booleans and
    frame-delta fields src_in_d, src_out_d, rec_in_d, rec_out_d plus the
    previous TC values for reference.

    Move detection: a clip is considered moved when the record-TC shift is not
    fully explained by the source trim, i.e.:
        moved = (rec_in_d != src_in_d) OR (rec_out_d != src_out_d)
    """
    old_by_id = {e['VFX ID']: e for e in old_events if e.get('VFX ID') and e.get('LOC')}
    old_by_reel_tc = {}
    for e in old_events:
        if e.get('reel') and e.get('source_start_TC'):
            old_by_reel_tc[f"{e['reel']}|{e['source_start_TC']}"] = e

    result = []
    matched_old_vfx_ids = set()
    matched_old_reel_tcs = set()

    for e in new_events:
        ev = dict(e)
        # Only use VFX ID for matching if it came from a real LOC marker,
        # not auto-generated — auto-generated IDs shift when clips are
        # inserted/removed, causing false matches.
        vfx_id = e.get('VFX ID', '') if e.get('LOC') else ''
        old = None

        if vfx_id:
            old = old_by_id.get(vfx_id)
            if old:
                matched_old_vfx_ids.add(vfx_id)

        if old is None:
            reel_tc_key = f"{e.get('reel', '')}|{e.get('source_start_TC', '')}"
            old = old_by_reel_tc.get(reel_tc_key)
            if old:
                matched_old_reel_tcs.add(reel_tc_key)

        if old is None:
            ev['change_status'] = 'new'
            ev['head_trimmed'] = False
            ev['tail_trimmed'] = False
        else:
            new_src_in  = Timecode(fps_val, e['source_start_TC']).frames
            new_src_out = Timecode(fps_val, e['source_end_TC']).frames
            old_src_in  = Timecode(fps_val, old['source_start_TC']).frames
            old_src_out = Timecode(fps_val, old['source_end_TC']).frames
            new_rec_in  = Timecode(fps_val, e['record_start_TC']).frames
            new_rec_out = Timecode(fps_val, e['record_end_TC']).frames
            old_rec_in  = Timecode(fps_val, old['record_start_TC']).frames
            old_rec_out = Timecode(fps_val, old['record_end_TC']).frames

            src_in_d  = new_src_in  - old_src_in
            src_out_d = new_src_out - old_src_out
            rec_in_d  = new_rec_in  - old_rec_in
            rec_out_d = new_rec_out - old_rec_out

            src_changed  = src_in_d != 0 or src_out_d != 0
            head_trimmed = src_in_d != 0
            tail_trimmed = src_out_d != 0
            moved        = (rec_in_d != src_in_d) or (rec_out_d != src_out_d)
            within_handles = (new_src_in >= old_src_in - handles_val) and \
                             (new_src_out <= old_src_out + handles_val)

            if not src_changed and not moved:
                status = 'unchanged'
            elif not src_changed and moved:
                status = 'moved'
            elif src_changed and not moved:
                status = 'trimmed_ok' if within_handles else 'trimmed_pull'
            else:
                status = 'moved_trimmed_ok' if within_handles else 'moved_trimmed_pull'

            ev['change_status']       = status
            ev['head_trimmed']        = head_trimmed
            ev['tail_trimmed']        = tail_trimmed
            ev['src_in_d']            = src_in_d
            ev['src_out_d']           = src_out_d
            ev['rec_in_d']            = rec_in_d
            ev['rec_out_d']           = rec_out_d
            ev['prev_source_start_TC'] = old['source_start_TC']
            ev['prev_source_end_TC']   = old['source_end_TC']
            ev['prev_record_start_TC'] = old['record_start_TC']
            ev['prev_record_end_TC']   = old['record_end_TC']

        result.append(ev)

    # Append removed events (in old but not matched in new)
    for e in old_events:
        vfx_id      = e.get('VFX ID', '')
        reel_tc_key = f"{e.get('reel', '')}|{e.get('source_start_TC', '')}"
        is_matched  = (vfx_id and vfx_id in matched_old_vfx_ids) or \
                      (reel_tc_key in matched_old_reel_tcs)
        if not is_matched:
            ev = dict(e)
            ev['change_status'] = 'removed'
            ev['head_trimmed']  = False
            ev['tail_trimmed']  = False
            result.append(ev)

    return result


def _changelist_label(e: dict) -> str:
    """Return a human-readable status label for a changelist event."""
    TRIM_PART = {
        (True,  True):  'HEAD & TAIL',
        (True,  False): 'HEAD',
        (False, True):  'TAIL',
    }

    def _fmt_delta(n):
        return f'+{n}f' if n >= 0 else f'{n}f'

    def _trim_delta(ev):
        src_in_d  = ev.get('src_in_d', 0)
        src_out_d = ev.get('src_out_d', 0)
        h = ev.get('head_trimmed', False)
        t = ev.get('tail_trimmed', False)
        if h and t:
            return f'H:{_fmt_delta(-src_in_d)} T:{_fmt_delta(src_out_d)}'
        elif h:
            return _fmt_delta(-src_in_d)
        elif t:
            return _fmt_delta(src_out_d)
        return ''

    status = e.get('change_status', 'unchanged')
    head   = e.get('head_trimmed', False)
    tail   = e.get('tail_trimmed', False)

    if status == 'new':
        return 'NEW - NEED TO PULL'
    elif status == 'removed':
        return 'REMOVED'
    elif status == 'moved':
        return 'MOVED'
    elif status in ('trimmed_ok', 'trimmed_pull'):
        trim_part = TRIM_PART.get((head, tail), 'HEAD & TAIL')
        pull      = 'NEED TO PULL' if status == 'trimmed_pull' else 'NO PULL NEEDED'
        delta     = _trim_delta(e)
        return f'TRIMMED {trim_part} {delta} - {pull}' if delta else f'TRIMMED {trim_part} - {pull}'
    elif status in ('moved_trimmed_ok', 'moved_trimmed_pull'):
        trim_part = TRIM_PART.get((head, tail), 'HEAD & TAIL')
        pull      = 'NEED TO PULL' if status == 'moved_trimmed_pull' else 'NO PULL NEEDED'
        delta     = _trim_delta(e)
        return f'MOVED TRIMMED {trim_part} {delta} - {pull}' if delta else f'MOVED TRIMMED {trim_part} - {pull}'
    return status.upper()


def export_changelist_markers(events: list, fps_val: str, output_path: str,
                              user: str = 'vfx', track: str = 'V1', color: str = 'green'):
    """Write a changelist markers .txt file for Avid from annotated EDL events.

    Marker timecode is placed at 1/3 of each event's record duration.
    'unchanged' events are skipped. 'removed' events use their own record TCs.
    """
    if not confirm_overwrite(output_path):
        return
    try:
        with open(output_path, 'w') as out:
            for e in events:
                status = e.get('change_status', 'unchanged')
                if status == 'unchanged':
                    continue
                rec_start  = Timecode(fps_val, e['record_start_TC'])
                rec_end    = Timecode(fps_val, e['record_end_TC'])
                duration_f = rec_end.frames - rec_start.frames
                marker_tc  = str(rec_start + duration_f // 3)
                vfx_id     = e.get('VFX ID') or '[NO ID]'
                label      = _changelist_label(e)
                line = create_string('\t', user, marker_tc, track, color, f'{vfx_id} {label}', '1')
                out.write(line + '\n')
        print(f"  Markers:  {os.path.basename(output_path)}")
    except Exception as ex:
        print(f"Error writing {output_path}: {ex}")


def export_changelist_tab(events: list, fps_val: str, handles_val: int, output_path: str):
    """Write a changelist TAB file (same columns as -t) from annotated EDL events."""
    if not confirm_overwrite(output_path):
        return
    try:
        with open(output_path, 'w') as out:
            heading = '#\tName\tThumbnail\tComments\tStatus\tDate\tDuration\tStart\tEnd\tFrame Count Duration\tHandles\tTape'
            out.write(heading + '\n')
            counter = 1
            for e in events:
                if e.get('change_status', 'unchanged') == 'unchanged':
                    continue
                src_start = Timecode(fps_val, e['source_start_TC'])
                src_end   = Timecode(fps_val, e['source_end_TC'])
                duration  = src_end - src_start
                line = create_string(
                    '\t',
                    str(counter),
                    e.get('VFX ID') or '[NO ID]',
                    '',
                    '',
                    _changelist_label(e),
                    '',
                    str(duration),
                    e['source_start_TC'],
                    e['source_end_TC'],
                    str(duration.frames),
                    str(handles_val),
                    e.get('reel', ''),
                )
                out.write(line + '\n')
                counter += 1
        print(f"  TAB:      {os.path.basename(output_path)}")
    except Exception as ex:
        print(f"Error writing {output_path}: {ex}")


def _ensure_descriptive_metadata_def(f):
    """Register DescriptiveMetadata DataDef if missing.

    Avid-produced AAFs store it as 'Descriptive Metadata' (with a space), which
    pyaaf2's lookup_datadef() cannot resolve by the canonical name. Registering it
    explicitly lets f.create.DescriptiveMarker() succeed on any input AAF.
    """
    try:
        f.dictionary.lookup_datadef('DescriptiveMetadata')
    except Exception:
        dm_dd = f.create.DataDef(
            "01030201-1000-0000-060e-2b3404010101",
            "DataDef_DescriptiveMetadata",
            "Descriptive metadata",
        )
        f.dictionary.register_def(dm_dd)


def json_to_aaf(json_file_path: str, input_aaf_path: str, output_aaf_path: str,
                user: str = 'vfx', color: str = 'green', position: str = 'start',
                clip_color: str = 'none'):
    """Copy an AAF and write VFX IDs from JSON as clip notes and timeline markers."""

    with open(json_file_path) as input_file:
        json_file = json.load(input_file)
    events = json_file['events']

    color_str, color_rgb = MARKER_COLOR_MAP.get(color.lower(), MARKER_COLOR_MAP['green'])
    now_ts = int(time.time())

    if not confirm_overwrite(output_aaf_path):
        return
    shutil.copy2(input_aaf_path, output_aaf_path)

    with aaf2.open(output_aaf_path, 'rw') as f:
        _ensure_descriptive_metadata_def(f)

        for mob in f.content.toplevel():
            video_slot = None
            for slot in mob.slots:
                if not hasattr(slot.segment, 'components'):
                    continue
                media_kind = getattr(slot, 'media_kind', None)
                if media_kind and 'picture' in str(media_kind).lower():
                    video_slot = slot
                    break

            if not video_slot:
                continue

            video_slot_id = video_slot.slot_id
            track_name = video_slot['SlotName'].value or f"V{video_slot['PhysicalTrackNumber'].value}"
            print(f'  Detected track: {track_name}')
            clip_num = 0
            timeline_pos = 0
            marker_data = []   # list of (marker_frame, vfx_id) for clips needing new markers
            kept_markers = []  # existing marker objects to preserve as-is

            # Pre-collect existing markers by position for preservation
            existing_markers_by_pos = {}
            for slot in mob.slots:
                if type(slot).__name__ == 'EventMobSlot':
                    for m in slot.segment.components:
                        try:
                            existing_markers_by_pos[m['Position'].value] = m
                        except Exception:
                            pass
                    break

            for comp in video_slot.segment.components:
                comp_type = type(comp).__name__
                length = getattr(comp, 'length', 0) or 0

                if comp_type == 'Filler':
                    timeline_pos += length
                    continue

                if isinstance(comp, aaf2.components.SourceClip) and comp.mob:
                    target = comp
                    clip_name = comp.mob.name
                elif comp_type == 'Selector':
                    target = comp
                    sel = comp['Selected'].value
                    clip_name = sel.mob.name if (sel and sel.mob) else ''
                elif comp_type == 'OperationGroup':
                    target = comp
                    clip_name = ''
                    segments = comp.get('InputSegments')
                    if segments:
                        for seg in segments:
                            if isinstance(seg, aaf2.components.SourceClip) and seg.mob:
                                clip_name = seg.mob.name
                                break
                            if hasattr(seg, 'components'):
                                for sc in seg.components:
                                    if isinstance(sc, aaf2.components.SourceClip) and sc.mob:
                                        clip_name = sc.mob.name
                                        break
                                if clip_name:
                                    break
                else:
                    timeline_pos += length
                    continue

                clip_num += 1

                if clip_num > len(events):
                    print(f'  Warning: more clips ({clip_num}) than events ({len(events)}), stopping')
                    break

                vfx_id = events[clip_num - 1]['VFX ID']
                has_clip_note = events[clip_num - 1].get('has_clip_note', False)
                job_desc = events[clip_num - 1].get('job_description', '')

                # Check for existing marker at this clip's position directly in the AAF
                existing_marker = None
                marker_vfx_id = None
                for pos, m in existing_markers_by_pos.items():
                    if timeline_pos <= pos < timeline_pos + length:
                        existing_marker = m
                        attrs = m.get('CommentMarkerAttributeList')
                        if attrs:
                            for tag in attrs:
                                if tag.name == '_ATN_CRM_COM' and tag.value:
                                    marker_vfx_id = tag.value.split()[0]
                                    break
                        break

                # VFX ID: use marker's if available, else fall back to JSON
                effective_vfx_id = marker_vfx_id if marker_vfx_id else vfx_id
                # Full string written to both clip note and marker (VFX ID + job description if present)
                full_id = f"{effective_vfx_id} {job_desc}".strip() if job_desc else effective_vfx_id

                # Get or create ComponentAttributeList (needed for both clip note and clip color)
                attr_list = target.get('ComponentAttributeList')
                if attr_list is None:
                    target['ComponentAttributeList'] = []
                    attr_list = target['ComponentAttributeList']

                # Write clip note:
                # - If clip has an existing marker: always write/update note with marker's VFX ID
                # - Otherwise: write only if no clip note exists yet
                if existing_marker is not None or not has_clip_note:
                    found = False
                    for attr in attr_list:
                        if attr.name == '_COMMENT':
                            attr.value = full_id
                            found = True
                            break
                    if not found:
                        tv = f.create.TaggedValue()
                        tv['Name'].value = '_COMMENT'
                        tv['Value'].value = full_id
                        attr_list.append(tv)

                # Write clip color
                if clip_color != 'none':
                    r16, g16, b16 = CLIP_COLOR_MAP[clip_color.lower()]
                    color_vals = {'_COLOR_R': r16, '_COLOR_G': g16, '_COLOR_B': b16}
                    found_keys = set()
                    for attr in attr_list:
                        if attr.name in color_vals:
                            attr.value = color_vals[attr.name]
                            found_keys.add(attr.name)
                    for name, val in color_vals.items():
                        if name not in found_keys:
                            tv = f.create.TaggedValue()
                            tv['Name'].value = name
                            tv['Value'].value = val
                            attr_list.append(tv)

                # Marker: update existing or queue a new one
                if existing_marker is not None:
                    existing_marker['Comment'].value = full_id
                    attrs = existing_marker.get('CommentMarkerAttributeList')
                    if attrs:
                        for tag in attrs:
                            if tag.name == '_ATN_CRM_COM':
                                tag.value = full_id
                                break
                    kept_markers.append(existing_marker)
                    mark_str = 'updated'
                else:
                    marker_frame = timeline_pos + length // 2 if position == 'middle' else timeline_pos
                    marker_data.append((marker_frame, full_id))
                    mark_str = f'new @ {marker_frame}'

                note_str = 'updated' if existing_marker is not None else ('kept' if has_clip_note else 'new')
                print(f'  Clip {clip_num}: {clip_name} -> {full_id}  (note: {note_str}, marker: {mark_str})')
                timeline_pos += length

            if clip_num < len(events):
                print(f'  Warning: fewer clips ({clip_num}) than events ({len(events)})')

            # Find or create EventMobSlot for markers
            event_slot = None
            for slot in mob.slots:
                if type(slot).__name__ == 'EventMobSlot':
                    event_slot = slot
                    break

            if event_slot is None:
                existing_ids = {s.slot_id for s in mob.slots}
                new_slot_id = max(existing_ids) + 1 if existing_ids else 1008
                event_slot = f.create.EventMobSlot()
                event_slot['SlotID'].value = new_slot_id
                event_slot['EditRate'].value = video_slot.edit_rate
                event_slot['SlotName'].value = ''
                seq = f.create.Sequence(media_kind='DescriptiveMetadata')
                seq['Components'].value = []
                event_slot['Segment'].value = seq
                mob.slots.append(event_slot)
            else:
                seq = event_slot.segment

            # Build markers and assign all at once (StrongRefVectorProperty requires this)
            new_markers = []
            for marker_frame, vfx_id in marker_data:
                marker = f.create.DescriptiveMarker()
                marker['Length'].value = 1
                marker['Position'].value = marker_frame
                marker['Comment'].value = vfx_id
                marker['CommentMarkerUSer'].value = user
                marker['CommentMarkerColor'].value = color_rgb
                marker['DescribedSlots'].value = {video_slot_id}
                tv_list = []
                for tv_name, tv_val in [
                    ('_ATN_CRM_COLOR',           color_str),
                    ('_ATN_CRM_COLOR_EXTENDED',   color_str),
                    ('_ATN_CRM_USER',             user),
                    ('_ATN_CRM_COM',              vfx_id),
                    ('_ATN_CRM_LONG_CREATE_DATE', now_ts),
                    ('_ATN_CRM_LONG_MOD_DATE',    now_ts),
                    ('_ATN_CRM_LENGTH',           1),
                    ('_ATN_CRM_ID',               uuid.uuid4().hex),
                ]:
                    tv_list.append(f.create.TaggedValue(tv_name, tv_val))
                marker['CommentMarkerAttributeList'].value = tv_list
                new_markers.append(marker)

            all_markers = sorted(kept_markers + new_markers, key=lambda m: m['Position'].value)
            seq['Components'].value = all_markers

        f.save()

    print(f'\nProcessed {clip_num} clips: {len(marker_data)} new markers, {len(kept_markers)} preserved → {output_aaf_path}')


def _edit_rate_to_fps_str(numerator: int, denominator: int) -> str:
    """Convert an AAF edit rate fraction to a FPS_CHOICES-compatible string."""
    rate = numerator / denominator
    for candidate in FPS_CHOICES:
        if abs(rate - float(candidate)) < 0.01:
            return candidate
    return f'{rate:.3f}'.rstrip('0').rstrip('.')


def check_aaf_project_settings(aaf_file: str, config: dict):
    """Warn if AAF fps or resolution does not match the project config."""
    try:
        with aaf2.open(aaf_file, 'r') as f:
            # --- FPS ---
            aaf_fps = None
            for mob in f.content.toplevel():
                for slot in mob.slots:
                    mk = getattr(slot, 'media_kind', None)
                    if mk and 'picture' in str(mk).lower() and hasattr(slot.segment, 'components'):
                        er = slot.edit_rate
                        aaf_fps = _edit_rate_to_fps_str(er.numerator, er.denominator)
                        break
                if aaf_fps:
                    break

            # --- Resolution ---
            aaf_height = None
            for mob in f.content['Mobs']:
                if type(mob).__name__ == 'SourceMob':
                    desc = mob.descriptor
                    if desc is not None and 'CDCI' in type(desc).__name__:
                        try:
                            aaf_height = str(desc['StoredHeight'].value)
                        except Exception:
                            pass
                        break

        project_fps = config.get('fps', DEFAULT_CONFIG['fps'])
        project_res = config.get('resolution', DEFAULT_CONFIG['resolution'])
        warnings = []
        if aaf_fps and aaf_fps != project_fps:
            warnings.append(f"  FPS:        AAF={aaf_fps}  project={project_fps}")
        if aaf_height and aaf_height != project_res:
            warnings.append(f"  Resolution: AAF={aaf_height}  project={project_res}")
        if warnings:
            print("Warning: AAF metadata does not match project settings:", file=sys.stderr)
            for w in warnings:
                print(w, file=sys.stderr)
    except Exception as e:
        print(f"Warning: could not read AAF metadata for settings check: {e}", file=sys.stderr)


def check_aaf_consistency(aaf_file: str):
    """Check AAF for clip note / marker VFX ID mismatches. Exit if any found."""
    inconsistencies = []
    with aaf2.open(aaf_file, 'r') as f:
        main_mob = None
        for mob in f.content.toplevel():
            for slot in mob.slots:
                if not hasattr(slot.segment, 'components'):
                    continue
                media_kind = getattr(slot, 'media_kind', None)
                if media_kind and 'picture' in str(media_kind).lower():
                    main_mob = mob
                    break
            if main_mob:
                break

        if main_mob is None:
            print("Error: no video timeline found in AAF", file=sys.stderr)
            sys.exit(1)

        video_slot = None
        for slot in main_mob.slots:
            if not hasattr(slot.segment, 'components'):
                continue
            media_kind = getattr(slot, 'media_kind', None)
            if media_kind and 'picture' in str(media_kind).lower():
                video_slot = slot
                break

        fps_check = str(int(round(video_slot.edit_rate.numerator / video_slot.edit_rate.denominator)))
        tc_start_str = '01:00:00:00'
        for slot in main_mob.slots:
            if type(slot.segment).__name__ == 'Timecode':
                try:
                    tc_start_str = str(Timecode(fps_check, frames=slot.segment['Start'].value + 1))
                except Exception:
                    pass
                break
        base_tc = Timecode(fps_check, tc_start_str)

        existing_markers = {}
        for slot in main_mob.slots:
            if type(slot).__name__ == 'EventMobSlot':
                for marker in slot.segment.components:
                    attrs = marker.get('CommentMarkerAttributeList')
                    if attrs:
                        try:
                            pos = marker['Position'].value
                        except Exception:
                            continue
                        for tag in attrs:
                            if tag.name == '_ATN_CRM_COM' and tag.value:
                                existing_markers[pos] = tag.value
                                break
                break

        timeline_pos = 0
        total_clips  = 0
        clips_with_id = 0
        missing_id = []   # (clip_name, tc) for clips with no marker and no clip note
        for comp in video_slot.segment.components:
            comp_type = type(comp).__name__
            length = getattr(comp, 'length', 0) or 0

            if comp_type == 'Filler':
                timeline_pos += length
                continue

            target_comp = None
            source_clip = None
            if isinstance(comp, aaf2.components.SourceClip) and comp.mob:
                target_comp = comp
                source_clip = comp
            elif comp_type == 'Selector':
                target_comp = comp
                sel = comp['Selected'].value
                if isinstance(sel, aaf2.components.SourceClip) and sel.mob:
                    source_clip = sel
            elif comp_type == 'OperationGroup':
                target_comp = comp
                segments = comp.get('InputSegments')
                if segments:
                    for seg in segments:
                        if isinstance(seg, aaf2.components.SourceClip) and seg.mob:
                            source_clip = seg
                            break
                        if hasattr(seg, 'components'):
                            for sc in seg.components:
                                if isinstance(sc, aaf2.components.SourceClip) and sc.mob:
                                    source_clip = sc
                                    break
                            if source_clip:
                                break

            if source_clip is None:
                timeline_pos += length
                continue

            total_clips += 1
            clip_name = source_clip.mob.name or ''

            clip_note_id = None
            if target_comp is not None:
                attr_list = target_comp.get('ComponentAttributeList')
                if attr_list:
                    for attr in attr_list:
                        if attr.name == '_COMMENT' and attr.value:
                            clip_note_id = attr.value.split()[0]
                            break

            marker_id = None
            for pos, vid in existing_markers.items():
                if timeline_pos <= pos < timeline_pos + length:
                    marker_id = vid.split()[0]
                    break

            if clip_note_id or marker_id:
                clips_with_id += 1
            else:
                missing_id.append((clip_name, str(base_tc + timeline_pos)))

            if clip_note_id and marker_id and clip_note_id != marker_id:
                inconsistencies.append((clip_name, str(base_tc + timeline_pos), clip_note_id, marker_id))

            timeline_pos += length

    if clips_with_id > 0 and missing_id:
        print(f"Error: AAF has VFX IDs on some clips but {len(missing_id)} clip(s) are missing both marker and clip note:", file=sys.stderr)
        for clip_name, tc in missing_id:
            print(f"  [{tc}]", file=sys.stderr)
        print("Resolve the mismatches in Avid before re-running.", file=sys.stderr)
        sys.exit(1)

    if inconsistencies:
        print(f"\nWarning: {len(inconsistencies)} VFX ID mismatch(es) found — fix the source AAF before exporting:\n", file=sys.stderr)
        for clip_name, tc, note_id, mark_id in inconsistencies:
            print(f"  [{tc}]  {clip_name}\n    Clip note : {note_id}\n    Marker    : {mark_id}", file=sys.stderr)
        sys.exit(1)


def aaf_to_json(aaf_file: str) -> dict:
    """Read an AAF timeline with pyaaf2, extract clips, and return event data like edl_to_json."""

    edl_data = {
        "edl_metadata": {
            "edl_title": os.path.splitext(os.path.basename(aaf_file))[0],
            "edl_fcm": "NON-DROP FRAME",
        },
        "events": [],
    }

    last_scene = '0'
    VFX_counter = 10

    with aaf2.open(aaf_file, 'r') as f:
        # Find the main CompositionMob with a video track
        main_mob = None
        for mob in f.content.toplevel():
            for slot in mob.slots:
                if not hasattr(slot.segment, 'components'):
                    continue
                media_kind = getattr(slot, 'media_kind', None)
                if media_kind and 'picture' in str(media_kind).lower():
                    main_mob = mob
                    break
            if main_mob:
                break

        if main_mob is None:
            print("Error: no video timeline found in AAF", file=sys.stderr)
            sys.exit(1)

        # Find video slot
        video_slot = None
        for slot in main_mob.slots:
            if not hasattr(slot.segment, 'components'):
                continue
            media_kind = getattr(slot, 'media_kind', None)
            if media_kind and 'picture' in str(media_kind).lower():
                video_slot = slot
                break

        # Get sequence start TC from Timecode slot (default 01:00:00:00 = Avid standard)
        tc_start_str = '01:00:00:00'
        for slot in main_mob.slots:
            if type(slot.segment).__name__ == 'Timecode':
                try:
                    tc_start_str = str(Timecode(fps, frames=slot.segment['Start'].value + 1))
                except Exception:
                    pass
                break

        base_tc = Timecode(fps, tc_start_str)
        event_num = 0
        timeline_pos = 0
        event_lines = []

        # Collect existing markers from EventMobSlot for VFX ID reuse detection
        existing_markers = {}  # {position: vfx_id}
        for slot in main_mob.slots:
            if type(slot).__name__ == 'EventMobSlot':
                for marker in slot.segment.components:
                    attrs = marker.get('CommentMarkerAttributeList')
                    if attrs:
                        try:
                            pos = marker['Position'].value
                        except Exception:
                            continue
                        for tag in attrs:
                            if tag.name == '_ATN_CRM_COM' and tag.value:
                                existing_markers[pos] = tag.value
                                break
                break

        for comp in video_slot.segment.components:
            comp_type = type(comp).__name__
            length = getattr(comp, 'length', 0) or 0

            if comp_type == 'Filler':
                timeline_pos += length
                continue

            # Resolve SourceClip reference through Selector / OperationGroup wrappers
            # target_comp holds ComponentAttributeList (_COMMENT lives on Selector, not inner clip)
            target_comp = None
            source_clip = None
            if isinstance(comp, aaf2.components.SourceClip) and comp.mob:
                target_comp = comp
                source_clip = comp
            elif comp_type == 'Selector':
                target_comp = comp  # _COMMENT lives on Selector
                sel = comp['Selected'].value
                if isinstance(sel, aaf2.components.SourceClip) and sel.mob:
                    source_clip = sel
            elif comp_type == 'OperationGroup':
                target_comp = comp
                segments = comp.get('InputSegments')
                if segments:
                    for seg in segments:
                        if isinstance(seg, aaf2.components.SourceClip) and seg.mob:
                            source_clip = seg
                            break
                        if hasattr(seg, 'components'):
                            for sc in seg.components:
                                if isinstance(sc, aaf2.components.SourceClip) and sc.mob:
                                    source_clip = sc
                                    break
                            if source_clip:
                                break

            if source_clip is None:
                timeline_pos += length
                continue

            # Timeline SourceClip start offset (comp.start; comp['StartTime'] is not accessible via [])
            src_offset = getattr(source_clip, 'start', 0) or 0

            # subclip = SubClip CompositionMob (scene-based clip name, e.g. "33-2-/01 A")
            subclip = source_clip.mob
            clip_name = subclip.name or ''

            # Navigate: SubClip → picture slot SourceClip → MasterMob
            master_mob = None
            sub_sc_start = 0
            for sub_slot in subclip.slots:
                if 'picture' not in str(getattr(sub_slot, 'media_kind', '')).lower():
                    continue
                sub_seg = sub_slot.segment
                if isinstance(sub_seg, aaf2.components.SourceClip) and sub_seg.mob:
                    for p in sub_seg.properties():
                        if p.name == 'StartTime':
                            sub_sc_start = p.value or 0
                            break
                    master_mob = sub_seg.mob
                    break

            # Navigate: MasterMob → picture Sequence SourceClip → CDCIDescriptor SourceMob
            cdi_mob = None
            master_sc_start = 0
            if master_mob:
                for m_slot in master_mob.slots:
                    if 'picture' not in str(getattr(m_slot, 'media_kind', '')).lower():
                        continue
                    m_seg = m_slot.segment
                    if hasattr(m_seg, 'components'):
                        for sc in m_seg.components:
                            if isinstance(sc, aaf2.components.SourceClip) and sc.mob:
                                for p in sc.properties():
                                    if p.name == 'StartTime':
                                        master_sc_start = p.value or 0
                                        break
                                cdi_mob = sc.mob
                                break
                    break

            # Navigate: CDCIDescriptor SourceMob → picture Sequence SourceClip → TapeDescriptor SourceMob
            # The SourceClip.StartTime here is the key tape offset for source TC calculation
            tape_mob = None
            cdi_sc_start = 0
            if cdi_mob:
                for c_slot in cdi_mob.slots:
                    if 'picture' not in str(getattr(c_slot, 'media_kind', '')).lower():
                        continue
                    c_seg = c_slot.segment
                    if hasattr(c_seg, 'components'):
                        for sc in c_seg.components:
                            if isinstance(sc, aaf2.components.SourceClip):
                                for p in sc.properties():
                                    if p.name == 'StartTime':
                                        cdi_sc_start = p.value or 0
                                        break
                                tape_mob = sc.mob  # may be None for offline media
                                break
                    break

            # Reel name: TapeDescriptor mob name (e.g. "A059_A006_0519W9_001"), matches EDL reel column
            reel_name = (tape_mob.name if tape_mob else None) or (master_mob.name if master_mob else None) or clip_name

            # Source TC: accumulate offsets through the full chain
            # cdi_sc_start is the tape frame offset; src_offset is the usage start within the subclip
            total_offset = cdi_sc_start + master_sc_start + sub_sc_start + src_offset
            src_start_tc = str(Timecode(fps, frames=total_offset + 1))
            src_end_tc = str(Timecode(fps, src_start_tc) + length)

            # Record TCs computed from sequence start + cumulative timeline position
            rec_start_tc = str(base_tc + timeline_pos)
            rec_end_tc = str(base_tc + (timeline_pos + length))

            # Check for existing clip note and color (_COMMENT, _COLOR_R/G/B on ComponentAttributeList)
            clip_note_raw = ""
            clip_note_id = None
            clip_note_desc = ""
            color_vals = {}
            if target_comp is not None:
                attr_list = target_comp.get('ComponentAttributeList')
                if attr_list:
                    for attr in attr_list:
                        if attr.name == '_COMMENT' and attr.value:
                            clip_note_raw = attr.value
                            parts = attr.value.split(None, 1)
                            clip_note_id = parts[0]
                            clip_note_desc = parts[1] if len(parts) > 1 else ""
                        elif attr.name in ('_COLOR_R', '_COLOR_G', '_COLOR_B'):
                            color_vals[attr.name] = attr.value
            clip_color = 'none'
            if len(color_vals) == 3:
                r16, g16, b16 = color_vals['_COLOR_R'], color_vals['_COLOR_G'], color_vals['_COLOR_B']
                for name, vals in CLIP_COLOR_MAP.items():
                    if vals == (r16, g16, b16):
                        clip_color = name
                        break

            # Check for existing marker within this clip's timeline range
            marker_id = None
            marker_desc = ""
            for pos, vid in existing_markers.items():
                if timeline_pos <= pos < timeline_pos + length:
                    parts = vid.split(None, 1)
                    marker_id = parts[0]
                    marker_desc = parts[1] if len(parts) > 1 else ""
                    break

            # Generate VFX ID from subclip name (has scene number, same as *FROM CLIP NAME in EDL)
            # Always advance counter so new clips get the correct next ID even if some have existing IDs
            scene_match = re.search(r'\d+', clip_name)
            scene_clip = scene_match.group().rjust(3, '0') if scene_match else str(event_num + 1).rjust(3, '0')

            if scene_clip == last_scene:
                VFX_counter += 10
            else:
                VFX_counter = 10
            last_scene = scene_clip

            event_num += 1
            generated_id = create_string('_', ProjectID, scene_clip, str(VFX_counter).rjust(4, '0'))
            # Use existing VFX ID if found (clip note takes priority over marker); otherwise generated
            vfx_id = clip_note_id or marker_id or generated_id
            job_description = clip_note_desc or marker_desc

            event = {
                "type": "event",
                "event_number": str(event_num),
                "reel": reel_name,
                "track": "V",
                "transition": "C",
                "source_start_TC": src_start_tc,
                "source_end_TC": src_end_tc,
                "record_start_TC": rec_start_tc,
                "record_end_TC": rec_end_tc,
                "FROM": clip_name,
                "LOC": "",
                "SOURCE": reel_name,
                "VFX ID": vfx_id,
                "job_description": job_description,
                "clip_note": clip_note_raw,
                "color": clip_color,
                "has_clip_note": bool(clip_note_id),
                "has_marker": bool(marker_id),
            }
            edl_data["events"].append(event)
            status = []
            if clip_note_id:
                status.append('note')
            if marker_id:
                status.append('marker')
            status_str = f' [existing: {", ".join(status)}]' if status else ''
            event_lines.append(f"  Event {event_num}: {clip_name} -> {vfx_id}  [{rec_start_tc} - {rec_end_tc}]{status_str}")
            timeline_pos += length

    # If SOME clips have existing IDs and others don't, warn but still load with empty VFX ID
    events_with_id    = [e for e in edl_data['events'] if e['has_clip_note'] or e['has_marker']]
    events_without_id = [e for e in edl_data['events'] if not e['has_clip_note'] and not e['has_marker']]
    if events_with_id and events_without_id:
        print(f"Warning: AAF has VFX IDs on some clips but {len(events_without_id)} clip(s) are missing both marker and clip note:", file=sys.stderr)
        for e in events_without_id:
            print(f"  [{e['record_start_TC']}]  {e['FROM']}", file=sys.stderr)
        print("Missing VFX IDs will be empty in the project.", file=sys.stderr)
        for e in events_without_id:
            e['VFX ID'] = ''

    for line in event_lines:
        print(line)
    print(f"\nFound {event_num} clips in AAF timeline.")
    return edl_data


def export_final_vfx_edl(json_file_path: str, final_vfx_bin: str, edl_final_file_path: str):
    """Export an EDL for cutting in final vfx in AVID."""
    AVID_bin_data = read_csv(final_vfx_bin, delimiter='\t') # Read AVID bin file
    # print(AVID_bin_data)
    
    with open(json_file_path) as input_file:    # Open JSON file
        json_file = json.load(input_file)   # Load JSON file
    
    if not confirm_overwrite(edl_final_file_path):
        return
    try:
        with open(edl_final_file_path, 'w') as output_file:   # Open EDL file
            heading = 'TITLE: ' + os.path.splitext(os.path.basename(edl_final_file_path))[0]+ '\n'\
            'FCM: NON-DROP FRAME\n'    # Define EDL heading
            output_file.write(heading)  # Write heading to EDL file
            for i in range(len(AVID_bin_data['Name'])):  # Loop through AVID bin file
                # print(AVID_bin_data['Name'][i])
                for j in range(len(json_file['events'])):   # Loop through JSON file
                    # print(json_file['events'][j]['VFX ID'])
                    if json_file['events'][j]['VFX ID'] in AVID_bin_data['Name'][i]:    # Check if VFX ID is in AVID bin file name
                        print("Processed: ", json_file['events'][j]['VFX ID'])
                        edl_final_file_line = create_string(
                            ' ', 
                            json_file['events'][j]['event_number'], 
                            AVID_bin_data['Name'][i], 
                            json_file['events'][j]['track'], 
                            json_file['events'][j]['transition'], 
                            json_file['events'][j]['source_start_TC'], 
                            json_file['events'][j]['source_end_TC'],
                            # str(Timecode(fps, json_file['events'][i]['source_end_TC']) - 1), # per gestire i consolidati senza maniglie... 
                            json_file['events'][j]['record_start_TC'], 
                            json_file['events'][j]['record_end_TC'],
                        )
                        # print(edl_final_file_line)
                        # edl_final_file_line = json_file['events'][j]['event_number'] + ' ' + AVID_bin_data['Name'][i] + ' ' + json_file['events'][j]['track'] + ' ' + \
                        # json_file['events'][j]['transition'] + ' ' + json_file['events'][j]['source_start_TC'] + ' ' + json_file['events'][j]['source_end_TC'] + ' ' + \
                        # json_file['events'][j]['record_start_TC'] + ' ' + json_file['events'][j]['record_end_TC']   # Define EDL file line
                        output_file.write(edl_final_file_line + '\n')   # Write line to EDL file
            print(f"Succesfully exported EDL file: {edl_final_file_path}")  # Print success message
    except Exception as e:  # Catch exception
        print(f"Error writing {edl_final_file_path}: {e}")  # Print error message


def main():

    global ProjectID, fps, handles

    parser = argparse.ArgumentParser(description='Import EDL, create project and export various stuff for AVID')

    parser.add_argument('-i', '--init', action='store_true', help='Initialize project settings (Project ID, FPS, resolution, handles)')
    parser.add_argument('-e', '--edl', metavar='FILE', help='Import an EDL or AAF and create a project file')
    parser.add_argument('-a', '--aaf_write', action='store_true', help='Export a new AAF with VFX ID clip notes (requires project imported from AAF via -e)')
    parser.add_argument('-m', '--markers', action='store_true', help='Export markers file for AVID (interactive options)')
    parser.add_argument('-s', '--subcaps', action='store_true', help='Export subcaps file for AVID')
    parser.add_argument('-p', '--pulls', action='store_true', help='Export ALE and EDL files for creating pulls in AVID bin')
    parser.add_argument('-t', '--tab', nargs='?', const=True, metavar='ALE', help='Export TAB spreadsheet. Optionally pass an ALE file to merge ALE columns.')
    parser.add_argument('-f', '--final', metavar='BIN', help='Export EDL for cutting in final vfx in AVID, requires an AVID bin (TAB)')
    parser.add_argument('-c', '--compare', metavar='NEW_EDL', help='Compare new EDL against loaded project and export changelist markers file')

    args = parser.parse_args()

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(0)

    if args.init:
        if os.path.exists(PROJECT_FILE):
            with open(PROJECT_FILE) as f:
                project = json.load(f)
            old_config = project.get('config', DEFAULT_CONFIG.copy())
        else:
            project = {'config': {}, 'edl_metadata': {}, 'events': []}
            old_config = DEFAULT_CONFIG.copy()
        project_id, fps_val, resolution, handles_val = prompt_init_options(old_config)
        old_config.update({
            'ProjectID': project_id,
            'fps': fps_val,
            'resolution': resolution,
            'handles': handles_val,
        })
        project['config'] = old_config
        os.makedirs(PROJECT_DIR, exist_ok=True)
        with open(PROJECT_FILE, 'w') as f:
            json.dump(project, f, indent=2)
        print(f"\nProject initialized:")
        print(f"  Project ID:  {project_id}")
        print(f"  FPS:         {fps_val}")
        print(f"  Resolution:  {resolution}")
        print(f"  Handles:     {handles_val}")
    elif args.edl:
        if os.path.exists(PROJECT_FILE):
            with open(PROJECT_FILE) as f:
                old_config = json.load(f).get('config', DEFAULT_CONFIG)
        else:
            old_config = DEFAULT_CONFIG.copy()
        project_id = old_config.get('ProjectID', DEFAULT_CONFIG['ProjectID'])
        fps_val    = old_config.get('fps', DEFAULT_CONFIG['fps'])
        ProjectID  = project_id
        fps        = fps_val
        input_file = args.edl
        input_dir  = os.path.dirname(os.path.abspath(input_file))
        if os.path.splitext(input_file)[1].lower() == '.aaf':
            check_aaf_project_settings(input_file, old_config)
            file_data = aaf_to_json(input_file)
        else:
            file_data = edl_to_json(input_file)
        project = {
            'config': {
                'edl_file': os.path.basename(input_file),
                'edl_dir': input_dir,
                'ProjectID': project_id,
                'fps': fps_val,
                'resolution': old_config.get('resolution', DEFAULT_CONFIG['resolution']),
                'handles': old_config.get('handles', DEFAULT_CONFIG['handles']),
                'markers': old_config.get('markers', DEFAULT_CONFIG['markers']),
            },
            'edl_metadata': file_data['edl_metadata'],
            'events': file_data['events'],
        }
        save_project(project)
        print("Project saved.")
    elif args.markers:
        project = load_project()
        edl_dir = project['config']['edl_dir']
        edl_stem = os.path.splitext(project['config']['edl_file'])[0]
        user, track, color, position = prompt_markers_options(project['config'])
        project['config']['markers'] = {'user': user, 'track': track, 'color': color, 'position': position}
        save_project(project)
        print("\nExported:")
        json_to_markers(PROJECT_FILE, os.path.join(edl_dir, edl_stem + '_markers.txt'), user, track, color, position)
    elif args.subcaps:
        project = load_project()
        edl_dir = project['config']['edl_dir']
        edl_stem = os.path.splitext(project['config']['edl_file'])[0]
        print("\nExported:")
        json_to_subcaps(PROJECT_FILE, os.path.join(edl_dir, edl_stem + '_subcaps.txt'))
    elif args.pulls:
        project = load_project()
        edl_dir = project['config']['edl_dir']
        edl_stem = os.path.splitext(project['config']['edl_file'])[0]
        print("\nExported:")
        export_ale_pulls(PROJECT_FILE, os.path.join(edl_dir, edl_stem + '.ALE'))
        export_pulls_edl(PROJECT_FILE, os.path.join(edl_dir, edl_stem + '_pulls.edl'))
    elif args.tab is not None:
        project = load_project()
        edl_dir = project['config']['edl_dir']
        edl_stem = os.path.splitext(project['config']['edl_file'])[0]
        if args.tab is True:
            export_google_tab(PROJECT_FILE, os.path.join(edl_dir, edl_stem + '_TAB.txt'))
        else:
            ale_stem = os.path.splitext(os.path.basename(args.tab))[0]
            out_path = os.path.join(edl_dir, f"{edl_stem}_{ale_stem}_merge.txt")
            print("\nExported:")
            merge_ale_tab(PROJECT_FILE, args.tab, out_path)
    elif args.final:
        project = load_project()
        edl_dir = project['config']['edl_dir']
        edl_stem = os.path.splitext(project['config']['edl_file'])[0]
        export_final_vfx_edl(PROJECT_FILE, args.final, os.path.join(edl_dir, edl_stem + '_vfx_final.edl'))
    elif args.compare:
        project = load_project()
        new_edl = args.compare
        config = project['config']
        fps_val = config['fps']
        ProjectID = config['ProjectID']
        fps = fps_val
        m = config.get('markers', DEFAULT_CONFIG['markers'])
        handles_val = config.get('handles') or DEFAULT_CONFIG['handles']
        handles = handles_val
        user  = input(f"AVID user name [default: {m['user']}]: ").strip() or m['user']
        track = prompt_choice("Marker track:", MARKER_TRACKS, m.get('track', 'V1'))
        color = prompt_choice("Marker color:", MARKER_COLORS, m['color'])
        print()
        project['config']['markers'] = {**m, 'user': user, 'track': track, 'color': color}
        save_project(project)
        old_events = project['events']
        new_data = edl_to_json(new_edl)
        events = compare_edls(old_events, new_data['events'], fps_val, handles_val)
        counts = {}
        for e in events:
            s = e.get('change_status', 'unchanged')
            counts[s] = counts.get(s, 0) + 1
        print("\nChangelist summary:")
        order = [
            ('new',               'new'),
            ('removed',           'removed'),
            ('moved',             'moved'),
            ('trimmed_ok',        'trimmed (no pull)'),
            ('trimmed_pull',      'trimmed (need pull)'),
            ('moved_trimmed_ok',  'moved+trimmed (no pull)'),
            ('moved_trimmed_pull','moved+trimmed (need pull)'),
            ('unchanged',         'unchanged'),
        ]
        for key, label in order:
            if counts.get(key):
                print(f"  {counts[key]:>3}  {label}")
        new_dir  = os.path.dirname(os.path.abspath(new_edl))
        new_stem = os.path.splitext(os.path.basename(new_edl))[0]
        print("\nExported:")
        output_path = os.path.join(new_dir, new_stem + '_changelist_markers.txt')
        export_changelist_markers(events, fps_val, output_path, user, track, color)
        tab_path = os.path.join(new_dir, new_stem + '_changelist_TAB.txt')
        export_changelist_tab(events, fps_val, handles_val, tab_path)
    elif args.aaf_write:
        project = load_project()
        aaf_file = os.path.join(project['config']['edl_dir'], project['config']['edl_file'])
        if not aaf_file.lower().endswith('.aaf'):
            print("Error: project was not imported from an AAF. Run -e with an AAF file first.", file=sys.stderr)
            sys.exit(1)
        check_aaf_consistency(aaf_file)
        user, color, position, clip_color = prompt_aaf_options(project['config'])
        project['config']['markers'] = {'user': user, 'color': color, 'position': position, 'clip_color': clip_color}
        save_project(project)
        aaf_stem = os.path.splitext(project['config']['edl_file'])[0]
        output_aaf = os.path.join(project['config']['edl_dir'], aaf_stem + '_new.aaf')
        json_to_aaf(PROJECT_FILE, aaf_file, output_aaf, user, color, position, clip_color)
        for event in project['events']:
            vfx_id  = event['VFX ID']
            job_desc = event.get('job_description', '')
            event['clip_note'] = f"{vfx_id} {job_desc}".strip() if job_desc else vfx_id
            if clip_color != 'none':
                event['color'] = clip_color
        save_project(project)


if __name__ == "__main__":
    main()