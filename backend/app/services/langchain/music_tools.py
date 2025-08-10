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
    
    def format_samples_for_prompt(self, samples: Dict[str, Dict[str, List[str]]]) -> str:
        """Format samples for LLM prompts, including user-uploaded sample metadata"""
        formatted = []
        
        # Add default samples first
        for category, sample_groups in samples.items():
            formatted.append(f"{category.title()} Samples:")
            for group_name, sample_list in sample_groups.items():
                formatted.append(f"  {group_name}: {', '.join(sample_list)}")
        
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
