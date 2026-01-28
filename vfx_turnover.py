import re
import json
import argparse
import os
import sys
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

def edl_to_json(edl_file: str, json_file: str):
    """Reads an EDL file, parses it, and writes the data to a JSON file."""
    
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
    TITLE = ""
    FCM = ""
    last_scene = 0

    try:
        with open(edl_file, 'r') as f:
            for line in f:
                line = line.strip() # Strip leading and trailing whitespace
                if not line: # Skip empty lines
                    continue
                elif line.startswith("TITLE:"):
                    edl_data["edl_metadata"]["edl_title"] = line.strip("TITLE:").strip() # Strip TITLE: and spaces from line
                elif line.startswith("FCM:"):
                    edl_data["edl_metadata"]["edl_fcm"] = line.strip("FCM:").strip() # Strip FCM: and spaces from line
                elif re.match(r'^\d+\s+\w+\s+\w+\s+\w+\s+(\d{2}:\d{2}:\d{2}:\d{2})+\s+(\d{2}:\d{2}:\d{2}:\d{2})+\s+(\d{2}:\d{2}:\d{2}:\d{2})+\s+(\d{2}:\d{2}:\d{2}:\d{2})$',line):
                     parsed_line = parse_edl_line(line)
                     if parsed_line:
                        edl_data["events"].append(parsed_line)
                        last_event = edl_data["events"][-1]
                elif line.startswith("*FROM") or line.startswith("* FROM"):  # Handle comment lines FROM (both formats)
                    from_index = line.find("FROM")
                    last_event["FROM"] = line[from_index + 4:].strip() # Extract text after FROM
                elif line.startswith("*LOC:") or line.startswith("* LOC:"):  # Handle comment lines LOC (both formats)
                    loc_index = line.find("LOC:")
                    loc_value = line[loc_index + 4:].strip()
                    last_event["LOC"] = loc_value # Extract text after LOC:
                    last_event["VFX ID"] = loc_value.split()[-1] # Copy marker comment in VFX ID if present
                elif line.startswith("*SOURCE") or line.startswith("* SOURCE"):  # Handle comment lines SOURCE (both formats)
                    source_index = line.find("SOURCE")
                    last_event["SOURCE"] = line[source_index + 6:].strip() # Extract text after SOURCE
                    if not last_event["LOC"]: # First edl with no markers, create VFX ID
                        scene_clip = last_event["FROM"].strip("*FROM CLIP NAME:").strip() # Strip *FROM CLIP NAME: and spaces from line
                        scene_clip = re.search(r'\d+', scene_clip).group().rjust(3, "0") # Select only scene number an pad to three zeros
                        if scene_clip == last_scene: # Check to see if we still are in the same scene
                            VFX_counter += 10 # Add 10 to VFX counter
                        else:
                            VFX_counter = 10 # Reset VFX counter for new scene
                        last_event["VFX ID"] = create_string("_", FilmID, scene_clip, str(VFX_counter).rjust(3, "0")) # Create VFX ID and write in json file
                        # last_event["VFX ID"] = FilmID + "_" + scene_clip + "_" + str(VFX_counter).rjust(3, "0") # Create VFX ID and write in json file
                        last_scene = scene_clip
                else:
                    print(f"Skipping unparsable line: {line}")  # Print error message

    except FileNotFoundError:
        print(f"Error: EDL file not found: {edl_file}") # Print error message
        return

    try:        
        with open(json_file, 'w') as outfile: # Open JSON file
            json.dump(edl_data, outfile, indent=4) # Write data to JSON file
        print(f"Successfully converted {edl_file} to {json_file}")  # Print success message
    except Exception as e:
        print(f"Error writing JSON file: {e}")  # Print error message


def json_to_markers(json_file_path: str, markers_file_path: str):
    """Reads a JSON file and export a markers file for AVID."""
    user = 'enzo_0624' # Define AVID user name
    track_number = 'V1' # Define track number
    marker_color = 'green' # Define AVID marker color

    with open(json_file_path) as input_file:
        json_file = json.load(input_file) # Load JSON file

    if os.path.exists(markers_file_path): os.remove(markers_file_path) # Remove file if it exists
    try:
        with open(markers_file_path, 'a') as output_file: # Open markers file
            for i in range(len(json_file['events'])): # Loop through JSON file
                markers_file_line = create_string('\t', user, json_file['events'][i]['record_start_TC'], track_number, marker_color, json_file['events'][i]['VFX ID'], '1') # Define markers file line
                # markers_file_line = user + '\t' + json_file['events'][i]['record_start_TC'] + '\t' + track_number + '\t' + marker_color + '\t' + \
                # json_file['events'][i]['VFX ID'] + '\t' + '1' + '\n' # Define markers file line
                output_file.write(markers_file_line + '\n') # Write line to markers file
        print(f"Succesfully exported markers file: {markers_file_path}")    # Print success message
    except Exception as e:
        print(f"Error writing {markers_file_path}: {e}")    # Print error message


def json_to_subcaps(json_file_path: str, sub_file_path: str):
    """Reads a JSON file and export a subcap file for AVID."""
    
    with open(json_file_path) as input_file:
        json_file = json.load(input_file) # Load JSON file

    if os.path.exists(sub_file_path): os.remove(sub_file_path) # Remove file if it exists
    try:
        with open(sub_file_path, 'a') as output_file:
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
        print(f"Succesfully exported subcaps file: {sub_file_path}")    # Print success message
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
    
    if os.path.exists(ale_pulls_file_path): os.remove(ale_pulls_file_path) # Remove file if it exists
    try:
        with open(ale_pulls_file_path, 'a') as output_file:
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
            print(f"Succesfully exported ALE file: {ale_pulls_file_path}")  # Print success message
    except Exception as e:  # Catch exception
        print(f"Error writing {ale_pulls_file_path}: {e}")      # Print error message


def export_pulls_edl(json_file_path: str, edl_pulls_file_path: str):
    """Export an EDL for cutting in pulls in AVID."""
    with open(json_file_path) as input_file:
        json_file = json.load(input_file) # Load JSON file
    
    if os.path.exists(edl_pulls_file_path): os.remove(edl_pulls_file_path) # Remove file if it exists
    try:
        with open(edl_pulls_file_path, 'a') as output_file: # Open EDL file
            heading = 'TITLE: ' + os.path.splitext(edl_pulls_file_path)[0]+ '\n'\
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
            print(f"Succesfully exported EDL file: {edl_pulls_file_path}")  # Print success message
    except Exception as e:  # Catch exception
        print(f"Error writing {edl_pulls_file_path}: {e}")  # Print error message


def export_dummy_edl(json_file_path: str, dummy_edl_file_path: str):
    """Export a Dummy EDL of VFX in AVID."""
    with open(json_file_path) as input_file: # Open JSON file
        json_file = json.load(input_file)   # Load JSON file
    if os.path.exists(dummy_edl_file_path): os.remove(dummy_edl_file_path)      # Remove file if it exists

    try:
        with open(dummy_edl_file_path, 'a') as output_file: # Open EDL file
            heading = 'TITLE: ' + os.path.splitext(dummy_edl_file_path)[0]+ '\n'\
            'FCM: NON-DROP FRAME\n'     # Define EDL heading
            output_file.write(heading)  # Write heading to EDL file
            for i in range(len(json_file['events'])):   # Loop through JSON file
                dummy_edl_file_line = create_string(
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
                # dummy_edl_file_line = json_file['events'][i]['event_number'] + ' ' + json_file['events'][i]['VFX ID'] + ' ' + json_file['events'][i]['track'] + ' ' + \
                # json_file['events'][i]['transition'] + ' ' + json_file['events'][i]['source_start_TC'] + ' ' + json_file['events'][i]['source_end_TC'] + ' ' + \
                # json_file['events'][i]['record_start_TC'] + ' ' + json_file['events'][i]['record_end_TC']   # Define EDL file line
                output_file.write(dummy_edl_file_line + '\n')   # Write line to EDL file
            print(f"Succesfully exported EDL file: {dummy_edl_file_path}")  # Print success message
    except Exception as e:  # Catch exception
        print(f"Error writing {dummy_edl_file_path}: {e}")      # Print error message


def export_google_tab(json_file_path: str, google_file_path: str):
    """Export a TAB file to import into a Spreadsheet."""
    
    with open(json_file_path) as input_file:    # Open JSON file
        json_file = json.load(input_file)   # Load JSON file
    if os.path.exists(google_file_path): os.remove(google_file_path)    # Remove file if it exists
    try:
        with open(google_file_path, 'a') as output_file:    # Open TAB file
            heading = '#' + '\t' + 'Name' + '\t' + 'Frame' + '\t' + 'Comments' + '\t' + 'Status' + '\t' + 'Date' + '\t' + 'Duration' + '\t' + 'Start' + '\t' +\
            'End' + '\t' + 'Frame Count Duration' + '\t' + 'Tape'   # Define TAB heading
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
                    '', 
                    '', 
                    str(duration), 
                    json_file['events'][i]['source_start_TC'],
                    json_file['events'][i]['source_end_TC'],
                    # str(Timecode(fps, json_file['events'][i]['source_end_TC']) - 1), # per gestire i consolidati senza maniglie...
                    str(number_of_frames),
                    json_file['events'][i]['reel'],
                )
                # google_file_line = str(counter) + '\t' +  json_file['events'][i]['VFX ID'] + '\t' + '\t' + '\t' + '\t' + '\t' + str(duration) + '\t' + json_file['events'][i]['source_start_TC'] + '\t' +\
                # json_file['events'][i]['source_end_TC'] + '\t' + str(number_of_frames) + '\t' + json_file['events'][i]['reel']  # Define TAB file line
                output_file.write(google_file_line + '\n')  # Write line to TAB file
                counter += 1    # Increment counter
            print(f"Succesfully exported TAB file: {google_file_path}")   # Print success message
    except Exception as e:  # Catch exception
        print(f"Error writing {google_file_path}: {e}")  # Print error message


def export_final_vfx_edl(json_file_path: str, final_vfx_bin: str, edl_final_file_path: str):
    """Export an EDL for cutting in final vfx in AVID."""
    AVID_bin_data = read_csv(final_vfx_bin, delimiter='\t') # Read AVID bin file
    # print(AVID_bin_data)
    
    with open(json_file_path) as input_file:    # Open JSON file
        json_file = json.load(input_file)   # Load JSON file
    
    if os.path.exists(edl_final_file_path): os.remove(edl_final_file_path)  # Remove file if it exists
    try:
        with open(edl_final_file_path, 'a') as output_file:   # Open EDL file
            heading = 'TITLE: ' + os.path.splitext(edl_final_file_path)[0]+ '\n'\
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


if __name__ == "__main__":

    global FilmID, fps, handles, VIDEO_FORMAT, AUDIO_FORMAT
    FilmID='ABC' # Define film code
    fps='24'  # Define frame rate
    handles=0  # Define handles

    parser = argparse.ArgumentParser(description='Import EDL, create JSON and export various stuff for AVID')   # Define parser

    parser.add_argument('-e', '--edl', metavar =(''), help='Import an EDL and export a JSON, requires an EDL')  # Define arguments
    parser.add_argument('-m', '--markers', metavar =(''), help='Export markers for AVID, requires a JSON')  # Define arguments
    parser.add_argument('-s', '--subcaps', metavar =(''), help='Export subcaps file for AVID, requires a JSON') # Define arguments
    parser.add_argument('-p', '--pulls', metavar =(''), help='Export ALE file for creating pulls in AVID bin, requires a JSON') # Define arguments
    parser.add_argument('-x', '--edl_pulls', metavar =(''), help='Export EDL for cutting in pulls in AVID, requires a JSON')    # Define arguments
    parser.add_argument('-d', '--dummy_edl', metavar =(''), help='Export Dummy EDL of VFX in AVID, requires a JSON')        # Define arguments
    parser.add_argument('-g', '--google', metavar =(''), help='Export TAB file to import into a Spreadsheet, requires a JSON')  # Define arguments
    parser.add_argument('-f', '--final', nargs=2, metavar=('JSON file', 'BIN file'), help='Export EDL for cutting in final vfx in AVID, requires a JSON and an AVID bin (TAB)') # Define arguments
      
    args = parser.parse_args() # Call function to parse arguments

    if len(sys.argv) == 1:  # Check if no arguments are given
        parser.print_help(sys.stderr)  # Print help message
        sys.exit(0) # Exit program
    
    if args.edl:
        edl_file_path =  args.edl # EDL input 
        edl_filename = os.path.splitext(edl_file_path)[0] # Remove extension from EDL file
        json_file_path = edl_filename + ".json"  #  JSON output file
        edl_to_json(edl_file_path, json_file_path) # Call function to write edl to json
    elif args.markers:
        json_file_path = args.markers # JSON file input
        json_filename = os.path.splitext(json_file_path)[0] # Remove extension from JSON file
        markers_file_path = json_filename + "_markers.txt"  # Markers output file    
        json_to_markers(json_file_path, markers_file_path) # Call function to write json to markers
    elif args.subcaps:
        json_file_path = args.subcaps # JSON file input
        json_filename = os.path.splitext(json_file_path)[0] # Remove extension from JSON file
        sub_file_path = json_filename + "_subcaps.txt"  # Subcaps output file
        json_to_subcaps(json_file_path, sub_file_path) # Call function to write json to subcaps
    elif args.pulls:
        json_file_path = args.pulls # JSON file input
        json_filename = os.path.splitext(json_file_path)[0] # Remove extension from JSON file
        ale_pulls_file_path = json_filename + ".ALE"  # ALE output file
        export_ale_pulls(json_file_path, ale_pulls_file_path) # Call function to write json to ALE
    elif args.edl_pulls:
        json_file_path = args.edl_pulls # JSON file input
        json_filename = os.path.splitext(json_file_path)[0] # Remove extension from JSON file
        edl_pulls_file_path = json_filename + "_pulls.edl"  # ALE output file
        export_pulls_edl(json_file_path, edl_pulls_file_path)   # Call function to write json to EDL for cutting in pulls in AVID
    elif args.dummy_edl:
        json_file_path = args.dummy_edl # JSON file input
        json_filename = os.path.splitext(json_file_path)[0] # Remove extension from JSON file
        dummy_edl_file_path = json_filename + "_dummy.edl"  # Dummy EDL output file
        export_dummy_edl(json_file_path, dummy_edl_file_path) # Call function to write json to dummy EDL
    elif args.google:
        json_file_path = args.google # JSON file input
        json_filename = os.path.splitext(json_file_path)[0] # Remove extension from JSON file
        google_file_path = json_filename + "_TAB.txt"  # ALE output file
        export_google_tab(json_file_path, google_file_path) # Call function to write json to TAB file
    elif args.final:
        json_file_path = args.final[0] # JSON file input
        json_filename = os.path.splitext(json_file_path)[0] # Remove extension from JSON file
        edl_final_file_path = json_filename + "_vfx_final.edl"  # EDL output file
        final_vfx_bin = args.final[1] # AVID bin file input
        export_final_vfx_edl(json_file_path, final_vfx_bin, edl_final_file_path) # Call function to write json to EDL for cutting in final vfx in AVID