"""
Music composition tools and utilities for loading instruments, samples, and voices.
"""

import json
import random
from typing import Dict, List, Any
from pathlib import Path

from .utils import safe_log_error

# Avoid importing VoiceService to prevent Flask context issues in background threads
VoiceService = None

# Musical note and pattern generation utilities
def generate_note_pattern(instrument_type: str, category: str, key: str = "C", style: str = "default", 
                         duration_beats: int = 8) -> List[str]:
    """
    Generate appropriate musical note patterns based on instrument type and style.
    
    Args:
        instrument_type: The specific instrument name
        category: The instrument category (keyboards, strings, percussion, etc.)
        key: Musical key (default "C")
        style: Musical style hint (rock, jazz, classical, etc.)
        duration_beats: Number of beats to generate patterns for
        
    Returns:
        List of note names appropriate for the instrument
    """
    try:
        # Parse key to get root note and mode
        key_parts = key.split()
        root_note = key_parts[0] if key_parts else "C"
        mode = key_parts[1].lower() if len(key_parts) > 1 else "major"
        
        # Define scale patterns
        if mode in ["major", "maj"]:
            scale_intervals = [0, 2, 4, 5, 7, 9, 11]  # Major scale
        elif mode in ["minor", "min"]:
            scale_intervals = [0, 2, 3, 5, 7, 8, 10]  # Natural minor scale
        else:
            scale_intervals = [0, 2, 4, 5, 7, 9, 11]  # Default to major
        
        # Map note names to semitones from C
        note_to_semitone = {
            "C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4,
            "F": 5, "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9,
            "A#": 10, "Bb": 10, "B": 11
        }
        
        # Map semitones back to note names (prefer sharps for simplicity)
        semitone_to_note = {
            0: "C", 1: "C#", 2: "D", 3: "D#", 4: "E", 5: "F",
            6: "F#", 7: "G", 8: "G#", 9: "A", 10: "A#", 11: "B"
        }
        
        root_semitone = note_to_semitone.get(root_note, 0)
        
        # Generate scale notes in the key
        scale_notes = []
        for interval in scale_intervals:
            note_semitone = (root_semitone + interval) % 12
            scale_notes.append(semitone_to_note[note_semitone])
        
        # Generate patterns based on instrument category and type
        if category == "percussion" or "drum" in instrument_type.lower():
            return generate_drum_pattern(duration_beats, style)
        
        elif category == "keyboards" or "piano" in instrument_type.lower():
            return generate_piano_pattern(scale_notes, duration_beats, style)
        
        elif category == "strings":
            if "bass" in instrument_type.lower():
                return generate_bass_pattern(scale_notes, duration_beats, style)
            else:
                return generate_string_pattern(scale_notes, duration_beats, style)
        
        elif category in ["woodwinds", "brass"]:
            return generate_wind_pattern(scale_notes, duration_beats, style)
        
        elif category == "synth":
            return generate_synth_pattern(scale_notes, duration_beats, style)
        
        else:
            # Default melodic pattern
            return generate_melodic_pattern(scale_notes, duration_beats, style)
        
    except Exception as e:
        print(f"Error generating note pattern: {e}")
        # Fallback to simple pattern
        return ["C4", "E4", "G4", "C5"]

def generate_drum_pattern(duration_beats: int, style: str) -> List[str]:
    """Generate drum patterns appropriate for the style."""
    patterns = {
        "rock": ["C4", "C4", "E4", "C4", "C4", "E4", "C4", "E4"],  # Kick-Snare pattern
        "jazz": ["C4", "F#4", "C4", "F#4", "E4", "F#4", "C4", "F#4"],  # Jazz pattern
        "electronic": ["C4", "C4", "E4", "E4", "C4", "E4", "C4", "E4"],
        "pop": ["C4", "C4", "E4", "C4", "C4", "E4", "C4", "E4"],
        "default": ["C4", "C4", "E4", "C4", "C4", "E4", "C4", "E4"]
    }
    
    base_pattern = patterns.get(style.lower(), patterns["default"])
    # Repeat pattern to fill duration
    repeats = max(1, duration_beats // len(base_pattern))
    return (base_pattern * repeats)[:duration_beats]

def generate_bass_pattern(scale_notes: List[str], duration_beats: int, style: str) -> List[str]:
    """Generate bass patterns using low octaves."""
    # Use root and fifth primarily, in octave 2-3
    root = f"{scale_notes[0]}2"
    fifth = f"{scale_notes[4]}2" if len(scale_notes) > 4 else f"{scale_notes[0]}2"
    third = f"{scale_notes[2]}2" if len(scale_notes) > 2 else f"{scale_notes[0]}2"
    
    patterns = {
        "rock": [root, root, fifth, root],
        "jazz": [root, third, fifth, root],
        "electronic": [root, root, root, fifth],
        "pop": [root, fifth, root, fifth],
        "default": [root, fifth, third, root]
    }
    
    base_pattern = patterns.get(style.lower(), patterns["default"])
    repeats = max(1, duration_beats // len(base_pattern))
    return (base_pattern * repeats)[:duration_beats]

def generate_piano_pattern(scale_notes: List[str], duration_beats: int, style: str) -> List[str]:
    """Generate piano chord progressions and melodies."""
    # Create chord progressions in octave 4-5
    notes_oct4 = [f"{note}4" for note in scale_notes]
    notes_oct5 = [f"{note}5" for note in scale_notes]
    
    patterns = {
        "classical": notes_oct4 + notes_oct5[:3],  # Arpeggio-like
        "jazz": [f"{scale_notes[0]}4", f"{scale_notes[2]}4", f"{scale_notes[4]}4", f"{scale_notes[6]}5"],
        "pop": [f"{scale_notes[0]}4", f"{scale_notes[4]}4", f"{scale_notes[5]}4", f"{scale_notes[0]}5"],
        "rock": [f"{scale_notes[0]}4", f"{scale_notes[2]}4", f"{scale_notes[4]}4", f"{scale_notes[0]}5"],
        "default": [f"{scale_notes[0]}4", f"{scale_notes[2]}4", f"{scale_notes[4]}4", f"{scale_notes[0]}5"]
    }
    
    base_pattern = patterns.get(style.lower(), patterns["default"])
    repeats = max(1, duration_beats // len(base_pattern))
    return (base_pattern * repeats)[:duration_beats]

def generate_wind_pattern(scale_notes: List[str], duration_beats: int, style: str) -> List[str]:
    """Generate melodic patterns for wind instruments."""
    # Wind instruments typically play in octave 5-6
    notes = [f"{note}5" for note in scale_notes]
    
    # Create melodic movement
    if style.lower() in ["classical", "orchestral"]:
        # More stepwise motion
        pattern = [notes[0], notes[1], notes[2], notes[3], notes[4], notes[3], notes[2], notes[0]]
    elif style.lower() in ["jazz"]:
        # More chromatic and complex
        pattern = [notes[0], notes[2], notes[4], notes[6], notes[5], notes[3], notes[1], notes[0]]
    else:
        # Default melodic pattern
        pattern = [notes[0], notes[2], notes[4], notes[2], notes[1], notes[3], notes[0], notes[4]]
    
    repeats = max(1, duration_beats // len(pattern))
    return (pattern * repeats)[:duration_beats]

def generate_string_pattern(scale_notes: List[str], duration_beats: int, style: str) -> List[str]:
    """Generate string section patterns (excluding bass)."""
    # Strings often play in mid-to-high range
    notes_oct4 = [f"{note}4" for note in scale_notes]
    notes_oct5 = [f"{note}5" for note in scale_notes]
    
    patterns = {
        "orchestral": notes_oct4[:4] + notes_oct5[:4],  # Harmonic layers
        "folk": [f"{scale_notes[0]}4", f"{scale_notes[2]}4", f"{scale_notes[4]}4", f"{scale_notes[0]}5"],
        "rock": [f"{scale_notes[0]}4", f"{scale_notes[4]}4", f"{scale_notes[0]}5", f"{scale_notes[4]}4"],
        "default": [f"{scale_notes[0]}4", f"{scale_notes[2]}4", f"{scale_notes[4]}4", f"{scale_notes[2]}5"]
    }
    
    base_pattern = patterns.get(style.lower(), patterns["default"])
    repeats = max(1, duration_beats // len(base_pattern))
    return (base_pattern * repeats)[:duration_beats]

def generate_synth_pattern(scale_notes: List[str], duration_beats: int, style: str) -> List[str]:
    """Generate synthesizer patterns."""
    # Synths can cover wide range
    notes_oct3 = [f"{note}3" for note in scale_notes]
    notes_oct4 = [f"{note}4" for note in scale_notes]
    notes_oct5 = [f"{note}5" for note in scale_notes]
    
    patterns = {
        "electronic": notes_oct4 + [notes_oct5[0], notes_oct3[0]],
        "ambient": [notes_oct3[0], notes_oct4[2], notes_oct5[0], notes_oct4[4]],
        "lead": [notes_oct5[0], notes_oct5[2], notes_oct5[4], notes_oct5[7%len(notes_oct5)]],
        "default": [notes_oct4[0], notes_oct4[2], notes_oct4[4], notes_oct5[0]]
    }
    
    base_pattern = patterns.get(style.lower(), patterns["default"])
    repeats = max(1, duration_beats // len(base_pattern))
    return (base_pattern * repeats)[:duration_beats]

def generate_melodic_pattern(scale_notes: List[str], duration_beats: int, style: str) -> List[str]:
    """Generate general melodic patterns."""
    notes_oct4 = [f"{note}4" for note in scale_notes]
    
    # Create interesting melodic movement
    pattern = [
        notes_oct4[0],  # Root
        notes_oct4[2],  # Third  
        notes_oct4[4],  # Fifth
        notes_oct4[1],  # Second
        notes_oct4[3],  # Fourth
        notes_oct4[2],  # Third
        notes_oct4[0],  # Root
        notes_oct4[4]   # Fifth
    ]
    
    repeats = max(1, duration_beats // len(pattern))
    return (pattern * repeats)[:duration_beats]

# Flask-context-free versions of instrument scanning functions
def get_all_available_instruments_no_flask():
    """
    Get all available instruments from all categories in the sample library
    Flask-context-free version for use in background threads
    """
    try:
        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent.parent.parent.parent
        instruments_root = project_root / 'frontend' / 'public' / 'instruments'
        
        if not instruments_root.exists():
            print(f"Warning: Instruments directory not found: {instruments_root}")
            return []
        
        all_instruments = []
        for category_dir in instruments_root.iterdir():
            if category_dir.is_dir():
                category = category_dir.name
                instruments = get_available_sample_instruments_no_flask(category)
                for instrument in instruments:
                    all_instruments.append({
                        'name': instrument,
                        'category': category,
                        'full_name': f"{category}/{instrument}",
                        'display_name': instrument.replace('_', ' ').title()
                    })
        
        print(f"Info: Found {len(all_instruments)} instruments across all categories")
        return all_instruments
    
    except Exception as e:
        print(f"Error getting all available instruments: {str(e)}")
        return []

def get_available_sample_instruments_no_flask(category):
    """
    Scan the public/instruments/[category] directory to find available instruments
    Flask-context-free version for use in background threads
    """
    try:
        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent.parent.parent.parent
        instruments_dir = project_root / 'frontend' / 'public' / 'instruments' / category
        print(f"Info: Looking for instruments in: {instruments_dir}")
        if not instruments_dir.exists():
            print(f"Warning: Samples directory not found: {instruments_dir}")
            return []
        instruments = []
        for item in instruments_dir.iterdir():
            if item.is_dir():
                instruments.append(item.name)
        print(f"Info: Found instruments: {instruments}")
        return instruments
    except Exception as e:
        print(f"Error scanning sample instruments: {str(e)}")
        return []

def get_instrument_chords_no_flask(category, instrument):
    """
    Get available chords/samples for a specific instrument in a category
    Flask-context-free version for use in background threads
    """
    try:
        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent.parent.parent.parent
        instruments_dir = project_root / 'frontend' / 'public' / 'instruments' / category / instrument
        print(f"Info: Looking for {instrument} chords in: {instruments_dir}")
        
        if not instruments_dir.exists():
            print(f"Warning: Instrument directory not found: {instruments_dir}")
            return []
        
        chords = []

        # Check for format directories directly in the instrument folder (newer structure)
        format_dirs = ['mp3', 'wav', 'midi']
        for format_name in format_dirs:
            format_dir = instruments_dir / format_name
            if format_dir.exists():
                for audio_file in format_dir.iterdir():
                    if audio_file.is_file() and audio_file.suffix.lower() in ['.mp3', '.wav']:
                        # Extract chord name from filename (e.g., "C_major.mp3" -> "C_major")
                        chord_name = audio_file.stem
                        if chord_name not in chords:
                            chords.append(chord_name)

        # Also check for duration subdirectories (older structure)
        for duration_dir in instruments_dir.iterdir():
            if duration_dir.is_dir() and duration_dir.name not in format_dirs:
                # Check multiple format directories in order of preference
                for format_name in format_dirs:
                    format_dir = duration_dir / format_name
                    if format_dir.exists():
                        for audio_file in format_dir.iterdir():
                            if audio_file.is_file() and audio_file.suffix.lower() in ['.mp3', '.wav']:
                                # Extract chord name from filename (e.g., "C_major.mp3" -> "C_major")
                                chord_name = audio_file.stem
                                if chord_name not in chords:
                                    chords.append(chord_name)

        print(f"Info: Found {len(chords)} chords for {instrument}")
        return chords

    except Exception as e:
        print(f"Error getting chords for {instrument} in {category}: {str(e)}")
        return []


class MusicCompositionTools:
    """Tools for music composition and song structure manipulation"""
    
    def __init__(self):
        # Initialize as None - load lazily when first accessed
        self._available_instruments = None
        self._available_samples = None
        self._available_voices = None
    
    @property
    def available_instruments(self) -> Dict[str, List[str]]:
        """Lazily load available instruments"""
        if self._available_instruments is None:
            self._available_instruments = self._load_available_instruments()
        return self._available_instruments
    
    @property
    def available_samples(self) -> Dict[str, Dict[str, List[str]]]:
        """Lazily load available samples"""
        if self._available_samples is None:
            self._available_samples = self._load_available_samples()
        return self._available_samples
    
    @property
    def available_voices(self) -> Dict[str, Dict[str, Any]]:
        """Lazily load available voices"""
        if self._available_voices is None:
            self._available_voices = self._load_available_voices()
        return self._available_voices
    
    def _load_available_instruments(self) -> Dict[str, List[str]]:
        """Load available instruments from sample library using standardized functions"""
        try:
            all_instruments = get_all_available_instruments_no_flask()
            
            # Group instruments by category
            instruments = {}
            for instrument in all_instruments:
                category = instrument['category']
                if category not in instruments:
                    instruments[category] = []
                # Use the actual file system name (with underscores) not display name
                # This ensures AI generates JSON that matches actual file paths
                instruments[category].append(instrument['name'])
            
            # Sort instruments alphabetically within each category
            for category in instruments:
                instruments[category].sort()
            
            print(f"✅ Loaded {sum(len(insts) for insts in instruments.values())} instruments across {len(instruments)} categories")
            return instruments
            
        except Exception as e:
            safe_log_error(f"Error loading instruments: {e}")
            # Fallback to hardcoded instruments (use file system names)
            return {
                'strings': ['Guitar', 'Bass', 'Violin', 'Cello'],
                'keyboards': ['Grand_Piano', 'Piano', 'Synth', 'Organ'],  # Use actual dir names
                'percussion': ['Drums', 'Bongos', 'Cymbals'],
                'brass': ['Trumpet', 'Trombone', 'Horn'],
                'woodwinds': ['Flute', 'Clarinet', 'Saxophone']
            }
    
    def _load_available_samples(self) -> Dict[str, Dict[str, List[str]]]:
        """Load available samples from the sample library using standardized functions"""
        try:
            all_instruments = get_all_available_instruments_no_flask()
            
            samples = {}
            for instrument in all_instruments:
                category = instrument['category']
                instrument_name = instrument['name']  # Use file system name
                
                if category not in samples:
                    samples[category] = {}
                
                # Get chords/samples for this instrument
                chords = get_instrument_chords_no_flask(category, instrument_name)
                samples[category][instrument_name] = chords  # Use file system name as key
            
            print(f"✅ Loaded samples for {len(all_instruments)} instruments")
            return samples
            
        except Exception as e:
            safe_log_error(f"Error loading samples: {e}")
            return {}
    
    def _load_available_voices(self) -> Dict[str, Dict[str, Any]]:
        """Load available voices from voice service"""
        try:
            if VoiceService is None:
                safe_log_error("VoiceService not available - using default voices")
                # Provide default voices when VoiceService is not available
                return {
                    "soprano01": {
                        "name": "Soprano Voice 1",
                        "range": "soprano",
                        "gender": "female",
                        "language": "en",
                        "min_note": "C4",
                        "max_note": "C6"
                    },
                    "alto01": {
                        "name": "Alto Voice 1", 
                        "range": "alto",
                        "gender": "female",
                        "language": "en",
                        "min_note": "G3",
                        "max_note": "G5"
                    },
                    "tenor01": {
                        "name": "Tenor Voice 1",
                        "range": "tenor", 
                        "gender": "male",
                        "language": "en",
                        "min_note": "C3",
                        "max_note": "C5"
                    },
                    "bass01": {
                        "name": "Bass Voice 1",
                        "range": "bass",
                        "gender": "male", 
                        "language": "en",
                        "min_note": "E2",
                        "max_note": "E4"
                    }
                }
            
            voice_service = VoiceService()
            voices = voice_service.get_available_voices()
            
            if not voices:
                safe_log_error("No voices found in voice service")
                return {}
            
            return voices
            
        except Exception as e:
            safe_log_error(f"Error loading voices: {e}")
            return {}
    
    def format_instruments_for_prompt(self, instruments_dict: Dict[str, List[str]]) -> str:
        """Format instruments dictionary for use in AI prompts"""
        formatted = []
        for category, instruments in instruments_dict.items():
            if instruments:
                formatted.append(f"{category.title()}: {', '.join(instruments)}")
        
        result = "\n".join(formatted) if formatted else "No instruments available"
        result += "\n\nIMPORTANT: Use the EXACT instrument names as listed above (including underscores like 'Grand_Piano'). These names must match the file system directories exactly."
        return result
    
    def format_voices_for_prompt(self, voices_dict: Dict[str, Dict[str, Any]]) -> str:
        """Format voices dictionary for use in AI prompts"""
        formatted = []
        
        # Group voices by range/type
        ranges = {}
        for voice_id, voice_info in voices_dict.items():
            voice_range = voice_info.get('range', 'unknown')
            if voice_range not in ranges:
                ranges[voice_range] = []
            ranges[voice_range].append(f"{voice_id} ({voice_info.get('name', voice_id)})")
        
        for range_name, voices in ranges.items():
            formatted.append(f"{range_name.title()}: {', '.join(voices)}")
        
        return "\n".join(formatted) if formatted else "No voices available"
    
    def format_samples_for_prompt(self, samples: Dict[str, Dict[str, List[str]]] = None) -> str:
        """Format samples for LLM prompts, including user-uploaded sample metadata"""
        
        # Handle different input types - could be default samples or user samples
        if samples is None:
            samples = self.available_samples
        
        formatted = []
        
        # Check if this looks like user samples (list of dicts) vs default samples (dict of lists)
        # User samples format: {category: [sample_objects]} where each sample is a dict
        # Default samples format: {category: {instrument: [sample_names]}} where sample_names are strings
        
        is_user_samples = False
        if samples:
            try:
                # Check the structure more carefully
                first_value = next(iter(samples.values()), None)
                if isinstance(first_value, list):
                    # It's a list - check what's in the list
                    if first_value and isinstance(first_value[0], dict):
                        # List of dicts = user samples
                        is_user_samples = True
                    else:
                        # List of strings = default samples (but this structure is unusual)
                        is_user_samples = False
                elif isinstance(first_value, dict):
                    # It's a dict - check if it's nested structure
                    nested_first_value = next(iter(first_value.values()), None) if first_value else None
                    if isinstance(nested_first_value, list):
                        # Nested dict structure = default samples: {category: {instrument: [samples]}}
                        is_user_samples = False
                    else:
                        # Single level dict = user samples (unusual but possible)
                        is_user_samples = True
                else:
                    # Neither list nor dict - treat as default
                    is_user_samples = False
            except (StopIteration, IndexError, TypeError):
                # If we can't determine structure, assume default
                is_user_samples = False
        
        if is_user_samples:
            # This appears to be user samples format: {category: [sample_objects]}
            if samples:
                formatted.append("User-Uploaded Samples:")
                
                for category, sample_list in samples.items():
                    if sample_list:
                        formatted.append(f"\n{category.title()} Category:")
                        
                        for sample in sample_list:
                            sample_info = f"  • {sample.get('name', 'Unnamed sample')}"
                            
                            # Add metadata details
                            details = []
                            if sample.get('bpm'):
                                details.append(f"{sample['bpm']} BPM")
                            if sample.get('key'):
                                details.append(f"Key: {sample['key']}")
                            if sample.get('duration'):
                                details.append(f"{sample['duration']:.1f}s")
                            if sample.get('tags'):
                                tags = [tag for tag in sample['tags'] if tag not in [category, sample.get('name', '').lower()]]
                                if tags:
                                    details.append(f"Tags: {', '.join(tags[:3])}")  # Show first 3 tags
                            
                            if details:
                                sample_info += f" ({'; '.join(details)})"
                            
                            formatted.append(sample_info)
            else:
                formatted.append("No user samples available")
            
            return "\n".join(formatted)
        
        else:
            # This is default samples format: {category: {instrument: [samples]}}
            # BUT we need to handle cases where detection was wrong and we actually have user samples
            for category, sample_groups in samples.items():
                formatted.append(f"{category.title()} Samples:")
                
                # Check if sample_groups is actually a list (user samples mistakenly in this branch)
                if isinstance(sample_groups, list):
                    # This is actually user samples format - handle it appropriately
                    for sample in sample_groups:
                        if isinstance(sample, dict):
                            sample_name = sample.get('name', sample.get('filename', 'Unnamed sample'))
                            sample_info = f"  • {sample_name}"
                            
                            # Add some basic metadata
                            details = []
                            if sample.get('bpm'):
                                details.append(f"{sample['bpm']} BPM")
                            if sample.get('duration'):
                                details.append(f"{sample['duration']:.1f}s")
                            
                            if details:
                                sample_info += f" ({'; '.join(details)})"
                            
                            formatted.append(sample_info)
                        else:
                            formatted.append(f"  • {str(sample)}")
                            
                elif isinstance(sample_groups, dict):
                    # This is the expected default samples format
                    for group_name, sample_list in sample_groups.items():
                        # Ensure all items in sample_list are strings
                        if isinstance(sample_list, list):
                            # Convert any non-string items to strings safely
                            string_samples = []
                            for item in sample_list:
                                if isinstance(item, str):
                                    string_samples.append(item)
                                elif isinstance(item, dict):
                                    # Extract name from dict if available
                                    name = item.get('name', item.get('filename', str(item)))
                                    string_samples.append(name)
                                else:
                                    string_samples.append(str(item))
                            formatted.append(f"  {group_name}: {', '.join(string_samples)}")
                        else:
                            # If sample_list is not a list, convert it to string
                            formatted.append(f"  {group_name}: {str(sample_list)}")
                else:
                    # Unknown format, just convert to string
                    formatted.append(f"  {str(sample_groups)}")
            
            # Add user-uploaded samples with rich metadata
            try:
                from app.api.sample_routes import get_user_samples_for_agents
                user_samples = get_user_samples_for_agents()
                if user_samples:
                    formatted.append("\nUser-Uploaded Samples:")
                    
                    for category, sample_list in user_samples.items():
                        if sample_list:
                            formatted.append(f"\n{category.title()} Category:")
                            
                            for sample in sample_list:
                                sample_info = f"  • {sample['name']}"
                                
                                # Add metadata details
                                details = []
                                if sample.get('bpm'):
                                    details.append(f"{sample['bpm']} BPM")
                                if sample.get('key'):
                                    details.append(f"Key: {sample['key']}")
                                if sample.get('duration'):
                                    details.append(f"{sample['duration']:.1f}s")
                                if sample.get('tags'):
                                    tags = [tag for tag in sample['tags'] if tag not in [category, sample['name'].lower()]]
                                    if tags:
                                        details.append(f"Tags: {', '.join(tags[:3])}")  # Show first 3 tags
                                
                                if details:
                                    sample_info += f" ({'; '.join(details)})"
                                
                                formatted.append(sample_info)
            
            except Exception as e:
                # If user samples can't be loaded, continue with defaults only
                formatted.append(f"\nNote: User samples temporarily unavailable ({str(e)})")
            
            return "\n".join(formatted)
    
    def get_all_available_samples(self) -> Dict[str, Any]:
        """Get combined samples data (default + user samples) for agent context"""
        try:
            from app.api.sample_routes import get_user_samples_for_agents
            
            # Start with default samples
            all_samples = {
                'default_samples': self.available_samples,
                'user_samples': get_user_samples_for_agents(),
                'combined_count': len(self._flatten_samples(self.available_samples))
            }
            
            # Add user sample count
            user_samples = get_user_samples_for_agents()
            user_count = sum(len(samples) for samples in user_samples.values()) if user_samples else 0
            all_samples['user_count'] = user_count
            all_samples['total_count'] = all_samples['combined_count'] + user_count
            
            return all_samples
            
        except Exception as e:
            # Fallback to defaults only
            return {
                'default_samples': self.available_samples,
                'user_samples': {},
                'combined_count': len(self._flatten_samples(self.available_samples)),
                'user_count': 0,
                'total_count': len(self._flatten_samples(self.available_samples)),
                'error': str(e)
            }
    
    def _flatten_samples(self, samples: Dict[str, Dict[str, List[str]]]) -> List[str]:
        """Flatten sample structure to count total samples"""
        flattened = []
        for category_samples in samples.values():
            for sample_list in category_samples.values():
                flattened.extend(sample_list)
        return flattened

    def normalize_instrument_name(self, instrument_name: str, category: str = None) -> str:
        """
        Normalize an instrument name to match file system conventions.
        Converts display names (with spaces) to file system names (with underscores).
        Also fixes common category mismatches.
        """
        if not instrument_name:
            return instrument_name
            
        # First try exact match (in case AI used correct name)
        all_instruments = get_all_available_instruments_no_flask()
        for instrument in all_instruments:
            if instrument['name'] == instrument_name:
                return instrument_name
        
        # Try matching by display name (case insensitive)
        normalized_input = instrument_name.lower().strip()
        for instrument in all_instruments:
            if instrument['display_name'].lower() == normalized_input:
                return instrument['name']
        
        # Try replacing spaces with underscores and matching
        underscore_name = instrument_name.replace(' ', '_')
        for instrument in all_instruments:
            if instrument['name'].lower() == underscore_name.lower():
                return instrument['name']
        
        # Fallback: just replace spaces with underscores
        return instrument_name.replace(' ', '_')
    
    def validate_instrument_category(self, instrument_name: str, suggested_category: str) -> str:
        """
        Validate and correct instrument category based on actual file structure.
        Returns the correct category for the instrument.
        """
        all_instruments = get_all_available_instruments_no_flask()
        
        # Find instrument in the actual file structure
        for instrument in all_instruments:
            if (instrument['name'].lower() == instrument_name.lower() or 
                instrument['display_name'].lower() == instrument_name.lower()):
                return instrument['category']
        
        # Common category corrections
        category_fixes = {
            'keys': 'keyboards',  # Fix common mistake
            'piano': 'keyboards',
            'drums': 'percussion',
            'guitar': 'strings'
        }
        
        return category_fixes.get(suggested_category.lower(), suggested_category)

    def generate_intelligent_notes(self, instrument_name: str, category: str, 
                                  key: str = "C major", style_tags: List[str] = None, 
                                  duration_beats: int = 8) -> List[str]:
        """
        Generate intelligent musical note patterns for instruments.
        
        Args:
            instrument_name: The specific instrument name
            category: The instrument category
            key: Musical key (e.g., "C major", "A minor")
            style_tags: List of style tags for context
            duration_beats: Number of beats to generate patterns for
            
        Returns:
            List of note names appropriate for the instrument
        """
        try:
            # Determine primary style from tags
            style = "default"
            if style_tags:
                style_priority = ["rock", "jazz", "classical", "pop", "electronic", "ambient"]
                for s in style_priority:
                    if any(s in tag.lower() for tag in style_tags):
                        style = s
                        break
            
            # Use the global pattern generation function
            return generate_note_pattern(
                instrument_type=instrument_name,
                category=category,
                key=key,
                style=style,
                duration_beats=duration_beats
            )
            
        except Exception as e:
            safe_log_error(f"Error generating intelligent notes: {e}")
            # Enhanced fallback based on category
            if category == "percussion" or "drum" in instrument_name.lower():
                return ["C4", "C4", "E4", "C4", "C4", "E4", "C4", "E4"]
            elif "bass" in instrument_name.lower():
                return ["C2", "G2", "F2", "G2"]
            elif category == "keyboards":
                return ["C4", "E4", "G4", "C5", "F4", "A4", "C5", "G4"]
            elif category in ["woodwinds", "brass"]:
                return ["C5", "D5", "E5", "F5", "G5", "E5", "C5", "G4"]
            elif category == "strings":
                return ["G4", "C5", "E5", "G5", "C5", "E5", "G4", "C5"]
            else:
                return ["C4", "E4", "G4", "C5"]

    def generate_extended_vocal_clip(self, clip_id: str, track_id: str, section_id: str, 
                                   start_time: float, duration: float, voice_id: str,
                                   lyrics_text: str, notes: List[str], durations: List[float],
                                   tags: List[str] = None) -> Dict[str, Any]:
        """
        Generate an extended vocal clip with syllable breakdown and phonemes.
        
        Args:
            clip_id: Unique clip identifier
            track_id: Parent track identifier
            section_id: Section identifier for structure reference
            start_time: Start time in seconds
            duration: Duration in seconds
            voice_id: Voice identifier (e.g., "soprano01")
            lyrics_text: The lyrics text to be sung
            notes: List of note names
            durations: List of durations for each note
            tags: Optional tags like ["lead", "harmony", "choir", "adlib"]
            
        Returns:
            Extended vocal clip dictionary with syllables and phonemes
        """
        try:
            # Generate syllable breakdown
            syllables = self._generate_syllable_breakdown(lyrics_text, notes, durations)
            
            # Generate phonemes
            phonemes = self._generate_phonemes(lyrics_text)
            
            # Create the extended vocal clip structure
            clip = {
                "id": clip_id,
                "trackId": track_id,
                "type": "lyrics",
                "sectionId": section_id,
                "startTime": start_time,
                "duration": duration,
                "voiceId": voice_id,
                "lyrics": [
                    {
                        "text": lyrics_text,
                        "start": 0.0,
                        "notes": notes,
                        "durations": durations,
                        "syllables": syllables,
                        "phonemes": phonemes
                    }
                ],
                "tags": tags or ["lead"]
            }
            
            return clip
            
        except Exception as e:
            safe_log_error(f"Error generating extended vocal clip: {e}")
            # Fallback to basic structure
            return {
                "id": clip_id,
                "trackId": track_id,
                "type": "lyrics",
                "sectionId": section_id,
                "startTime": start_time,
                "duration": duration,
                "voiceId": voice_id,
                "lyrics": [
                    {
                        "text": lyrics_text,
                        "start": 0.0,
                        "notes": notes,
                        "durations": durations
                    }
                ],
                "tags": tags or ["lead"]
            }

    def generate_song_structure(self, sections: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate song structure with sections for better visualization.
        
        Args:
            sections: List of section dictionaries with id, type, label, startTime, endTime, index
            
        Returns:
            Song structure dictionary with sections
        """
        try:
            structure = {
                "sections": []
            }
            
            for section in sections:
                section_dict = {
                    "id": section.get("id", f"sec-{section.get('type', 'unknown')}"),
                    "type": section.get("type", "unknown"),
                    "label": section.get("label", section.get("type", "Unknown").title()),
                    "startTime": section.get("startTime", 0.0),
                    "endTime": section.get("endTime", 8.0),
                    "index": section.get("index", 1)
                }
                structure["sections"].append(section_dict)
            
            return structure
            
        except Exception as e:
            safe_log_error(f"Error generating song structure: {e}")
            return {"sections": []}

    def generate_section_spans(self, section_spans: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Generate section spans for clips that cross section boundaries.
        
        Args:
            section_spans: List of section span dictionaries
            
        Returns:
            List of formatted section spans
        """
        try:
            spans = []
            for span in section_spans:
                span_dict = {
                    "sectionId": span.get("sectionId", ""),
                    "startOffset": span.get("startOffset", 0.0),
                    "duration": span.get("duration", 1.0)
                }
                spans.append(span_dict)
            
            return spans
            
        except Exception as e:
            safe_log_error(f"Error generating section spans: {e}")
            return []

    def _generate_syllable_breakdown(self, lyrics_text: str, notes: List[str], 
                                   durations: List[float]) -> List[Dict[str, Any]]:
        """
        Generate syllable breakdown with note mapping.
        
        Args:
            lyrics_text: The lyrics text
            notes: List of note names
            durations: List of durations
            
        Returns:
            List of syllable dictionaries with note mapping
        """
        try:
            words = lyrics_text.split()
            syllables = []
            note_index = 0
            
            for word in words:
                # Simple syllable detection (can be enhanced with proper phonetic libraries)
                word_syllables = self._split_into_syllables(word)
                
                for i, syllable in enumerate(word_syllables):
                    is_melisma = len(word_syllables) > 1 and i == len(word_syllables) - 1
                    
                    # Map syllable to notes
                    note_indices = []
                    if note_index < len(notes):
                        if is_melisma and note_index + 1 < len(notes):
                            # For melisma, use multiple notes
                            note_indices = [note_index, note_index + 1]
                            note_index += 2
                        else:
                            note_indices = [note_index]
                            note_index += 1
                    
                    duration = durations[note_indices[0]] if note_indices and note_indices[0] < len(durations) else 0.3
                    
                    syllable_dict = {
                        "t": syllable,
                        "noteIdx": note_indices,
                        "dur": duration
                    }
                    
                    if is_melisma:
                        syllable_dict["melisma"] = True
                    
                    syllables.append(syllable_dict)
            
            return syllables
            
        except Exception as e:
            safe_log_error(f"Error generating syllable breakdown: {e}")
            return [{"t": lyrics_text, "noteIdx": [0], "dur": 1.0}]

    def _split_into_syllables(self, word: str) -> List[str]:
        """
        Simple syllable splitting (basic implementation).
        For production, consider using a proper phonetic library like pyphen or syllables.
        
        Args:
            word: Word to split into syllables
            
        Returns:
            List of syllables
        """
        try:
            # Basic vowel-based syllable detection
            vowels = "aeiouyAEIOUY"
            syllables = []
            current_syllable = ""
            
            for i, char in enumerate(word):
                current_syllable += char
                
                if char in vowels:
                    # Check if this is the end of a syllable
                    if i + 1 < len(word) and word[i + 1] not in vowels:
                        # Add consonant to current syllable if it's not the last character
                        if i + 2 < len(word):
                            current_syllable += word[i + 1]
                            syllables.append(current_syllable)
                            current_syllable = ""
                            continue
                    elif i == len(word) - 1:
                        # End of word
                        syllables.append(current_syllable)
                        current_syllable = ""
            
            if current_syllable:
                if syllables:
                    syllables[-1] += current_syllable
                else:
                    syllables.append(current_syllable)
            
            return syllables if syllables else [word]
            
        except Exception as e:
            safe_log_error(f"Error splitting syllables for word '{word}': {e}")
            return [word]

    def _generate_phonemes(self, lyrics_text: str) -> List[str]:
        """
        Generate IPA phonemes for TTS/singing engines.
        This is a basic implementation - for production use, consider proper IPA libraries.
        
        Args:
            lyrics_text: The lyrics text
            
        Returns:
            List of IPA phoneme strings
        """
        try:
            # Basic English phoneme mapping (simplified)
            phoneme_map = {
                # Vowels
                'a': 'ɑ', 'e': 'ɛ', 'i': 'ɪ', 'o': 'ɔ', 'u': 'ʊ',
                'ai': 'aɪ', 'ay': 'eɪ', 'ey': 'eɪ', 'oy': 'ɔɪ', 'ow': 'aʊ',
                'ee': 'i', 'oo': 'u', 'ou': 'aʊ',
                
                # Consonants
                'th': 'θ', 'sh': 'ʃ', 'ch': 'tʃ', 'ng': 'ŋ', 'ph': 'f',
                'b': 'b', 'c': 'k', 'd': 'd', 'f': 'f', 'g': 'g',
                'h': 'h', 'j': 'dʒ', 'k': 'k', 'l': 'l', 'm': 'm',
                'n': 'n', 'p': 'p', 'r': 'r', 's': 's', 't': 't',
                'v': 'v', 'w': 'w', 'x': 'ks', 'y': 'j', 'z': 'z'
            }
            
            words = lyrics_text.lower().split()
            phonemes = []
            
            for word in words:
                word_phonemes = []
                i = 0
                while i < len(word):
                    # Check for two-character combinations first
                    if i + 1 < len(word):
                        two_char = word[i:i+2]
                        if two_char in phoneme_map:
                            word_phonemes.append(phoneme_map[two_char])
                            i += 2
                            continue
                    
                    # Single character
                    char = word[i]
                    if char in phoneme_map:
                        word_phonemes.append(phoneme_map[char])
                    else:
                        word_phonemes.append(char)  # Keep unknown characters as-is
                    i += 1
                
                phonemes.extend(word_phonemes)
                # Add word boundary marker
                if word != words[-1]:
                    phonemes.append(' ')
            
            return phonemes
            
        except Exception as e:
            safe_log_error(f"Error generating phonemes: {e}")
            # Fallback: return characters as basic phonemes
            return list(lyrics_text.lower().replace(' ', ' '))

    def create_complete_vocal_track(self, track_id: str, voice_id: str, 
                                  clips_data: List[Dict[str, Any]], 
                                  structure: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a complete vocal track with extended clip structure and song sections.
        
        Args:
            track_id: Track identifier
            voice_id: Voice identifier
            clips_data: List of clip data dictionaries
            structure: Song structure with sections
            
        Returns:
            Complete vocal track dictionary
        """
        try:
            clips = []
            
            for clip_data in clips_data:
                clip = self.generate_extended_vocal_clip(
                    clip_id=clip_data.get("id", f"clip-{voice_id}-{len(clips)}"),
                    track_id=track_id,
                    section_id=clip_data.get("sectionId", "sec-unknown"),
                    start_time=clip_data.get("startTime", 0.0),
                    duration=clip_data.get("duration", 4.0),
                    voice_id=voice_id,
                    lyrics_text=clip_data.get("lyrics_text", ""),
                    notes=clip_data.get("notes", ["C4"]),
                    durations=clip_data.get("durations", [1.0]),
                    tags=clip_data.get("tags", ["lead"])
                )
                
                # Add section spans if clip crosses section boundaries
                if clip_data.get("sectionSpans"):
                    clip["sectionSpans"] = self.generate_section_spans(clip_data["sectionSpans"])
                
                clips.append(clip)
            
            track = {
                "id": track_id,
                "name": f"Voice: {voice_id}",
                "instrument": "vocals",
                "category": "vocals",
                "voiceId": voice_id,
                "volume": 0.8,
                "pan": 0,
                "muted": False,
                "solo": False,
                "clips": clips,
                "effects": {
                    "reverb": 0,
                    "delay": 0,
                    "distortion": 0,
                    "pitchShift": 0,
                    "chorus": 0,
                    "filter": 0,
                    "bitcrush": 0
                }
            }
            
            return track
            
        except Exception as e:
            safe_log_error(f"Error creating complete vocal track: {e}")
            return {
                "id": track_id,
                "name": f"Voice: {voice_id}",
                "instrument": "vocals",
                "category": "vocals",
                "voiceId": voice_id,
                "clips": []
            }

    def create_example_extended_song(self) -> Dict[str, Any]:
        """
        Create an example song with extended vocal structure, sections, and phonemes.
        Demonstrates the complete extended JSON format.
        
        Returns:
            Complete song structure with extended vocal features
        """
        try:
            # Define song sections
            sections = [
                {
                    "id": "sec-intro",
                    "type": "intro",
                    "label": "Intro",
                    "startTime": 0.0,
                    "endTime": 8.0,
                    "index": 1
                },
                {
                    "id": "sec-v1",
                    "type": "verse",
                    "label": "Verse 1",
                    "startTime": 8.0,
                    "endTime": 24.0,
                    "index": 1
                },
                {
                    "id": "sec-chorus",
                    "type": "chorus",
                    "label": "Chorus",
                    "startTime": 24.0,
                    "endTime": 40.0,
                    "index": 1
                }
            ]
            
            # Create song structure
            structure = self.generate_song_structure(sections)
            
            # Define vocal clips data
            clips_data = [
                {
                    "id": "clip-v1-soprano-a",
                    "sectionId": "sec-v1",
                    "startTime": 8.0,
                    "duration": 4.0,
                    "lyrics_text": "Shine bright like a diamond",
                    "notes": ["E4", "F4", "G4", "A4", "B4"],
                    "durations": [0.3, 0.3, 0.4, 0.5, 0.5],
                    "tags": ["lead"]
                }
            ]
            
            # Create vocal track
            soprano_track = self.create_complete_vocal_track(
                track_id="track-soprano",
                voice_id="soprano01",
                clips_data=clips_data,
                structure=structure
            )
            
            # Create complete song
            song = {
                "id": "song-example-extended",
                "name": "Extended Vocal Example",
                "tempo": 120,
                "timeSignature": [4, 4],
                "key": "C",
                "structure": structure,
                "tracks": [soprano_track],
                "duration": 40.0,
                "createdAt": "2025-08-21T12:00:00.000Z",
                "updatedAt": "2025-08-21T12:00:00.000Z",
                "lyrics": "Shine bright like a diamond"
            }
            
            return song
            
        except Exception as e:
            safe_log_error(f"Error creating example extended song: {e}")
            return {"error": f"Failed to create example song: {str(e)}"}

    def validate_extended_vocal_structure(self, clip_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate an extended vocal clip structure and provide feedback.
        
        Args:
            clip_data: Vocal clip data to validate
            
        Returns:
            Validation result with status and messages
        """
        try:
            validation_result = {
                "valid": True,
                "errors": [],
                "warnings": [],
                "suggestions": []
            }
            
            # Required fields validation
            required_fields = ["id", "trackId", "type", "sectionId", "startTime", "duration", "voiceId"]
            for field in required_fields:
                if field not in clip_data:
                    validation_result["errors"].append(f"Missing required field: {field}")
                    validation_result["valid"] = False
            
            # Type validation
            if clip_data.get("type") != "lyrics":
                validation_result["errors"].append("Vocal clips must have type 'lyrics'")
                validation_result["valid"] = False
            
            # Lyrics structure validation
            if "lyrics" in clip_data:
                for i, lyric in enumerate(clip_data["lyrics"]):
                    if "text" not in lyric:
                        validation_result["warnings"].append(f"Lyric {i} missing text field")
                    
                    if "syllables" in lyric:
                        # Validate syllable structure
                        for j, syllable in enumerate(lyric["syllables"]):
                            if "t" not in syllable:
                                validation_result["warnings"].append(f"Syllable {j} in lyric {i} missing text ('t') field")
                            if "noteIdx" not in syllable:
                                validation_result["warnings"].append(f"Syllable {j} in lyric {i} missing noteIdx field")
                    
                    if "phonemes" in lyric:
                        if not isinstance(lyric["phonemes"], list):
                            validation_result["warnings"].append(f"Phonemes in lyric {i} should be a list")
            
            # Voice ID validation
            valid_voices = ["soprano01", "alto01", "tenor01", "bass01"]
            if clip_data.get("voiceId") not in valid_voices:
                validation_result["suggestions"].append(f"Consider using a standard voice ID: {', '.join(valid_voices)}")
            
            # Tags validation
            if "tags" in clip_data:
                valid_tags = ["lead", "harmony", "choir", "adlib"]
                for tag in clip_data["tags"]:
                    if tag not in valid_tags:
                        validation_result["suggestions"].append(f"Unknown tag '{tag}'. Valid tags: {', '.join(valid_tags)}")
            
            return validation_result
            
        except Exception as e:
            return {
                "valid": False,
                "errors": [f"Validation error: {str(e)}"],
                "warnings": [],
                "suggestions": []
            }

    def get_extended_vocal_schema(self) -> Dict[str, Any]:
        """
        Get the schema definition for extended vocal clips with examples.
        
        Returns:
            JSON schema for extended vocal clips
        """
        return {
            "title": "Extended Vocal Clip Schema",
            "description": "Enhanced vocal clip structure with syllables, sections, and phonemes",
            "type": "object",
            "required": ["id", "trackId", "type", "sectionId", "startTime", "duration", "voiceId", "lyrics"],
            "properties": {
                "id": {
                    "type": "string",
                    "description": "Unique clip identifier",
                    "example": "clip-v1-soprano-a"
                },
                "trackId": {
                    "type": "string", 
                    "description": "Parent track identifier",
                    "example": "track-soprano"
                },
                "type": {
                    "type": "string",
                    "enum": ["lyrics"],
                    "description": "Clip type (must be 'lyrics' for vocal clips)"
                },
                "sectionId": {
                    "type": "string",
                    "description": "Section identifier for structure reference",
                    "example": "sec-v1"
                },
                "startTime": {
                    "type": "number",
                    "description": "Start time in seconds",
                    "example": 8.0
                },
                "duration": {
                    "type": "number",
                    "description": "Duration in seconds",
                    "example": 4.0
                },
                "voiceId": {
                    "type": "string",
                    "description": "Voice identifier",
                    "enum": ["soprano01", "alto01", "tenor01", "bass01"],
                    "example": "soprano01"
                },
                "lyrics": {
                    "type": "array",
                    "description": "Array of lyric fragments",
                    "items": {
                        "type": "object",
                        "required": ["text", "start", "notes", "durations"],
                        "properties": {
                            "text": {
                                "type": "string",
                                "description": "Lyrics text",
                                "example": "Shine bright like a diamond"
                            },
                            "start": {
                                "type": "number",
                                "description": "Start time relative to clip",
                                "example": 0.0
                            },
                            "notes": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Musical notes",
                                "example": ["E4", "F4", "G4", "A4", "B4"]
                            },
                            "durations": {
                                "type": "array",
                                "items": {"type": "number"},
                                "description": "Duration for each note",
                                "example": [0.3, 0.3, 0.4, 0.5, 0.5]
                            },
                            "syllables": {
                                "type": "array",
                                "description": "Syllable breakdown with note mapping",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "t": {"type": "string", "description": "Syllable text"},
                                        "noteIdx": {"type": "array", "items": {"type": "integer"}},
                                        "dur": {"type": "number", "description": "Duration"},
                                        "melisma": {"type": "boolean", "description": "Is this a melisma"}
                                    }
                                },
                                "example": [
                                    {"t": "Shine", "noteIdx": [0], "dur": 0.3},
                                    {"t": "bright", "noteIdx": [1], "dur": 0.3},
                                    {"t": "like", "noteIdx": [2], "dur": 0.4},
                                    {"t": "a", "noteIdx": [3], "dur": 0.5},
                                    {"t": "dia-mond", "noteIdx": [4], "dur": 0.5, "melisma": True}
                                ]
                            },
                            "phonemes": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "IPA phonemes for TTS/singing engines",
                                "example": ["ʃ", "aɪ", "n", " ", "b", "r", "aɪ", "t"]
                            }
                        }
                    }
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Flexible tags for vocal classification",
                    "enum": ["lead", "harmony", "choir", "adlib"],
                    "example": ["lead"]
                },
                "sectionSpans": {
                    "type": "array",
                    "description": "For clips that span multiple sections",
                    "items": {
                        "type": "object",
                        "properties": {
                            "sectionId": {"type": "string"},
                            "startOffset": {"type": "number"},
                            "duration": {"type": "number"}
                        }
                    },
                    "example": [
                        {"sectionId": "sec-v1", "startOffset": 0.0, "duration": 2.0},
                        {"sectionId": "sec-chorus", "startOffset": 0.0, "duration": 1.0}
                    ]
                }
            }
        }


# Global helper function for creating extended vocal examples
def create_extended_vocal_example() -> Dict[str, Any]:
    """
    Create a comprehensive example showing the extended vocal JSON structure.
    
    Returns:
        Complete song with extended vocal structure, sections, syllables, and phonemes
    """
    return {
        "id": "song-extended-vocal-demo",
        "name": "Extended Vocal Structure Demo",
        "tempo": 120,
        "timeSignature": [4, 4],
        "key": "C",
        "structure": {
            "sections": [
                {
                    "id": "sec-intro",
                    "type": "intro",
                    "label": "Intro",
                    "startTime": 0.0,
                    "endTime": 8.0,
                    "index": 1
                },
                {
                    "id": "sec-v1",
                    "type": "verse",
                    "label": "Verse 1",
                    "startTime": 8.0,
                    "endTime": 24.0,
                    "index": 1
                },
                {
                    "id": "sec-chorus",
                    "type": "chorus",
                    "label": "Chorus",
                    "startTime": 24.0,
                    "endTime": 40.0,
                    "index": 1
                }
            ]
        },
        "tracks": [
            {
                "id": "track-soprano",
                "name": "Soprano Voice",
                "instrument": "vocals",
                "category": "vocals",
                "voiceId": "soprano01",
                "volume": 0.8,
                "pan": -0.2,
                "muted": False,
                "solo": False,
                "clips": [
                    {
                        "id": "clip-v1-soprano-a",
                        "trackId": "track-soprano",
                        "type": "lyrics",
                        "sectionId": "sec-v1",
                        "startTime": 8.0,
                        "duration": 4.0,
                        "voiceId": "soprano01",
                        "lyrics": [
                            {
                                "text": "Shine bright like a diamond",
                                "start": 0.0,
                                "notes": ["E4", "F4", "G4", "A4", "B4"],
                                "durations": [0.3, 0.3, 0.4, 0.5, 0.5],
                                "syllables": [
                                    {"t": "Shine", "noteIdx": [0], "dur": 0.3},
                                    {"t": "bright", "noteIdx": [1], "dur": 0.3},
                                    {"t": "like", "noteIdx": [2], "dur": 0.4},
                                    {"t": "a", "noteIdx": [3], "dur": 0.5},
                                    {"t": "dia-mond", "noteIdx": [4], "dur": 0.5, "melisma": True}
                                ],
                                "phonemes": ["ʃ", "aɪ", "n", " ", "b", "r", "aɪ", "t", " ", "l", "aɪ", "k", " ", "ɑ", " ", "d", "aɪ", "ɑ", "m", "ə", "n", "d"]
                            }
                        ],
                        "tags": ["lead"]
                    }
                ],
                "effects": {
                    "reverb": 0.2,
                    "delay": 0,
                    "distortion": 0,
                    "pitchShift": 0,
                    "chorus": 0,
                    "filter": 0,
                    "bitcrush": 0
                }
            },
            {
                "id": "track-alto",
                "name": "Alto Voice",
                "instrument": "vocals",
                "category": "vocals", 
                "voiceId": "alto01",
                "volume": 0.7,
                "pan": 0.2,
                "muted": False,
                "solo": False,
                "clips": [
                    {
                        "id": "clip-v1-alto-a",
                        "trackId": "track-alto",
                        "type": "lyrics",
                        "sectionId": "sec-v1",
                        "startTime": 10.0,
                        "duration": 6.0,
                        "voiceId": "alto01",
                        "lyrics": [
                            {
                                "text": "So shine tonight",
                                "start": 0.0,
                                "notes": ["C4", "D4", "E4", "F4"],
                                "durations": [0.5, 0.5, 0.5, 1.5],
                                "syllables": [
                                    {"t": "So", "noteIdx": [0], "dur": 0.5},
                                    {"t": "shine", "noteIdx": [1], "dur": 0.5},
                                    {"t": "to-", "noteIdx": [2], "dur": 0.5},
                                    {"t": "night", "noteIdx": [3], "dur": 1.5, "melisma": True}
                                ],
                                "phonemes": ["s", "oʊ", " ", "ʃ", "aɪ", "n", " ", "t", "ə", "n", "aɪ", "t"]
                            }
                        ],
                        "tags": ["harmony"],
                        "sectionSpans": [
                            {"sectionId": "sec-v1", "startOffset": 2.0, "duration": 4.0},
                            {"sectionId": "sec-chorus", "startOffset": 0.0, "duration": 2.0}
                        ]
                    }
                ],
                "effects": {
                    "reverb": 0.1,
                    "delay": 0,
                    "distortion": 0,
                    "pitchShift": 0,
                    "chorus": 0,
                    "filter": 0,
                    "bitcrush": 0
                }
            }
        ],
        "duration": 40.0,
        "createdAt": "2025-08-21T12:00:00.000Z",
        "updatedAt": "2025-08-21T12:00:00.000Z",
        "lyrics": "Shine bright like a diamond\nSo shine tonight"
    }
