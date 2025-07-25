"""
LangChain tools for song structure manipulation and music composition.
"""

import json
import uuid
from typing import Dict, List, Any
from datetime import datetime

try:
    from langchain.tools import tool
except ImportError:
    tool = lambda func: func  # Simple decorator fallback

from .music_tools import MusicCompositionTools
from .utils import safe_log_error, get_chord_progression_for_key, get_suggested_tempo, get_roman_numerals


def optimize_clips_simple(clips: List[Dict]) -> List[Dict]:
    """Simple clip optimization to remove overlaps"""
    if not clips:
        return clips
    
    # Sort clips by start time
    sorted_clips = sorted(clips, key=lambda x: x.get('startTime', 0))
    optimized = []
    
    for clip in sorted_clips:
        if not optimized:
            optimized.append(clip)
            continue
        
        last_clip = optimized[-1]
        last_end = last_clip.get('startTime', 0) + last_clip.get('duration', 0)
        current_start = clip.get('startTime', 0)
        
        # If clips overlap, adjust the current clip's start time
        if current_start < last_end:
            clip = clip.copy()  # Don't modify original
            clip['startTime'] = last_end
            # Adjust duration if necessary
            original_end = current_start + clip.get('duration', 0)
            if original_end > last_end:
                clip['duration'] = original_end - last_end
            else:
                clip['duration'] = 0.5  # Minimum duration
        
        optimized.append(clip)
    
    return optimized


def combine_consecutive_clips(clips: List[Dict]) -> List[Dict]:
    """
    Combine consecutive clips for the same instrument with no gaps between them.
    
    Args:
        clips: List of clip dictionaries
        
    Returns:
        List of optimized clips with consecutive clips combined
    """
    if not clips:
        return clips
        
    try:
        # Sort clips by start time
        sorted_clips = sorted(clips, key=lambda x: x.get('startTime', 0))
        combined_clips = []
        
        current_clip = None
        
        for clip in sorted_clips:
            if current_clip is None:
                # First clip
                current_clip = clip.copy()
                continue
            
            # Check if this clip can be combined with the current one
            current_end_time = current_clip.get('startTime', 0) + current_clip.get('duration', 0)
            clip_start_time = clip.get('startTime', 0)
            
            # Check if clips are consecutive (no gap) and same instrument
            if (current_clip.get('instrument') == clip.get('instrument') and
                current_clip.get('trackId') == clip.get('trackId') and
                abs(current_end_time - clip_start_time) < 0.01):  # Allow tiny floating point differences
                
                # Combine the clips by extending duration and merging notes
                current_clip['duration'] = clip_start_time + clip.get('duration', 0) - current_clip.get('startTime', 0)
                
                # Merge notes if they exist
                current_notes = current_clip.get('notes', [])
                clip_notes = clip.get('notes', [])
                
                if isinstance(current_notes, list) and isinstance(clip_notes, list):
                    # Combine unique notes to avoid duplicates
                    combined_notes = current_notes.copy()
                    for note in clip_notes:
                        if note not in combined_notes:
                            combined_notes.append(note)
                    current_clip['notes'] = combined_notes
                
                # Keep other properties from current clip (volume, effects, etc.)
                # but update the ID to reflect the combination
                current_clip['id'] = f"clip-{uuid.uuid4().hex[:8]}"
                
            else:
                # Can't combine - add current clip to results and start new one
                combined_clips.append(current_clip)
                current_clip = clip.copy()
        
        # Add the last clip
        if current_clip is not None:
            combined_clips.append(current_clip)
        
        return combined_clips
        
    except Exception as e:
        safe_log_error(f"Error combining consecutive clips: {e}")
        # Return original clips if combining fails
        return clips


@tool
def analyze_song_structure(song_json: str) -> str:
    """
    Analyze the current song structure and provide detailed feedback.
    
    Args:
        song_json: Current song structure as JSON string
    
    Returns:
        Analysis of the song structure with suggestions
    """
    try:
        if isinstance(song_json, dict):
            song = song_json
        else:
            song = json.loads(song_json)
        
        tracks = song.get('tracks', [])
        tempo = song.get('tempo', 120)
        key = song.get('key', 'C')
        duration = song.get('duration', 0)
        
        analysis = []
        analysis.append(f"Song Analysis:")
        analysis.append(f"- Tempo: {tempo} BPM")
        analysis.append(f"- Key: {key}")
        analysis.append(f"- Duration: {duration} bars")
        analysis.append(f"- Tracks: {len(tracks)}")
        
        if tracks:
            instruments = [track.get('instrument', 'unknown') for track in tracks]
            categories = list(set([track.get('category', 'unknown') for track in tracks]))
            
            analysis.append(f"- Instruments: {', '.join(instruments)}")
            analysis.append(f"- Categories: {', '.join(categories)}")
            
            # Check for common missing elements
            missing = []
            if not any('drum' in inst.lower() or cat == 'percussion' for inst, cat in zip(instruments, categories)):
                missing.append('drums/percussion')
            if not any('bass' in inst.lower() for inst in instruments):
                missing.append('bass')
            if not any(cat in ['keyboards', 'strings'] for cat in categories):
                missing.append('harmonic instruments')
            
            if missing:
                analysis.append(f"- Suggested additions: {', '.join(missing)}")
            
            # Clip analysis
            total_clips = sum(len(track.get('clips', [])) for track in tracks)
            analysis.append(f"- Total clips: {total_clips}")
        else:
            analysis.append("- No tracks yet - start by adding instruments")
        
        return '\n'.join(analysis)
        
    except Exception as e:
        return f"Error analyzing song: {str(e)}"


@tool
def get_available_instruments() -> str:
    """
    Get a list of all available instruments categorized by type.
    
    Returns:
        JSON string with available instruments organized by category
    """
    try:
        music_tools = MusicCompositionTools()
        return json.dumps(music_tools.available_instruments, indent=2)
    except Exception as e:
        return f"Error getting instruments: {str(e)}"


@tool
def get_available_samples(category: str = "", instrument: str = "") -> str:
    """
    Get available samples for instruments, optionally filtered by category or instrument.
    
    Args:
        category: Filter by instrument category (e.g., 'drums', 'strings')
        instrument: Filter by specific instrument name
    
    Returns:
        JSON string with available samples
    """
    try:
        music_tools = MusicCompositionTools()
        samples = music_tools.available_samples
        
        if category:
            samples = {cat: insts for cat, insts in samples.items() if cat.lower() == category.lower()}
        
        if instrument:
            for cat, insts in samples.items():
                samples[cat] = {inst: samps for inst, samps in insts.items() if instrument.lower() in inst.lower()}
        
        return json.dumps(samples, indent=2)
    except Exception as e:
        return f"Error getting samples: {str(e)}"


@tool
def create_track(song_json: str, track_name: str, instrument: str, category: str = "") -> str:
    """
    Create a new track in the song structure.
    
    Args:
        song_json: Current song structure as JSON string
        track_name: Name for the new track
        instrument: Instrument to use for the track
        category: Category of the instrument (optional)
    
    Returns:
        Updated song structure with new track added
    """
    try:
        if isinstance(song_json, dict):
            song = song_json
        else:
            song = json.loads(song_json)
        
        # Auto-detect category if not provided
        if not category:
            instrument_lower = instrument.lower()
            if any(word in instrument_lower for word in ['drum', 'kick', 'snare', 'hihat', 'cymbal']):
                category = 'percussion'
            elif any(word in instrument_lower for word in ['bass', 'sub']):
                category = 'strings'
            elif any(word in instrument_lower for word in ['piano', 'synth', 'organ']):
                category = 'keyboards'
            elif any(word in instrument_lower for word in ['guitar', 'violin', 'cello']):
                category = 'strings'
            elif any(word in instrument_lower for word in ['vocal', 'voice', 'singer']):
                category = 'vocals'
            else:
                category = 'other'
        
        new_track = {
            "id": f"track-{uuid.uuid4().hex[:8]}",
            "name": track_name,
            "instrument": instrument,
            "category": category,
            "volume": 0.8,
            "pan": 0,
            "muted": False,
            "solo": False,
            "clips": [],
            "effects": {"reverb": 0.1, "delay": 0, "distortion": 0}
        }
        
        song.setdefault("tracks", []).append(new_track)
        song["updatedAt"] = datetime.now().isoformat()
        
        return json.dumps(song, indent=2)
        
    except Exception as e:
        return f"Error creating track: {str(e)}"


@tool
def add_clip_to_track(song_json: str, track_id: str, start_time: float, duration: float, 
                     notes: List[str] = None, chord_name: str = "", volume: float = 0.8) -> str:
    """
    Add a clip to an existing track.
    
    Args:
        song_json: Current song structure as JSON string
        track_id: ID of the track to add clip to
        start_time: Start time in seconds
        duration: Duration in seconds
        notes: List of notes to play (e.g., ["C4", "E4", "G4"])
        chord_name: Name of the chord (e.g., "C_major")
        volume: Volume level (0.0 to 1.0)
    
    Returns:
        Updated song structure with new clip added
    """
    try:
        if isinstance(song_json, dict):
            song = song_json
        else:
            song = json.loads(song_json)
        
        # Find the target track
        target_track = None
        for track in song.get("tracks", []):
            if track.get("id") == track_id:
                target_track = track
                break
        
        if not target_track:
            return f"Error: Track with ID {track_id} not found"
        
        new_clip = {
            "id": f"clip-{uuid.uuid4().hex[:8]}",
            "trackId": track_id,
            "startTime": start_time,
            "duration": duration,
            "instrument": target_track.get("instrument", "unknown"),
            "volume": volume,
            "effects": {"reverb": 0.1, "delay": 0, "distortion": 0}
        }
        
        if notes:
            new_clip["notes"] = notes
        
        if chord_name:
            new_clip["chordName"] = chord_name
        
        target_track.setdefault("clips", []).append(new_clip)
        
        # Optimize clips to prevent overlaps
        target_track["clips"] = optimize_clips_simple(target_track["clips"])
        
        # Update song duration if necessary
        clip_end = start_time + duration
        song["duration"] = max(song.get("duration", 0), clip_end)
        song["updatedAt"] = datetime.now().isoformat()
        
        return json.dumps(song, indent=2)
        
    except Exception as e:
        return f"Error adding clip: {str(e)}"


@tool
def generate_chord_progression(key: str, style: str = "pop", num_bars: int = 4) -> str:
    """
    Generate a chord progression for a given key and style.
    
    Args:
        key: Musical key (e.g., "C", "Am", "F")
        style: Musical style (e.g., "pop", "jazz", "rock")
        num_bars: Number of bars for the progression
    
    Returns:
        JSON string with chord progression details
    """
    try:
        chords = get_chord_progression_for_key(key)
        
        # Extend or truncate based on num_bars
        if num_bars > len(chords):
            # Repeat progression
            full_progression = (chords * ((num_bars // len(chords)) + 1))[:num_bars]
        else:
            full_progression = chords[:num_bars]
        
        # Style-specific modifications
        if style.lower() == "jazz":
            # Add seventh chords
            full_progression = [chord.replace("_major", "maj7").replace("_minor", "m7") for chord in full_progression]
        elif style.lower() == "rock":
            # Use power chords
            full_progression = [chord.replace("_major", "5").replace("_minor", "m") for chord in full_progression]
        
        progression_info = {
            "key": key,
            "style": style,
            "num_bars": num_bars,
            "chords": full_progression,
            "roman_numerals": get_roman_numerals(key, full_progression),
            "suggested_tempo": get_suggested_tempo(style),
            "description": f"A {num_bars}-bar {style} progression in {key}"
        }
        
        return json.dumps(progression_info, indent=2)
        
    except Exception as e:
        return f"Error generating chord progression: {str(e)}"


@tool
def create_song_section(song_json: str, section_name: str, start_time: float, duration: float, 
                       chord_progression: List[str] = None, track_ids: List[str] = None) -> str:
    """
    Create a song section (verse, chorus, bridge, etc.) with specified characteristics.
    
    Args:
        song_json: Current song structure as JSON string
        section_name: Name of the section (e.g., "Verse 1", "Chorus")
        start_time: Start time in seconds
        duration: Duration in seconds
        chord_progression: List of chords for this section
        track_ids: List of track IDs to include in this section
    
    Returns:
        Updated song structure with new section added
    """
    try:
        if isinstance(song_json, dict):
            song = song_json
        else:
            song = json.loads(song_json)
        
        tracks = song.get("tracks", [])
        
        if not tracks:
            return "Error: No tracks available to create section"
        
        # Use all tracks if none specified
        if not track_ids:
            track_ids = [track["id"] for track in tracks]
        
        # Use chord progression from song key if none provided
        if not chord_progression:
            song_key = song.get("key", "C")
            chord_progression = get_chord_progression_for_key(song_key)
        
        # Calculate timing for chords
        bars_per_chord = duration / len(chord_progression) if chord_progression else duration
        
        # Add clips to specified tracks
        for track in tracks:
            if track["id"] not in track_ids:
                continue
            
            track_category = track.get("category", "")
            
            if track_category == "percussion":
                # Add rhythmic pattern
                clip = {
                    "id": f"clip-{uuid.uuid4().hex[:8]}",
                    "trackId": track["id"],
                    "startTime": start_time,
                    "duration": duration,
                    "instrument": track.get("instrument", "drums"),
                    "volume": 0.8,
                    "effects": {"reverb": 0.1, "delay": 0, "distortion": 0},
                    "notes": ["C1", "C1", "C1", "C1"],  # Basic kick pattern
                    "section": section_name
                }
                track.setdefault("clips", []).append(clip)
                
            elif track_category in ["keyboards", "strings"]:
                # Add chord progression
                for i, chord in enumerate(chord_progression):
                    clip_start = start_time + (i * bars_per_chord)
                    clip = {
                        "id": f"clip-{uuid.uuid4().hex[:8]}",
                        "trackId": track["id"],
                        "startTime": clip_start,
                        "duration": bars_per_chord,
                        "instrument": track.get("instrument", "piano"),
                        "volume": 0.7,
                        "effects": {"reverb": 0.2, "delay": 0, "distortion": 0},
                        "chordName": chord,
                        "section": section_name
                    }
                    track.setdefault("clips", []).append(clip)
            
            else:
                # Add basic clip for other instruments
                clip = {
                    "id": f"clip-{uuid.uuid4().hex[:8]}",
                    "trackId": track["id"],
                    "startTime": start_time,
                    "duration": duration,
                    "instrument": track.get("instrument", "unknown"),
                    "volume": 0.7,
                    "effects": {"reverb": 0.1, "delay": 0, "distortion": 0},
                    "section": section_name
                }
                track.setdefault("clips", []).append(clip)
            
            # Optimize clips
            track["clips"] = optimize_clips_simple(track["clips"])
        
        # Update song duration
        section_end = start_time + duration
        song["duration"] = max(song.get("duration", 0), section_end)
        song["updatedAt"] = datetime.now().isoformat()
        
        return json.dumps(song, indent=2)
        
    except Exception as e:
        return f"Error creating song section: {str(e)}"


@tool
def modify_song_structure(song_json: str, modifications: str) -> str:
    """
    Modify the song structure based on natural language instructions.
    
    Args:
        song_json: Current song structure as JSON string
        modifications: Natural language description of changes to make
    
    Returns:
        Updated song structure with modifications applied
    """
    try:
        if isinstance(song_json, dict):
            song = song_json
        else:
            song = json.loads(song_json)
        
        modifications_lower = modifications.lower()
        
        # Parse common modifications
        if "tempo" in modifications_lower:
            # Extract tempo
            import re
            tempo_match = re.search(r'(\d+)\s*bpm', modifications_lower)
            if tempo_match:
                new_tempo = int(tempo_match.group(1))
                song["tempo"] = new_tempo
        
        if "key" in modifications_lower:
            # Extract key
            keys = ["c", "d", "e", "f", "g", "a", "b", "am", "dm", "em", "fm", "gm"]
            for key in keys:
                if f" {key} " in modifications_lower or f" {key}m" in modifications_lower:
                    song["key"] = key.title()
                    break
        
        if "add intro" in modifications_lower or "create intro" in modifications_lower:
            # Add intro section
            intro_duration = 8  # 8 seconds default
            create_song_section(song, "Intro", 0, intro_duration)
        
        if "add outro" in modifications_lower or "create outro" in modifications_lower:
            # Add outro section
            current_duration = song.get("duration", 0)
            outro_duration = 8
            create_song_section(song, "Outro", current_duration, outro_duration)
        
        song["updatedAt"] = datetime.now().isoformat()
        
        return json.dumps(song, indent=2)
        
    except Exception as e:
        return f"Error modifying song structure: {str(e)}"
