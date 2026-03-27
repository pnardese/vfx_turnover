---
name: pyaaf2
description: Reference for working with AAF files using pyaaf2. Use when reading, writing or manipulating AAF files, extracting markers, clip notes, timecode, or metadata from Avid AAF.
---

# pyaaf2 Reference

## Key AAF Concepts

- `CompositionMob`: Represents timelines/sequences. Find the main one via `f.content.toplevel()`.
- `EventMobSlot`: Contains markers (`DescriptiveMarker` instances).
- `TimelineMobSlot`: Contains video/audio segments. Has `SlotName`, `SlotID`, `PhysicalTrackNumber`, `EditRate`.
- `SourceClip`: Individual clips on tracks. References a subclip `CompositionMob` which references a `MasterMob`.
- `Selector`: Wraps a `SourceClip` with alternates (alt takes). Access selected clip via `comp['Selected'].value`. The `_COMMENT` lives on the `Selector`, not the inner clip.
- `OperationGroup`: Wraps clips with effects (e.g. dissolves). Iterate `InputSegments` to find the underlying `SourceClip`.
- `Filler`: Empty/gap segments — skip these when iterating components, but still advance `timeline_pos` by their `length`.
- `DescriptiveMarker`: Timeline markers. Access via `.get('CommentMarkerAttributeList')` — look for `_ATN_CRM_COM` (VFX ID), `_ATN_CRM_USER`, `_ATN_CRM_COLOR`.
- `UserComments`: Metadata on mobs. Access via `mob.get('UserComments')` — returns `TaggedValue` list with `.name` and `.value`.
- Clip notes stored as `_COMMENT` `TaggedValue` in `ComponentAttributeList`.

## Avid Mob Hierarchy (Sequence Export)

In an Avid AAF sequence export, each timeline clip references a 4-level chain:

```
Timeline CompositionMob
  └─ video slot → SourceClip  (comp.start = usage offset in SubClip)
       └─ comp.mob = SubClip CompositionMob  (name = scene-based, e.g. "33-2-/01 A")
            └─ picture slot → SourceClip  (StartTime = offset in MasterMob, usually 0)
                 └─ .mob = MasterMob  (name = camera roll without _001, e.g. "A059_A006_0519W9")
                      └─ picture Sequence → SourceClip  (StartTime = 0)
                           └─ .mob = CDCIDescriptor SourceMob  (same name as MasterMob)
                                └─ picture Sequence → SourceClip  (StartTime = TAPE OFFSET ← key!)
                                     └─ .mob = TapeDescriptor SourceMob  (name with _001, e.g. "A059_A006_0519W9_001")
```

- **SubClip name** → scene-based Avid bin name → use for VFX ID scene extraction
- **TapeDescriptor name** (with `_001`) → reel/tape name → use for `reel` / `SOURCE` fields
- **CDCIDescriptor SourceClip.StartTime** → tape frame offset (0-based from midnight) → key for source TC

## Timecode

### Sequence start TC
Found in the main `CompositionMob`'s `Timecode` slot. Value is 0-based frames from midnight:

```python
tc_start_str = '01:00:00:00'  # Avid default
for slot in main_mob.slots:
    if type(slot.segment).__name__ == 'Timecode':
        tc_start_str = str(Timecode(fps, frames=slot.segment['Start'].value + 1))
        break
```

### SourceClip start offset
Use `comp.start` — **not** `comp['StartTime'].value` (the `[]` accessor fails; `StartTime` IS a valid
property but must be read via `properties()` iterator or `.start` attribute):

```python
src_offset = getattr(comp, 'start', 0) or 0

# If you need to read it via properties():
for p in comp.properties():
    if p.name == 'StartTime':
        src_offset = p.value or 0
        break
```

### Source TC from the full mob chain
Accumulate StartTime offsets through all levels; the CDCIDescriptor SourceMob's StartTime is
the 0-based tape frame offset. Verified to match EDL source TCs exactly.

```python
# Navigate SubClip → MasterMob
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

# Navigate MasterMob → CDCIDescriptor SourceMob
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

# Navigate CDCIDescriptor → TapeDescriptor SourceMob; get tape offset
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
                    tape_mob = sc.mob  # None if media is offline
                    break
        break

# Reel name: TapeDescriptor mob (e.g. "A059_A006_0519W9_001")
reel_name = (tape_mob.name if tape_mob else None) or (master_mob.name if master_mob else None) or subclip.name

# Source TC: sum all offsets; add 1 for timecode library's 1-based frame count
total_offset = cdi_sc_start + master_sc_start + sub_sc_start + src_offset
src_start_tc = str(Timecode(fps, frames=total_offset + 1))
src_end_tc = str(Timecode(fps, src_start_tc) + length)
```

### Timecode library conversion (python `timecode` package)
AAF frame counts are 0-based from midnight. The `timecode` library is 1-based (`frames=1` = `00:00:00:00`):

```python
from timecode import Timecode
# AAF 0-based → timecode library 1-based:
tc = Timecode('24', frames=aaf_frames_0based + 1)
str(tc)  # → "HH:MM:SS:FF"

# Advance a TC by N frames:
str(Timecode('24', '01:00:00:00') + 24)  # → "01:00:01:00"
```

## TaggedValue — IMPORTANT

**Never** instantiate `aaf2.misc.TaggedValue()` directly — it has no file context (`.root` is `None`) and will raise `AttributeError: 'NoneType' object has no attribute 'metadict'`.

**Never** pass `name=` or `value=` as keyword arguments to `f.create.TaggedValue(...)` — the factory's internal `from_name(name, ...)` uses `name` as its own parameter, causing a `TypeError: got multiple values for argument 'name'`.

Always create with no args, then set properties:

```python
tv = f.create.TaggedValue()
tv['Name'].value = '_COMMENT'
tv['Value'].value = some_string
attr_list.append(tv)
```

For markers' `CommentMarkerAttributeList`, pass name and value as **positional** args:

```python
tv = f.create.TaggedValue('_ATN_CRM_COM', vfx_id)
```

## DescriptiveMetadata DataDef

Avid-produced AAFs store this as `'Descriptive Metadata'` (with a space), which pyaaf2's `lookup_datadef()` cannot resolve by canonical name. Register it explicitly before creating `DescriptiveMarker` objects:

```python
def _ensure_descriptive_metadata_def(f):
    try:
        f.dictionary.lookup_datadef('DescriptiveMetadata')
    except Exception:
        dm_dd = f.create.DataDef(
            "01030201-1000-0000-060e-2b3404010101",
            "DataDef_DescriptiveMetadata",
            "Descriptive metadata",
        )
        f.dictionary.register_def(dm_dd)
```

## Iterating Mobs — IMPORTANT

**Never** use `f.content.mobs()` — it raises `TypeError: 'StrongRefSetProperty' object is not callable`.

Use `f.content['Mobs']` to iterate all mobs, or `f.content.toplevel()` for top-level CompositionMobs only:

```python
# All mobs (CompositionMob, MasterMob, SourceMob, ...)
for mob in f.content['Mobs']:
    print(type(mob).__name__, mob.name)

# Top-level CompositionMobs only (main sequences)
for mob in f.content.toplevel():
    print(mob.name)
```

## Reading AAF Metadata (FPS and Resolution)

### FPS from edit rate

```python
# Get FPS from the main CompositionMob's video slot edit_rate
for mob in f.content.toplevel():
    for slot in mob.slots:
        mk = getattr(slot, 'media_kind', None)
        if mk and 'picture' in str(mk).lower() and hasattr(slot.segment, 'components'):
            er = slot.edit_rate
            fps_float = er.numerator / er.denominator
            # Map to common string: 24000/1001→'23.976', 30000/1001→'29.97', etc.
            break
```

Edit rate fractions: `24/1`→24fps, `25/1`→25fps, `24000/1001`→23.976fps, `30000/1001`→29.97fps, `60000/1001`→59.94fps.

### Resolution from CDCIDescriptor

```python
# Get stored height/width from the first CDCIDescriptor SourceMob
for mob in f.content['Mobs']:
    if type(mob).__name__ == 'SourceMob':
        desc = mob.descriptor
        if desc is not None and 'CDCI' in type(desc).__name__:
            height = desc['StoredHeight'].value   # e.g. 1080, 2160
            width  = desc['StoredWidth'].value    # e.g. 1920, 3840
            break
```

`StoredHeight` and `StoredWidth` are confirmed available on Avid-exported AAFs. Wrap in `try/except` when media may be offline.

## Common Patterns

```python
import aaf2
import shutil
import time
import uuid

# Open read-only
with aaf2.open('input.aaf', 'r') as f:
    for mob in f.content.toplevel():
        ...

# Open read-write in place (copy first to preserve original)
shutil.copy2('input.aaf', 'output.aaf')
with aaf2.open('output.aaf', 'rw') as f:
    _ensure_descriptive_metadata_def(f)
    # modify...
    f.save()

# Find the video slot by media_kind; get track name from PhysicalTrackNumber
for slot in mob.slots:
    media_kind = getattr(slot, 'media_kind', None)
    if media_kind and 'picture' in str(media_kind).lower():
        video_slot = slot
        break
track_name = video_slot['SlotName'].value or f"V{video_slot['PhysicalTrackNumber'].value}"

# Iterate components with timeline position tracking
timeline_pos = 0
for comp in video_slot.segment.components:
    comp_type = type(comp).__name__
    length = getattr(comp, 'length', 0) or 0

    if comp_type == 'Filler':
        timeline_pos += length  # advance position even for gaps
        continue

    if isinstance(comp, aaf2.components.SourceClip) and comp.mob:
        target = comp
        clip_name = comp.mob.name

    elif comp_type == 'Selector':
        target = comp  # _COMMENT lives on Selector, not inner clip
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

    # marker at start or middle of clip
    marker_frame = timeline_pos + length // 2  # middle
    # marker_frame = timeline_pos              # start
    timeline_pos += length

# Write or update _COMMENT on a component (must be inside `with aaf2.open(...) as f`)
attr_list = target.get('ComponentAttributeList')
if attr_list is None:
    target['ComponentAttributeList'] = []
    attr_list = target['ComponentAttributeList']

found = False
for attr in attr_list:
    if attr.name == '_COMMENT':
        attr.value = new_value  # update existing
        found = True
        break
if not found:
    tv = f.create.TaggedValue()   # must use f.create, NOT aaf2.misc.TaggedValue()
    tv['Name'].value = '_COMMENT'
    tv['Value'].value = new_value
    attr_list.append(tv)

# Write clip color (_COLOR_R/G/B) on a component
# Values are 16-bit: 8bit_value × 256
# Same pattern as _COMMENT — update existing or append new TaggedValues
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

# Write DescriptiveMarker to an EventMobSlot
# Find or create EventMobSlot
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

# Build and assign markers (StrongRefVectorProperty requires assigning all at once)
now_ts = int(time.time())
color_str = 'Green'
color_rgb = {'red': 13107, 'green': 52428, 'blue': 13107}
new_markers = []
for marker_frame, label in marker_data:
    marker = f.create.DescriptiveMarker()
    marker['Length'].value = 1
    marker['Position'].value = marker_frame
    marker['Comment'].value = label
    marker['CommentMarkerUSer'].value = user   # note: 'USer' not 'User' (pyaaf2 typo)
    marker['CommentMarkerColor'].value = color_rgb
    marker['DescribedSlots'].value = {video_slot.slot_id}
    tv_list = [
        f.create.TaggedValue('_ATN_CRM_COLOR',           color_str),
        f.create.TaggedValue('_ATN_CRM_COLOR_EXTENDED',  color_str),
        f.create.TaggedValue('_ATN_CRM_USER',            user),
        f.create.TaggedValue('_ATN_CRM_COM',             label),
        f.create.TaggedValue('_ATN_CRM_LONG_CREATE_DATE', now_ts),
        f.create.TaggedValue('_ATN_CRM_LONG_MOD_DATE',   now_ts),
        f.create.TaggedValue('_ATN_CRM_LENGTH',          1),
        f.create.TaggedValue('_ATN_CRM_ID',              uuid.uuid4().hex),
    ]
    marker['CommentMarkerAttributeList'].value = tv_list
    new_markers.append(marker)
seq['Components'].value = new_markers

# Pre-collect existing markers by position (before iterating clips)
# Use this to preserve or reuse existing markers when writing a modified AAF
existing_markers_by_pos = {}
for slot in mob.slots:
    if type(slot).__name__ == 'EventMobSlot':
        for m in slot.segment.components:
            try:
                existing_markers_by_pos[m['Position'].value] = m
            except Exception:
                pass
        break

# Per-clip: look up existing marker by timeline position range, extract VFX ID
existing_marker = None
marker_vfx_id = None
for pos, m in existing_markers_by_pos.items():
    if timeline_pos <= pos < timeline_pos + length:
        existing_marker = m
        attrs = m.get('CommentMarkerAttributeList')
        if attrs:
            for tag in attrs:
                if tag.name == '_ATN_CRM_COM' and tag.value:
                    marker_vfx_id = tag.value
                    break
        break
# Use marker's VFX ID if available; fall back to JSON/other source
effective_vfx_id = marker_vfx_id if marker_vfx_id else vfx_id

# Preserve existing markers; merge with new ones (sort by position)
kept_markers = []   # existing marker objects to preserve as-is
new_markers = []    # newly created markers
# ... populate kept_markers and new_markers ...
all_markers = sorted(kept_markers + new_markers, key=lambda m: m['Position'].value)
seq['Components'].value = all_markers

# Read markers from EventMobSlot
for slot in mob.slots:
    if type(slot).__name__ == 'EventMobSlot':
        for marker in slot.segment.components:
            attrs = marker.get('CommentMarkerAttributeList')
            if attrs:
                for tag in attrs:
                    if tag.name == '_ATN_CRM_COM':
                        vfx_id = tag.value

# Read UserComments from mob
for mob in f.content['Mobs']:
    comments = mob.get('UserComments')
    if comments:
        for tag in comments:
            print(tag.name, tag.value)
```

## Marker Color Values (16-bit RGB dict)

Stored as `{'red': int, 'green': int, 'blue': int}` where values are 0–65535:

| Color | red | green | blue |
|---|---|---|---|
| Green | 13107 | 52428 | 13107 |
| Red | 52428 | 13107 | 13107 |
| Blue | 13107 | 13107 | 52428 |
| Cyan | 13107 | 52428 | 52428 |
| Magenta | 52428 | 13107 | 52428 |
| Yellow | 52428 | 52428 | 13107 |
| Black | 0 | 0 | 0 |
| White | 65535 | 65535 | 65535 |

## Clip Color Values (_COLOR_R/G/B, 16-bit = 8-bit × 256)

Extracted from `VFX_48.Colore.aaf` reference file:

| Name | _COLOR_R | _COLOR_G | _COLOR_B |
|---|---|---|---|
| dark blue | 14592 | 11776 | 38144 |
| steel blue | 15104 | 25344 | 37888 |
| dark green | 16896 | 32768 | 13824 |
| cyan | 16896 | 54272 | 62464 |
| teal | 17920 | 39168 | 36864 |
| blue | 22528 | 17920 | 58624 |
| dark grey | 22784 | 22784 | 22784 |
| sky blue | 23040 | 38912 | 58112 |
| green | 25856 | 50432 | 21248 |
| dark purple | 32256 | 12544 | 26880 |
| dark brown | 32256 | 20992 | 13568 |
| olive | 32256 | 32768 | 14336 |
| dark red | 32768 | 9216 | 9216 |
| purple | 36608 | 0 | 45824 |
| mint | 43520 | 65280 | 49920 |
| crimson | 48896 | 0 | 26112 |
| sand | 48896 | 43264 | 36608 |
| light grey | 48896 | 48896 | 48896 |
| violet | 49408 | 19200 | 41216 |
| yellow-olive | 49408 | 50176 | 22016 |
| brown | 49664 | 32256 | 20992 |
| medium red | 51200 | 14592 | 14592 |
| beige | 56064 | 55296 | 47104 |
| light red | 56832 | 25600 | 29696 |
| gold | 58368 | 50688 | 0 |
| lavender | 58880 | 48640 | 65280 |
| magenta | 61440 | 12800 | 58880 |
| yellow-green | 61952 | 65280 | 16384 |
| orange | 62720 | 33280 | 12544 |
| pink | 64000 | 48640 | 48640 |
| rose | 65280 | 0 | 29440 |
| light orange | 65280 | 50176 | 32768 |

## VFX ID Priority (when reading AAF back)

When reading an AAF that may already have IDs annotated:

```python
# clip_note_id: from _COMMENT on ComponentAttributeList
# marker_id:    from _ATN_CRM_COM on the EventMobSlot marker within this clip's range
# generated_id: derived from subclip name + FilmID + counter

vfx_id = clip_note_id or marker_id or generated_id
# clip note takes priority over marker; marker over auto-generated
```

Clip note range check (per-clip, using cumulative `timeline_pos`):
```python
attr_list = target_comp.get('ComponentAttributeList')
if attr_list:
    for attr in attr_list:
        if attr.name == '_COMMENT' and attr.value:
            clip_note_id = attr.value
            break

# marker range check
for pos, vid in existing_markers.items():   # {frame_pos: vfx_id_string}
    if timeline_pos <= pos < timeline_pos + length:
        marker_id = vid
        break
```

## Scripts in ~/Documents/dev/python/opetimelineio/

- `read_aaf.py` — converts AAF to OTIO JSON
- `read_aaf_notes.py` — extracts clips with markers, clip notes, UserComments
- `add_clip_notes.py` — copies AAF and adds `_COMMENT` clip notes
- `read_aafv2.py` — direct pyaaf2 metadata extraction
- `read_notes.py` — extracts main timeline summary
