"""
LangChain Service
Handles advanced AI interactions using LangChain framework with React Agent for music composition

This module has been refactored into smaller, focused components.
Import from the langchain package instead for better modularity.
"""

# Import everything from the new modular structure
from .langchain import *

# Backward compatibility - re-export the main classes and functions
from .langchain.langchain_service import LangChainService
from .langchain.music_tools import MusicCompositionTools
from .langchain.utils import safe_log_error as _safe_log_error

# Make sure all tools are available at the module level for backward compatibility
__all__ = [
    'LangChainService',
    'MusicCompositionTools', 
    '_safe_log_error',
    'analyze_song_structure',
    'get_available_instruments',
    'get_available_samples', 
    'create_track',
    'add_clip_to_track',
    'generate_chord_progression',
    'create_song_section',
    'modify_song_structure',
    'add_lyrics_to_track',
    'create_multi_voice_lyrics',
    'get_available_voices'
]

# Legacy class for backward compatibility
class MusicCompositionTools:
    """Tools for music composition and song structure manipulation"""
    
    def __init__(self):
        self.available_instruments = self._load_available_instruments()
        self.available_samples = self._load_available_samples()
        self.available_voices = self._load_available_voices()
    
    def _load_available_instruments(self) -> Dict[str, List[str]]:
        """Load available instruments from sample library"""
        try:
            current_file = Path(__file__).resolve()
            project_root = current_file.parent.parent.parent.parent
            samples_dir = project_root / 'frontend' / 'public' / 'instruments'
            
            instruments = {}
            if samples_dir.exists():
                for category_dir in samples_dir.iterdir():
                    if category_dir.is_dir():
                        category_instruments = []
                        for instrument_dir in category_dir.iterdir():
                            if instrument_dir.is_dir():
                                # Use the actual instrument directory name
                                instrument_name = instrument_dir.name
                                # Clean up the name for better readability
                                clean_name = instrument_name.replace('_', ' ').replace('(', ' ').replace(')', ' ')
                                clean_name = ' '.join(clean_name.split())  # Remove extra spaces
                                category_instruments.append(clean_name)
                        
                        # Sort instruments alphabetically
                        category_instruments.sort()
                        instruments[category_dir.name] = category_instruments
            
            # If no instruments found, log warning and return empty dict
            if not instruments:
                _safe_log_error("No instruments found in sample library")
                return {}
            
            return instruments
        except Exception as e:
            _safe_log_error(f"Failed to load available instruments: {e}")
            # Return empty dict instead of fallback
            return {}
    
    def _load_available_samples(self) -> Dict[str, Dict[str, List[str]]]:
        """Load available samples for each instrument"""
        try:
            current_file = Path(__file__).resolve()
            project_root = current_file.parent.parent.parent.parent
            samples_dir = project_root / 'frontend' / 'public' / 'instruments'
            
            samples = {}
            if samples_dir.exists():
                for category_dir in samples_dir.iterdir():
                    if category_dir.is_dir():
                        category_samples = {}
                        for instrument_dir in category_dir.iterdir():
                            if instrument_dir.is_dir():
                                instrument_samples = []
                                instrument_name = instrument_dir.name
                                
                                # Look for sample files in various subdirectories
                                for item in instrument_dir.rglob('*.wav'):
                                    sample_name = item.stem
                                    if sample_name not in instrument_samples:
                                        instrument_samples.append(sample_name)
                                
                                # Also look for .sf2 files
                                for item in instrument_dir.rglob('*.sf2'):
                                    sample_name = item.stem
                                    if sample_name not in instrument_samples:
                                        instrument_samples.append(sample_name)
                                
                                # If no specific samples found, add the instrument name itself
                                if not instrument_samples:
                                    instrument_samples.append(instrument_name)
                                
                                clean_name = instrument_name.replace('_', ' ').replace('(', ' ').replace(')', ' ')
                                clean_name = ' '.join(clean_name.split())
                                category_samples[clean_name] = sorted(instrument_samples)
                        
                        samples[category_dir.name] = category_samples
            
            return samples
        except Exception as e:
            _safe_log_error(f"Failed to load available samples: {e}")
            return {}
    
    def _load_available_voices(self) -> Dict[str, Dict[str, Any]]:
        """Load available voices from RVC voice registry"""
        try:
            if VoiceService is None:
                _safe_log_error("VoiceService not available")
                return self._get_default_voices()
            
            voice_service = VoiceService()
            voices = voice_service.get_available_voices()
            
            # Organize voices by type and characteristics
            voice_dict = {}
            for voice in voices:
                voice_id = voice.get('id')
                voice_name = voice.get('name', voice_id)
                voice_type = voice.get('type', 'unknown')
                
                # Extract voice characteristics for better categorization
                characteristics = voice.get('voice_characteristics', {})
                fundamental_freq = characteristics.get('fundamental_freq', 200)
                
                # Categorize by vocal range based on fundamental frequency
                if fundamental_freq > 300:
                    voice_range = 'soprano'
                elif fundamental_freq > 250:
                    voice_range = 'alto'
                elif fundamental_freq > 180:
                    voice_range = 'tenor'
                else:
                    voice_range = 'bass'
                
                voice_dict[voice_id] = {
                    'name': voice_name,
                    'type': voice_type,
                    'range': voice_range,
                    'fundamental_freq': fundamental_freq,
                    'trained': voice.get('trained', False),
                    'language': voice.get('language', 'en')
                }
            
            return voice_dict
        except Exception as e:
            _safe_log_error(f"Failed to load available voices: {e}")
            return self._get_default_voices()
    
    def _get_default_voices(self) -> Dict[str, Dict[str, Any]]:
        """Fallback default voices when voice service is not available"""
        return {
            'default': {
                'name': 'Default Voice',
                'type': 'builtin',
                'range': 'alto',
                'fundamental_freq': 250,
                'trained': True,
                'language': 'en'
            },
            'male-01': {
                'name': 'Male Voice 1',
                'type': 'builtin',
                'range': 'tenor',
                'fundamental_freq': 180,
                'trained': True,
                'language': 'en'
            },
            'female-01': {
                'name': 'Female Voice 1',
                'type': 'builtin',
                'range': 'soprano',
                'fundamental_freq': 320,
                'trained': True,
                'language': 'en'
            }
        }


# Define tools for the React Agent
@tool
def analyze_song_structure(song_json: str) -> str:
    """
    Analyze the current song structure JSON and provide insights.
    
    Args:
        song_json: JSON string of the current song structure
    
    Returns:
        Analysis of the song structure with suggestions
    """
    try:
        song = json.loads(song_json)
        
        analysis = {
            "total_tracks": len(song.get("tracks", [])),
            "song_duration": song.get("duration", 0),
            "tempo": song.get("tempo", 120),
            "key": song.get("key", "C"),
            "instruments_used": [],
            "track_analysis": [],
            "suggestions": []
        }
        
        # Analyze each track
        for track in song.get("tracks", []):
            track_info = {
                "name": track.get("name", ""),
                "instrument": track.get("instrument", ""),
                "clip_count": len(track.get("clips", [])),
                "total_duration": sum(clip.get("duration", 0) for clip in track.get("clips", []))
            }
            analysis["track_analysis"].append(track_info)
            analysis["instruments_used"].append(track.get("instrument", ""))
        
        # Generate suggestions
        if analysis["total_tracks"] == 0:
            analysis["suggestions"].append("Song is empty. Consider adding tracks with instruments like piano, guitar, or drums.")
        elif analysis["total_tracks"] < 3:
            analysis["suggestions"].append("Song could benefit from more instruments. Consider adding bass, lead, or rhythm instruments.")
        
        if "drums" not in analysis["instruments_used"] and "percussion" not in analysis["instruments_used"]:
            analysis["suggestions"].append("Consider adding drums or percussion for rhythm foundation.")
        
        if "bass" not in analysis["instruments_used"]:
            analysis["suggestions"].append("Adding a bass track could provide low-end foundation.")
        
        return json.dumps(analysis, indent=2)
    
    except Exception as e:
        return f"Error analyzing song structure: {str(e)}"


@tool
def get_available_instruments() -> str:
    """
    Get a list of all available instruments that can be used in tracks.
    
    Returns:
        JSON string with available instruments by category
    """
    tools = MusicCompositionTools()
    return json.dumps(tools.available_instruments, indent=2)


@tool
def get_available_samples(category: str = "", instrument: str = "") -> str:
    """
    Get available samples for instruments. Optionally filter by category and instrument.
    
    Args:
        category: Optional category filter (e.g., "guitar", "piano")
        instrument: Optional instrument filter (e.g., "acoustic_guitar")
    
    Returns:
        JSON string with available samples
    """
    tools = MusicCompositionTools()
    samples = tools.available_samples
    
    if category and category in samples:
        samples = {category: samples[category]}
    
    if instrument and category in samples and instrument in samples[category]:
        samples = {category: {instrument: samples[category][instrument]}}
    
    return json.dumps(samples, indent=2)


@tool
def create_track(song_json: str, track_name: str, instrument: str, category: str = "") -> str:
    """
    Add a new track to the song structure.
    
    Args:
        song_json: Current song structure as JSON string
        track_name: Name for the new track
        instrument: Instrument type for the track
        category: Optional category for the instrument
    
    Returns:
        Updated song structure as JSON string
    """
    try:
        # Handle both dict and string inputs
        if isinstance(song_json, dict):
            song = song_json
        else:
            song = json.loads(song_json)
        
        # Set defaults for missing parameters
        if track_name is None:
            track_name = f"{instrument.title()} Track"
        if instrument is None:
            instrument = "piano"
        
        new_track = {
            "id": f"track-{uuid.uuid4().hex[:8]}",
            "name": track_name,
            "instrument": instrument,
            "category": category if category else "other",
            "volume": 0.8,
            "pan": 0,
            "muted": False,
            "solo": False,
            "clips": [],
            "effects": {
                "reverb": 0,
                "delay": 0,
                "distortion": 0
            }
        }
        
        song.setdefault("tracks", []).append(new_track)
        song["updatedAt"] = datetime.now().isoformat()
        
        return json.dumps(song, indent=2)
    
    except Exception as e:
        return f"Error creating track: {str(e)}"


@tool
def add_clip_to_track(song_json: str, track_id: str, start_time: float, duration: float, 
                     clip_type: str = "synth", notes: List[str] = None, sample_url: str = "") -> str:
    """
    Add a clip to a specific track in the song.
    
    Args:
        song_json: Current song structure as JSON string
        track_id: ID of the track to add the clip to
        start_time: Start time in seconds
        duration: Duration in seconds
        clip_type: Type of clip ("synth" or "sample")
        notes: Optional list of notes/chords for the clip
        sample_url: Optional sample URL for sample clips
    
    Returns:
        Updated song structure as JSON string
    """
    try:
        song = json.loads(song_json)
        
        # Find the track
        track = None
        for t in song.get("tracks", []):
            if t.get("id") == track_id:
                track = t
                break
        
        if not track:
            return f"Track with ID {track_id} not found"
        
        new_clip = {
            "id": f"clip-{uuid.uuid4().hex[:8]}",
            "trackId": track_id,
            "startTime": start_time,
            "duration": duration,
            "type": clip_type,
            "instrument": track.get("instrument", "synth"),
            "volume": 0.8,
            "effects": {
                "reverb": 0,
                "delay": 0,
                "distortion": 0
            }
        }
        
        if notes:
            new_clip["notes"] = notes
        
        if sample_url:
            new_clip["sampleUrl"] = sample_url
        
        track.setdefault("clips", []).append(new_clip)
        song["updatedAt"] = datetime.now().isoformat()
        
        # Update song duration if necessary
        max_end_time = max((clip.get("startTime", 0) + clip.get("duration", 0) 
                           for track in song.get("tracks", []) 
                           for clip in track.get("clips", [])), default=0)
        song["duration"] = max(song.get("duration", 0), max_end_time + 2)
        
        return json.dumps(song, indent=2)
    
    except Exception as e:
        return f"Error adding clip: {str(e)}"


@tool
def generate_chord_progression(key: str, style: str = "pop", num_bars: int = 4) -> str:
    """
    Generate a chord progression for a given key and style.
    
    Args:
        key: Musical key (e.g., "C", "G", "Am")
        style: Musical style (e.g., "pop", "jazz", "blues", "rock")
        num_bars: Number of bars for the progression
    
    Returns:
        JSON string with chord progression information
    """
    try:
        # Common chord progressions by style
        progressions = {
            "pop": {
                "C": ["C_major", "Am_minor", "F_major", "G_major"],
                "G": ["G_major", "Em_minor", "C_major", "D_major"],
                "Am": ["Am_minor", "F_major", "C_major", "G_major"],
                "F": ["F_major", "Dm_minor", "Bb_major", "C_major"]
            },
            "jazz": {
                "C": ["Cmaj7", "Am7", "Dm7", "G7"],
                "G": ["Gmaj7", "Em7", "Am7", "D7"],
                "Am": ["Am7", "Dm7", "G7", "Cmaj7"],
                "F": ["Fmaj7", "Dm7", "Gm7", "C7"]
            },
            "blues": {
                "C": ["C7", "C7", "F7", "C7", "G7", "F7", "C7", "G7"],
                "G": ["G7", "G7", "C7", "G7", "D7", "C7", "G7", "D7"],
                "A": ["A7", "A7", "D7", "A7", "E7", "D7", "A7", "E7"]
            },
            "rock": {
                "C": ["C_major", "F_major", "G_major", "C_major"],
                "G": ["G_major", "C_major", "D_major", "G_major"],
                "Am": ["Am_minor", "F_major", "C_major", "G_major"],
                "E": ["E_major", "A_major", "B_major", "E_major"]
            }
        }
        
        style_progressions = progressions.get(style, progressions["pop"])
        base_progression = style_progressions.get(key, style_progressions.get("C", ["C_major", "F_major", "G_major", "Am_minor"]))
        
        # Extend progression to fill requested bars
        full_progression = []
        for i in range(num_bars):
            full_progression.append(base_progression[i % len(base_progression)])
        
        result = {
            "key": key,
            "style": style,
            "num_bars": num_bars,
            "chords": full_progression,
            "roman_numerals": _get_roman_numerals(key, full_progression),
            "suggested_tempo": _get_suggested_tempo(style)
        }
        
        return json.dumps(result, indent=2)
    
    except Exception as e:
        return f"Error generating chord progression: {str(e)}"


def _optimize_clips_simple(clips: List[Dict]) -> List[Dict]:
    """Simple clip optimization function to combine consecutive clips"""
    if not clips:
        return clips
    
    optimized = []
    current_clip = None
    
    for clip in sorted(clips, key=lambda x: x.get('startTime', 0)):
        if current_clip is None:
            current_clip = clip.copy()
        else:
            # Check if clips are consecutive and can be combined
            current_end = current_clip.get('startTime', 0) + current_clip.get('duration', 0)
            clip_start = clip.get('startTime', 0)
            
            if (abs(current_end - clip_start) < 0.1 and  # Consecutive timing
                current_clip.get('trackId') == clip.get('trackId') and  # Same track
                current_clip.get('instrument') == clip.get('instrument') and  # Same instrument
                current_clip.get('notes') == clip.get('notes')):  # Same notes
                # Extend the current clip
                current_clip['duration'] = current_clip.get('duration', 0) + clip.get('duration', 0)
            else:
                # Start a new clip
                optimized.append(current_clip)
                current_clip = clip.copy()
    
    if current_clip:
        optimized.append(current_clip)
    
    return optimized


@tool
def create_song_section(song_json: str, section_name: str, start_time: float, duration: float, 
                       chord_progression: List[str] = None, instruments: List[str] = None) -> str:
    """
    Create a complete song section (verse, chorus, bridge, etc.) with multiple tracks.
    
    Args:
        song_json: Current song structure as JSON string
        section_name: Name of the section (e.g., "verse", "chorus", "bridge", "intro")
        start_time: Start time in seconds
        duration: Duration in seconds
        chord_progression: Optional chord progression for the section
        instruments: Optional list of instruments to use
    
    Returns:
        Updated song structure with the new section
    """
    try:
        # Parse inputs more robustly
        if isinstance(song_json, dict):
            song = song_json
        else:
            song = json.loads(song_json)
        
        # Set defaults for missing parameters
        if section_name is None:
            section_name = "new_section"
        if start_time is None:
            start_time = song.get("duration", 0)
        if duration is None:
            duration = 8.0
        
        # Default instruments if none provided
        if not instruments:
            existing_instruments = [track.get("instrument") for track in song.get("tracks", [])]
            instruments = existing_instruments if existing_instruments else ["piano", "bass", "drums"]
        
        # Default chord progression
        if not chord_progression:
            key = song.get("key", "C")
            chord_progression = ["C_major", "Am_minor", "F_major", "G_major"] if key == "C" else ["G_major", "Em_minor", "C_major", "D_major"]
        
        # Create tracks if they don't exist
        for instrument in instruments:
            track_exists = any(track.get("instrument") == instrument for track in song.get("tracks", []))
            if not track_exists:
                track_result = create_track(json.dumps(song), f"{instrument.title()} Track", instrument)
                song = json.loads(track_result)
        
        # Add clips to each track
        for track in song.get("tracks", []):
            if track.get("instrument") in instruments:
                # Calculate chord duration
                chord_duration = float(duration) / len(chord_progression)
                
                for i, chord in enumerate(chord_progression):
                    clip_start = float(start_time) + (i * chord_duration)
                    notes = [chord] if track.get("instrument") != "drums" else ["C4"]  # Drums use simple pattern
                    
                    clip_result = add_clip_to_track(
                        json.dumps(song), 
                        track.get("id"), 
                        clip_start, 
                        chord_duration, 
                        "synth", 
                        notes
                    )
                    song = json.loads(clip_result)
        
        # Optimize the song structure to combine consecutive clips
        # Apply optimization at module level since we can't import the service here
        for track in song.get("tracks", []):
            if 'clips' in track and isinstance(track['clips'], list):
                track['clips'] = _optimize_clips_simple(track['clips'])
        
        return json.dumps(song, indent=2)
    
    except Exception as e:
        return f"Error creating song section: {str(e)}"


@tool
def modify_song_structure(song_json: str, modifications: str) -> str:
    """
    Apply structural modifications to the song based on natural language description.
    
    Args:
        song_json: Current song structure as JSON string
        modifications: Description of changes to make
    
    Returns:
        Updated song structure as JSON string
    """
    try:
        song = json.loads(song_json)
        modifications = modifications.lower()
        
        # Parse common modifications
        if "tempo" in modifications:
            # Extract tempo value
            import re
            tempo_match = re.search(r'(\d+)\s*bpm', modifications)
            if tempo_match:
                song["tempo"] = int(tempo_match.group(1))
        
        if "key" in modifications:
            # Extract key
            keys = ["c", "d", "e", "f", "g", "a", "b", "am", "dm", "em", "fm", "gm", "bm"]
            for key in keys:
                if key in modifications:
                    song["key"] = key.upper()
                    break
        
        if "add intro" in modifications:
            intro_result = create_song_section(
                json.dumps(song), "intro", 0, 8, 
                ["C_major", "F_major"], ["piano"]
            )
            song = json.loads(intro_result)
        
        if "add bridge" in modifications:
            current_duration = song.get("duration", 32)
            bridge_result = create_song_section(
                json.dumps(song), "bridge", current_duration, 8,
                ["Am_minor", "F_major", "C_major", "G_major"]
            )
            song = json.loads(bridge_result)
        
        song["updatedAt"] = datetime.now().isoformat()
        return json.dumps(song, indent=2)
    
    except Exception as e:
        return f"Error modifying song structure: {str(e)}"


def _get_roman_numerals(key: str, chords: List[str]) -> List[str]:
    """Convert chord names to roman numerals based on key"""
    # Simplified mapping - would be more complex in full implementation
    major_scale_mapping = {
        "C": {"C_major": "I", "Dm_minor": "ii", "Em_minor": "iii", "F_major": "IV", "G_major": "V", "Am_minor": "vi"},
        "G": {"G_major": "I", "Am_minor": "ii", "Bm_minor": "iii", "C_major": "IV", "D_major": "V", "Em_minor": "vi"}
    }
    
    mapping = major_scale_mapping.get(key, major_scale_mapping["C"])
    return [mapping.get(chord, chord) for chord in chords]


def _get_suggested_tempo(style: str) -> int:
    """Get suggested tempo for musical style"""
    tempo_mapping = {
        "pop": 120,
        "rock": 130,
        "jazz": 110,
        "blues": 100,
        "electronic": 128,
        "ballad": 80
    }
    return tempo_mapping.get(style, 120)


class LangChainService:
    """Service for advanced AI interactions using LangChain with React Agent"""
    
    def __init__(self):
        self.openai_chat = None
        self.anthropic_chat = None
        self.memory = ConversationBufferMemory()
        self.agent_executor = None
        self._initialize_models()
        self._setup_react_agent()

    def _format_instruments_for_prompt(self, instruments_dict: Dict[str, List[str]]) -> str:
        """Format available instruments for inclusion in the agent prompt"""
        formatted = []
        for category, instruments in instruments_dict.items():
            # Show more instruments (up to 8) to give agent better options
            display_instruments = instruments[:8]
            if len(instruments) > 8:
                display_instruments.append(f"... and {len(instruments) - 8} more")
            
            formatted.append(f"- {category.title()}: {', '.join(display_instruments)}")
        
        return "\n".join(formatted)

    def _format_voices_for_prompt(self, voices_dict: Dict[str, Dict[str, Any]]) -> str:
        """Format available voices for inclusion in the agent prompt"""
        formatted = []
        
        # Group voices by range for better organization
        ranges = {'soprano': [], 'alto': [], 'tenor': [], 'bass': [], 'other': []}
        
        for voice_id, voice_info in voices_dict.items():
            voice_range = voice_info.get('range', 'other')
            voice_name = voice_info.get('name', voice_id)
            voice_type = voice_info.get('type', 'unknown')
            trained = voice_info.get('trained', False)
            
            status = "✓" if trained else "◯"
            voice_display = f"{voice_id} ({voice_name}) [{voice_type}] {status}"
            
            if voice_range in ranges:
                ranges[voice_range].append(voice_display)
            else:
                ranges['other'].append(voice_display)
        
        # Format by range
        for range_name, voices in ranges.items():
            if voices:
                formatted.append(f"- {range_name.title()}: {', '.join(voices)}")
        
        return "\n".join(formatted) if formatted else "No voices available"
    
    def _initialize_models(self):
        """Initialize LangChain models"""
        try:
            # Initialize OpenAI
            openai_key = os.getenv('OPENAI_API_KEY')
            if openai_key:
                self.openai_chat = ChatOpenAI(
                    openai_api_key=openai_key,
                    model_name="gpt-4",
                    temperature=0.7,
                    max_tokens=2000
                )
            
            # Initialize Anthropic
            anthropic_key = os.getenv('ANTHROPIC_API_KEY')
            if anthropic_key:
                self.anthropic_chat = ChatAnthropic(
                    anthropic_api_key=anthropic_key,
                    model="claude-3-sonnet-20240229",
                    temperature=0.7,
                    max_tokens=2000
                )
                
        except Exception as e:
            _safe_log_error(f"Failed to initialize LangChain models: {str(e)}")
    
    def _setup_react_agent(self):
        """Setup the React Agent with music composition tools"""
        try:
            # Choose the best available model
            llm = self.anthropic_chat or self.openai_chat
            if not llm:
                _safe_log_error("No LLM available for React Agent")
                return
            
            # Define the tools available to the agent
            tools = [
                analyze_song_structure,
                get_available_instruments,
                get_available_samples,
                get_available_voices,
                create_track,
                add_clip_to_track,
                add_lyrics_to_track,
                create_multi_voice_lyrics,
                generate_chord_progression,
                create_song_section,
                modify_song_structure
            ]
            
            # Get available instruments for the prompt
            music_tools = MusicCompositionTools()
            instruments_info = music_tools.available_instruments
            
            # Create a simpler prompt that works better with the React Agent
            try:
                # Try the new langchain_core approach first
                from langchain_core.prompts import PromptTemplate
                from langchain.agents import create_react_agent
                
                prompt = PromptTemplate.from_template("""You are an expert music composition assistant for mITy Studio. You help users create, modify, and improve their musical compositions using the JSON song structure format.

CRITICAL: ONLY USE INSTRUMENTS FROM THE AVAILABLE LIST BELOW!

AVAILABLE INSTRUMENTS BY CATEGORY:
{available_instruments}

AVAILABLE VOICES FOR LYRICS AND VOCALS:
{available_voices}

IMPORTANT: When creating tracks or suggesting instruments, you MUST ONLY use instruments from the list above. Do NOT invent or suggest instruments that are not in this list.

MANDATORY RULES:
1. NEVER suggest instruments like "piano", "guitar", "bass", "drums" unless they appear EXACTLY in the available instruments list above
2. ALWAYS use get_available_instruments tool first to check what instruments are available before making suggestions
3. ALWAYS use instruments from the available list above when calling create_track tool
4. If you need a specific type of instrument (e.g., piano), find the closest match from the available list (e.g., "Grand Piano" instead of "piano")
5. When users ask for song creation or adding instruments, FIRST call get_available_instruments to see what's available
6. For lyrics and vocals, ALWAYS use voice IDs from the available voices list above (e.g., "default", "male-01", "female-01", custom voice IDs)
7. Consider voice characteristics (range, type) when assigning voices to different vocal parts

You have access to the following tools:
{{tools}}

SONG STRUCTURE FORMAT:
The song structure is a JSON object with these key properties:
- name: Song title
- tempo: BPM (beats per minute)
- key: Musical key (e.g., "C", "Am", "F#")
- duration: Total duration in bars/beats
- tracks: Array of track objects
- updatedAt: Timestamp

Each TRACK has:
- id: Unique identifier
- name: Track name
- instrument: Instrument name (MUST be exactly from available instruments list above)
- category: Instrument category (keyboards, strings, percussion, etc.)
- volume: 0.0 to 1.0
- pan: -1.0 to 1.0 (left to right)
- muted: boolean
- solo: boolean
- clips: Array of clip objects
- effects: Object with reverb, delay, distortion values

Each CLIP has:
- id: Unique identifier
- trackId: ID of parent track
- startTime: Start time in beats/bars
- duration: Duration in beats/bars
- type: "synth", "sample", "audio", or "vocal"
- instrument: Instrument name (MUST match track instrument)
- volume: 0.0 to 1.0
- notes: Array of note names or chord names (for melody)
- chord: Chord name (for backing harmony)
- lyrics: Lyrics text (for vocal clips only)
- effects: Object with effect values

LYRICS AND VOCAL CLIPS:
When adding lyrics to a song, create proper vocal clips with advanced multi-voice structure:

SIMPLE LYRICS STRUCTURE (for basic vocals):
- type: "lyrics"
- text: Complete lyrics text
- notes: Array of melody notes for the words
- chordName: Backing chord name
- startTime: Precise timing in seconds
- duration: Duration in seconds
- effects: Reverb and delay for vocal processing

ADVANCED MULTI-VOICE LYRICS STRUCTURE (for complex arrangements):
- type: "lyrics"  
- voices: Array of voice objects, each containing:
  - voice_id: Unique identifier (e.g., "soprano01", "bass01")
  - lyrics: Array of lyric fragments, each with:
    - text: Text fragment (word or phrase)
    - notes: Array of notes for this fragment
    - start: Start time relative to clip start (seconds)
    - duration: Single duration for single note OR
    - durations: Array of durations for multiple notes
- startTime: Clip start time in seconds
- duration: Total clip duration in seconds
- effects: Vocal processing effects

EXAMPLE ADVANCED LYRICS CLIP:
{
  "id": "clip-lyrics-1",
  "trackId": "track-vocals",
  "startTime": 4,
  "duration": 2,
  "type": "lyrics",
  "instrument": "vocals",
  "volume": 0.8,
  "effects": {"reverb": 0.3, "delay": 0.1, "distortion": 0},
  "voices": [
    {
      "voice_id": "soprano01",
      "lyrics": [
        {
          "text": "Hello",
          "notes": ["E4", "F4"],
          "start": 0.0,
          "durations": [0.4, 0.4]
        },
        {
          "text": "world",
          "notes": ["G4"],
          "start": 1.0,
          "duration": 0.6
        }
      ]
    },
    {
      "voice_id": "bass01",
      "lyrics": [
        {
          "text": "Yeah",
          "notes": ["C3"],
          "start": 0.5,
          "duration": 0.6
        }
      ]
    }
  ]
}

LYRICS WORKFLOW:
1. Use get_available_voices to check available RVC voices before creating lyrics
2. Use create_track to create a vocal track with instrument="vocals"
3. For simple lyrics: Use add_lyrics_to_track with simple_mode=True
4. For complex multi-voice: Use create_multi_voice_lyrics or add_lyrics_to_track with voices parameter
5. Use actual voice IDs from available voices list (e.g., "default", "male-01", "female-01", custom voice IDs)
6. Ensure precise timing with start times and durations for each lyric fragment
7. Use appropriate note ranges for different voice types (soprano, alto, tenor, bass)
8. Add melody notes that complement the song's key and chord progressions
9. Consider voice characteristics (range, type, trained status) when assigning voices to vocal parts

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{{tool_names}}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

CRITICAL GUIDELINES:
1. ALWAYS analyze the current song structure first using analyze_song_structure if provided
2. ALWAYS use get_available_instruments tool to check available instruments before making suggestions
3. ALWAYS use get_available_voices tool to check available voices before adding lyrics
4. ONLY suggest instruments from the available instruments list above - never invent instruments
5. ONLY use voice IDs from the available voices list above for lyrics and vocals
6. Use create_track to add new instrument tracks (with instruments from the list only)
7. Use add_lyrics_to_track to add lyrics with proper timing, pitch, voice IDs, and chord information
8. Use add_clip_to_track to add musical content to tracks
9. Use modify_song_structure to update existing song properties
10. Provide practical music theory advice and chord progressions
11. Always return valid JSON song structure when modifying songs
12. Consider the existing tracks, tempo, and key when making suggestions
13. If no song structure exists, create a basic one with recommended tempo and key
14. Match voice characteristics (range, type) with appropriate vocal parts

SONG ANALYSIS STRATEGY:
1. First, understand what's already in the song (tracks, instruments, duration, etc.)
2. Identify what's missing or could be improved
3. Make targeted suggestions based on music theory and composition principles
4. Ensure new additions complement existing elements
5. ALWAYS use instruments from the available list above

INSTRUMENT SELECTION RULES:
- For keyboards/piano: Choose from available keyboards category (e.g., "Grand Piano", "Piano", etc.)
- For guitars: Choose from available strings category (e.g., "Guitar", "Electric guitar", etc.)
- For bass: Choose from available bass instruments in strings category
- For drums: Choose from available percussion category
- For vocals: Use "vocal" category for lyrics and singing
- For other sounds: Check the appropriate category in the available instruments list

EXAMPLE WORKFLOW FOR SONG CREATION:
1. User asks to create a song
2. Call get_available_instruments to see what's available
3. Choose appropriate instruments from the available list
4. Call create_track with exact instrument names from the list
5. Add clips with musical content

EXAMPLE WORKFLOW FOR ADDING LYRICS:
1. User asks to add lyrics to a song
2. Call create_vocal_track if no vocal track exists
3. For simple lyrics: Call add_lyrics_to_track with simple_mode=True
4. For complex multi-voice: Call create_multi_voice_lyrics with voice_parts
5. Ensure precise timing with:
   - startTime: When the clip starts in seconds
   - duration: Total duration of the clip
   - start: Relative timing within the clip for each fragment
   - duration/durations: Timing for each note/word

EXAMPLE ADVANCED LYRICS CLIP STRUCTURE:
{
  "id": "clip-lyrics-1",
  "trackId": "track-vocals",
  "startTime": 4,
  "duration": 2,
  "type": "lyrics",
  "instrument": "vocals",
  "volume": 0.8,
  "effects": {"reverb": 0.3, "delay": 0.1, "distortion": 0},
  "voices": [
    {
      "voice_id": "soprano01",
      "lyrics": [
        {"text": "Hello", "notes": ["E4", "F4"], "start": 0.0, "durations": [0.4, 0.4]},
        {"text": "world", "notes": ["G4"], "start": 1.0, "duration": 0.6}
      ]
    },
    {
      "voice_id": "bass01", 
      "lyrics": [
        {"text": "Yeah", "notes": ["C3"], "start": 0.5, "duration": 0.6}
      ]
    }
  ]
}

Always respond in the language the user speaks to you (English, Dutch, Spanish, etc.).
Be helpful, creative, and knowledgeable about music theory and composition.
Respect the JSON format and ensure all modifications are valid.
NEVER suggest instruments that are not in the available instruments list above.

Question: {{input}}
Thought: {{agent_scratchpad}}""".format(
                    available_instruments=self._format_instruments_for_prompt(instruments_info),
                    available_voices=self._format_voices_for_prompt(music_tools.available_voices)
                ))
                
                # Create the React agent with proper prompt formatting
                agent = create_react_agent(llm, tools, prompt)
                
            except ImportError:
                # Fallback for older versions
                from langchain.agents import initialize_agent, AgentType
                
                agent = initialize_agent(
                    tools=tools,
                    llm=llm,
                    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
                    verbose=True,
                    max_iterations=5,
                    handle_parsing_errors=True
                )
                
                # For older versions, use the agent directly
                self.agent_executor = agent
                return
            
            # Create the agent executor
            self.agent_executor = AgentExecutor(
                agent=agent,
                tools=tools,
                verbose=False,  # Reduce verbosity to avoid StopIteration issues
                max_iterations=5,  # Reduce iterations
                handle_parsing_errors=True,
                return_intermediate_steps=True
            )
            
        except Exception as e:
            try:
                current_app.logger.error(f"Failed to setup React Agent: {str(e)}")
            except RuntimeError:
                # Working outside application context
                print(f"Failed to setup React Agent: {str(e)}")
    
    def chat_with_music_assistant(self, message: str, song_structure: Dict = None, provider: str = 'anthropic') -> Dict:
        """
        Chat with the music composition assistant using React Agent
        
        Args:
            message: User's message
            song_structure: Current song structure as dict
            provider: AI provider to use
        
        Returns:
            Dict with response and updated song structure
        """
        try:
            if not self.agent_executor:
                return self._fallback_response(message, song_structure, "React Agent not available")
            
            # Build enhanced context with song structure analysis
            input_context = self._build_enhanced_context(message, song_structure)
            
            # Execute the agent with better error handling
            try:
                result = self.agent_executor.invoke({"input": input_context})
                
                # Parse the response
                response_text = result.get("output", "I apologize, but I couldn't process your request.")
                
                # Try to extract updated song structure from the response
                updated_structure = self._extract_json_from_response(result.get("output", ""))
                if not updated_structure and song_structure:
                    # If no structure was extracted but we have an existing one, check if tools were used
                    intermediate_steps = result.get('intermediate_steps', [])
                    if intermediate_steps:
                        # Try to extract from tool outputs
                        for step in intermediate_steps:
                            if len(step) > 1:
                                tool_output = step[1]
                                extracted = self._extract_json_from_response(str(tool_output))
                                if extracted:
                                    updated_structure = extracted
                                    break
                
                # Apply clip optimization to any extracted structure
                if updated_structure:
                    updated_structure = self._optimize_song_structure(updated_structure)
                
                return {
                    'response': response_text,
                    'updated_song_structure': updated_structure,
                    'provider': provider,
                    'success': True,
                    'tools_used': result.get('intermediate_steps', [])
                }
                
            except StopIteration as e:
                _safe_log_error(f"Agent execution StopIteration: {str(e)}")
                return self._fallback_response(message, song_structure, "Agent execution incomplete")
            
            except Exception as agent_error:
                _safe_log_error(f"Agent execution error: {str(agent_error)}")
                return self._fallback_response(message, song_structure, str(agent_error))
            
        except Exception as e:
            _safe_log_error(f"Music assistant chat error: {str(e)}")
            return self._fallback_response(message, song_structure, str(e))

    def _build_enhanced_context(self, message: str, song_structure: Dict = None) -> str:
        """Build enhanced context that includes song structure analysis and guidance for the agent"""
        context_parts = [message]
        
        if song_structure:
            # Add current song structure
            context_parts.append(f"\n\nCURRENT SONG STRUCTURE:")
            context_parts.append(json.dumps(song_structure, indent=2))
            
            # Add analysis prompt to guide the agent
            analysis_prompt = self._build_song_analysis_prompt(song_structure)
            context_parts.append(f"\n\nSONG ANALYSIS CONTEXT:")
            context_parts.append(analysis_prompt)
        else:
            context_parts.append(f"\n\nNO CURRENT SONG STRUCTURE - Please create a new song structure if the user wants to add musical elements.")
        
        return "\n".join(context_parts)

    def _build_song_analysis_prompt(self, song_structure: Dict) -> str:
        """Build a prompt that helps the agent understand the current song structure"""
        tracks = song_structure.get('tracks', [])
        tempo = song_structure.get('tempo', 120)
        key = song_structure.get('key', 'C')
        duration = song_structure.get('duration', 0)
        
        analysis_parts = []
        
        # Basic song info
        analysis_parts.append(f"Current song: {tempo} BPM in {key} major/minor, {duration} bars duration")
        
        # Track analysis
        if tracks:
            track_count = len(tracks)
            instruments = [track.get('instrument', 'unknown') for track in tracks]
            categories = list(set([track.get('category', 'unknown') for track in tracks]))
            
            analysis_parts.append(f"Existing tracks ({track_count}): {', '.join(instruments)}")
            analysis_parts.append(f"Categories covered: {', '.join(categories)}")
            
            # Check for common missing elements
            missing_elements = []
            if not any('drum' in inst.lower() or cat == 'percussion' for inst, cat in zip(instruments, categories)):
                missing_elements.append("rhythm/drums")
            if not any('bass' in inst.lower() for inst in instruments):
                missing_elements.append("bass")
            if not any(cat in ['keyboards', 'strings'] for cat in categories):
                missing_elements.append("harmonic foundation (piano/guitar)")
                
            if missing_elements:
                analysis_parts.append(f"Commonly missing elements: {', '.join(missing_elements)}")
            
            # Clip analysis
            total_clips = sum(len(track.get('clips', [])) for track in tracks)
            if total_clips > 0:
                analysis_parts.append(f"Total clips: {total_clips}")
            else:
                analysis_parts.append("No clips - tracks need musical content")
        else:
            analysis_parts.append("Empty song - needs tracks and musical content")
        
        # Suggestions based on analysis
        analysis_parts.append("\nConsider these when making changes:")
        analysis_parts.append("- Ensure good balance between rhythm, harmony, and melody")
        analysis_parts.append("- Use instruments that complement the existing key and tempo")
        analysis_parts.append("- Add clips with appropriate timing and duration")
        analysis_parts.append("- Maintain musical coherence and structure")
        
        return "\n".join(analysis_parts)
    
    def _extract_json_from_response(self, response: str) -> Optional[Dict]:
        """Extract JSON song structure from agent response"""
        try:
            # Look for JSON in the response
            import re
            json_pattern = r'\{[\s\S]*\}'
            matches = re.findall(json_pattern, response)
            
            for match in matches:
                try:
                    parsed = json.loads(match)
                    # Check if it looks like a song structure
                    if 'tracks' in parsed or 'tempo' in parsed or 'key' in parsed:
                        return parsed
                except json.JSONDecodeError:
                    continue
            
            return None
        except Exception:
            return None
    
    def _fallback_response(self, message: str, song_structure: Dict = None, error: str = "") -> Dict:
        """Fallback response when agent is not available - now song structure aware"""
        message_lower = message.lower()
        
        # Load available instruments for fallback
        music_tools = MusicCompositionTools()
        available_instruments = music_tools.available_instruments
        
        # Start with existing structure or create new one
        if song_structure:
            updated_structure = song_structure.copy()
        else:
            updated_structure = {
                'name': 'New Song',
                'tempo': 120,
                'key': 'C',
                'duration': 16,
                'tracks': [],
                'updatedAt': datetime.now().isoformat()
            }
        
        response = "I'm here to help with your music composition!"
        structure_modified = False
        
        # Analyze current song state for better responses
        existing_tracks = updated_structure.get('tracks', [])
        existing_instruments = [track.get('instrument', '') for track in existing_tracks]
        has_drums = any('drum' in inst.lower() for inst in existing_instruments)
        has_bass = any('bass' in inst.lower() for inst in existing_instruments)
        has_harmonic = any(track.get('category') in ['keyboards', 'strings'] for track in existing_tracks)
        
        # Context-aware responses based on current song structure
        if song_structure and existing_tracks:
            response = f"I can see your song has {len(existing_tracks)} track(s) with {', '.join(existing_instruments[:3])}{'...' if len(existing_instruments) > 3 else ''}. "
        
        # Handle specific requests with actual structure modifications
        if 'intro' in message_lower or 'add intro' in message_lower:
            response += "I'll add an intro section to your song."
            try:
                # Choose appropriate instrument based on what's available and already there
                intro_instrument = None
                intro_category = None
                
                if has_harmonic:
                    # If we have harmonic instruments, add a complementary one
                    if available_instruments.get('strings'):
                        intro_instrument = available_instruments['strings'][0]  # First available string instrument
                        intro_category = "strings"
                    elif available_instruments.get('keyboards'):
                        intro_instrument = available_instruments['keyboards'][0]  # First available keyboard
                        intro_category = "keyboards"
                else:
                    # Start with keyboard if available
                    if available_instruments.get('keyboards'):
                        intro_instrument = available_instruments['keyboards'][0]
                        intro_category = "keyboards"
                    elif available_instruments.get('strings'):
                        intro_instrument = available_instruments['strings'][0]
                        intro_category = "strings"
                
                if intro_instrument and intro_category:
                    piano_track = {
                        "id": f"track-{uuid.uuid4().hex[:8]}",
                        "name": f"{intro_instrument} Intro",
                        "instrument": intro_instrument,
                        "category": intro_category,
                        "volume": 0.8,
                        "pan": 0,
                        "muted": False,
                        "solo": False,
                        "clips": [],
                        "effects": {"reverb": 0.2, "delay": 0, "distortion": 0}
                    }
                    
                    # Create intro that matches song key and tempo
                    song_key = updated_structure.get('key', 'C')
                    chord_progression = self._get_intro_chords_for_key(song_key)
                    intro_clips = []
                    
                    for i, chord in enumerate(chord_progression):
                        clip = {
                            "id": f"clip-{uuid.uuid4().hex[:8]}",
                            "trackId": piano_track["id"],
                            "startTime": i * 2,
                            "duration": 2,
                            "type": "synth",
                            "instrument": intro_instrument,
                            "volume": 0.8,
                            "notes": [chord],
                            "effects": {"reverb": 0.2, "delay": 0, "distortion": 0}
                        }
                        intro_clips.append(clip)
                    
                    piano_track["clips"] = self._combine_consecutive_clips(intro_clips)
                    updated_structure.setdefault("tracks", []).append(piano_track)
                    updated_structure["duration"] = max(updated_structure.get("duration", 0), 8)
                    updated_structure["updatedAt"] = datetime.now().isoformat()
                    structure_modified = True
                    response += f" Added a {intro_instrument} intro in {song_key} with a classic chord progression."
                else:
                    response += " No suitable instruments available for intro."
                    
            except Exception as e:
                _safe_log_error(f"Fallback intro creation error: {e}")
                response += " (Note: Structure modification unavailable in fallback mode)"
        
        elif ('chord' in message_lower and ('progression' in message_lower or 'add' in message_lower)) or 'harmony' in message_lower:
            if has_harmonic:
                response += "I can see you already have harmonic instruments. I'll add complementary chords."
            else:
                response += "I'll add a harmonic foundation with chord progressions."
            
            try:
                # Choose instrument based on what's available and what exists
                chord_instrument = None
                chord_category = None
                
                # If we have piano already, try to get guitar
                if any('piano' in inst.lower() for inst in existing_instruments):
                    if available_instruments.get('strings'):
                        for inst in available_instruments['strings']:
                            if 'guitar' in inst.lower():
                                chord_instrument = inst
                                chord_category = "strings"
                                break
                
                # If no guitar found or no piano exists, use first available keyboard
                if not chord_instrument and available_instruments.get('keyboards'):
                    chord_instrument = available_instruments['keyboards'][0]
                    chord_category = "keyboards"
                
                # If no keyboards, use first available string instrument
                if not chord_instrument and available_instruments.get('strings'):
                    chord_instrument = available_instruments['strings'][0]
                    chord_category = "strings"
                
                if chord_instrument and chord_category:
                    chord_track = {
                        "id": f"track-{uuid.uuid4().hex[:8]}",
                        "name": f"{chord_instrument.title()} Chords",
                        "instrument": chord_instrument,
                        "category": chord_category,
                        "volume": 0.8,
                        "pan": 0,
                        "muted": False,
                        "solo": False,
                        "clips": [],
                        "effects": {"reverb": 0.2, "delay": 0, "distortion": 0}
                    }
                
                if chord_instrument and chord_category:
                    song_key = updated_structure.get('key', 'C')
                    chord_progression = self._get_chord_progression_for_key(song_key)
                    chord_clips = []
                    
                    for i, chord in enumerate(chord_progression):
                        clip = {
                            "id": f"clip-{uuid.uuid4().hex[:8]}",
                            "trackId": chord_track["id"],
                            "startTime": i * 4,
                            "duration": 4,
                            "type": "synth",
                            "instrument": chord_instrument,
                            "volume": 0.8,
                            "notes": [chord],
                            "effects": {"reverb": 0.2, "delay": 0, "distortion": 0}
                        }
                        chord_clips.append(clip)
                    
                    chord_track["clips"] = self._combine_consecutive_clips(chord_clips)
                    updated_structure.setdefault("tracks", []).append(chord_track)
                    updated_structure["duration"] = max(updated_structure.get("duration", 0), 16)
                    updated_structure["updatedAt"] = datetime.now().isoformat()
                    structure_modified = True
                    response += f" Added {chord_instrument} chord progression in {song_key}."
                else:
                    response += " No suitable harmonic instruments available."
                
            except Exception as e:
                _safe_log_error(f"Fallback chord creation error: {e}")
                response += " Popular progressions include I-V-vi-IV or vi-IV-I-V."
        
        elif 'bass' in message_lower and 'add' in message_lower:
            if has_bass:
                response += "I see you already have bass. I'll add a complementary bass line."
            else:
                response += "Adding a bass track will provide a solid foundation."
            
            try:
                # Find first available bass instrument
                bass_instrument = None
                bass_category = None
                
                # Look for bass in strings category
                if available_instruments.get('strings'):
                    for inst in available_instruments['strings']:
                        if 'bass' in inst.lower():
                            bass_instrument = inst
                            bass_category = "strings"
                            break
                
                # If no bass found, use first available string instrument
                if not bass_instrument and available_instruments.get('strings'):
                    bass_instrument = available_instruments['strings'][0]
                    bass_category = "strings"
                
                if bass_instrument and bass_category:
                    bass_track = {
                        "id": f"track-{uuid.uuid4().hex[:8]}",
                        "name": f"{bass_instrument} Bass",
                        "instrument": bass_instrument,
                        "category": bass_category,
                        "volume": 0.9,
                        "pan": 0,
                        "muted": False,
                        "solo": False,
                        "clips": [],
                        "effects": {"reverb": 0, "delay": 0, "distortion": 0.1}
                    }
                
                if bass_instrument and bass_category:
                    song_key = updated_structure.get('key', 'C')
                    bass_notes = self._get_bass_notes_for_key(song_key)
                    bass_clips = []
                    
                    for i, note in enumerate(bass_notes):
                        clip = {
                            "id": f"clip-{uuid.uuid4().hex[:8]}",
                            "trackId": bass_track["id"],
                            "startTime": i * 4,
                            "duration": 4,
                            "type": "synth",
                            "instrument": bass_instrument,
                            "volume": 0.9,
                            "notes": [note],
                            "effects": {"reverb": 0, "delay": 0, "distortion": 0.1}
                        }
                        bass_clips.append(clip)
                    
                    bass_track["clips"] = self._combine_consecutive_clips(bass_clips)
                    updated_structure.setdefault("tracks", []).append(bass_track)
                    updated_structure["duration"] = max(updated_structure.get("duration", 0), 16)
                    updated_structure["updatedAt"] = datetime.now().isoformat()
                    structure_modified = True
                    response += f" Added {bass_instrument} bass track with root notes in {song_key}."
                else:
                    response += " No suitable bass instruments available."
                
            except Exception as e:
                _safe_log_error(f"Fallback bass creation error: {e}")
                response += " Consider adding a bass track for low-end foundation."
        
        elif 'drums' in message_lower and 'add' in message_lower:
            if has_drums:
                response += "I see you have drums. I'll add a complementary percussion element."
            else:
                response += "Drums will give your song rhythm and energy."
            
            try:
                # Find first available drum/percussion instrument
                drum_instrument = None
                drum_category = None
                
                # Look for drums in percussion category
                if available_instruments.get('percussion'):
                    for inst in available_instruments['percussion']:
                        if 'drum' in inst.lower():
                            drum_instrument = inst
                            drum_category = "percussion"
                            break
                
                # If no drums found, use first available percussion instrument
                if not drum_instrument and available_instruments.get('percussion'):
                    drum_instrument = available_instruments['percussion'][0]
                    drum_category = "percussion"
                
                if drum_instrument and drum_category:
                    tempo = updated_structure.get('tempo', 120)
                    drum_name = "Percussion" if has_drums else drum_instrument
                    
                    drum_track = {
                        "id": f"track-{uuid.uuid4().hex[:8]}",
                        "name": drum_name,
                        "instrument": drum_instrument,
                        "category": drum_category,
                        "volume": 0.8,
                        "pan": 0,
                        "muted": False,
                        "solo": False,
                        "clips": [],
                        "effects": {"reverb": 0.1, "delay": 0, "distortion": 0}
                    }
                    
                    # Adjust pattern based on tempo
                    pattern_length = 2 if tempo > 140 else 4
                    num_patterns = 16 // pattern_length
                    
                    drum_clips = []
                    for i in range(num_patterns):
                        clip = {
                            "id": f"clip-{uuid.uuid4().hex[:8]}",
                            "trackId": drum_track["id"],
                            "startTime": i * pattern_length,
                            "duration": pattern_length,
                            "type": "synth",
                            "instrument": drum_instrument,
                            "volume": 0.8,
                            "notes": ["C4"],
                            "effects": {"reverb": 0.1, "delay": 0, "distortion": 0}
                        }
                        drum_clips.append(clip)
                    
                    drum_track["clips"] = self._combine_consecutive_clips(drum_clips)
                    updated_structure.setdefault("tracks", []).append(drum_track)
                    updated_structure["duration"] = max(updated_structure.get("duration", 0), 16)
                    updated_structure["updatedAt"] = datetime.now().isoformat()
                    structure_modified = True
                    response += f" Added {drum_name.lower()} pattern suitable for {tempo} BPM."
                else:
                    response += " No suitable percussion instruments available."
                
            except Exception as e:
                _safe_log_error(f"Fallback drum creation error: {e}")
                response += " Consider adding drums for rhythm foundation."
        
        elif 'lyrics' in message_lower or 'vocal' in message_lower or 'sing' in message_lower:
            response += "I'll help you add lyrics to your song."
            
            try:
                # Check if there's already a vocal track
                vocal_track = None
                for track in existing_tracks:
                    if track.get('category') == 'vocal' or 'vocal' in track.get('instrument', '').lower():
                        vocal_track = track
                        break
                
                # Create vocal track if it doesn't exist
                if not vocal_track:
                    vocal_track = {
                        "id": f"track-{uuid.uuid4().hex[:8]}",
                        "name": "Lyrics & Vocals",
                        "instrument": "vocals",
                        "category": "vocals",
                        "volume": 0.8,
                        "pan": 0,
                        "muted": False,
                        "solo": False,
                        "clips": [],
                        "effects": {"reverb": 0.3, "delay": 0.1, "distortion": 0}
                    }
                    updated_structure.setdefault("tracks", []).append(vocal_track)
                    response += " Created a vocal track for your lyrics."
                
                # Add sample lyrics if no specific lyrics are provided
                if not any(word in message_lower for word in ['add', 'write', 'create']):
                    # Just inform about lyrics capability
                    response += " You can add lyrics with advanced multi-voice structure including precise timing, pitch, and voice parts. "
                    response += "Lyrics support both simple and complex multi-voice arrangements with individual note timing."
                else:
                    # Add placeholder lyrics with advanced structure using actual voices
                    song_key = updated_structure.get('key', 'C')
                    sample_lyrics = "mitystudio forever in our hearts"
                    
                    # Get appropriate voice for fallback
                    fallback_voice_id = "default"
                    try:
                        # Try to get a suitable voice from available voices
                        for voice_id, voice_info in available_instruments.items():
                            if isinstance(voice_info, dict) and voice_info.get('trained', False):
                                fallback_voice_id = voice_id
                                break
                    except:
                        pass
                    
                    # Create advanced lyrics clip structure
                    lyrics_clip = {
                        "id": f"clip-{uuid.uuid4().hex[:8]}",
                        "trackId": vocal_track["id"],
                        "startTime": 0,
                        "duration": 4,
                        "type": "lyrics",
                        "instrument": "vocals",
                        "volume": 0.8,
                        "effects": {"reverb": 0.3, "delay": 0.1, "distortion": 0},
                        "voices": [
                            {
                                "voice_id": fallback_voice_id,
                                "lyrics": [
                                    {
                                        "text": "Hello",
                                        "notes": ["E4", "F4"] if song_key == 'C' else ["B4", "C5"],
                                        "start": 0.0,
                                        "durations": [0.4, 0.4]
                                    },
                                    {
                                        "text": "world",
                                        "notes": ["G4"] if song_key == 'C' else ["D5"],
                                        "start": 1.0,
                                        "duration": 0.8
                                    },
                                    {
                                        "text": "this",
                                        "notes": ["A4"] if song_key == 'C' else ["E5"],
                                        "start": 2.0,
                                        "duration": 0.4
                                    },
                                    {
                                        "text": "is",
                                        "notes": ["G4"] if song_key == 'C' else ["D5"],
                                        "start": 2.5,
                                        "duration": 0.4
                                    },
                                    {
                                        "text": "my",
                                        "notes": ["F4"] if song_key == 'C' else ["C5"],
                                        "start": 3.0,
                                        "duration": 0.4
                                    },
                                    {
                                        "text": "song",
                                        "notes": ["C4"] if song_key == 'C' else ["G4"],
                                        "start": 3.5,
                                        "duration": 0.5
                                    }
                                ]
                            }
                        ]
                    }
                    
                    vocal_track["clips"].append(lyrics_clip)
                    updated_structure["duration"] = max(updated_structure.get("duration", 0), 4)
                    updated_structure["updatedAt"] = datetime.now().isoformat()
                    structure_modified = True
                    response += f" Added sample lyrics in {song_key} with advanced multi-voice structure and precise timing."
                
            except Exception as e:
                _safe_log_error(f"Fallback lyrics creation error: {e}")
                response += " Consider adding a vocal track with lyrics that include advanced multi-voice structure, precise timing, and voice parts."
        
        # ...existing code for other cases...
        elif 'tempo' in message_lower:
            response = "You can adjust the tempo in your song structure."
            # Try to extract tempo from message
            import re
            tempo_match = re.search(r'(\d+)\s*bpm', message_lower)
            if tempo_match:
                new_tempo = int(tempo_match.group(1))
                updated_structure['tempo'] = new_tempo
                updated_structure["updatedAt"] = datetime.now().isoformat()
                structure_modified = True
                response += f" I've set your song tempo to {new_tempo} BPM."
            else:
                response += " Most pop songs are 110-130 BPM, while ballads are typically 60-90 BPM."
        
        else:
            # Context-aware general responses using available instruments
            if not existing_tracks:
                # Suggest available instruments for starting a song
                suggestions = []
                if available_instruments.get('percussion'):
                    suggestions.append(f"drums ({available_instruments['percussion'][0]})")
                if available_instruments.get('strings'):
                    bass_insts = [inst for inst in available_instruments['strings'] if 'bass' in inst.lower()]
                    if bass_insts:
                        suggestions.append(f"bass ({bass_insts[0]})")
                    else:
                        suggestions.append(f"strings ({available_instruments['strings'][0]})")
                if available_instruments.get('keyboards'):
                    suggestions.append(f"keyboards ({available_instruments['keyboards'][0]})")
                
                if suggestions:
                    response += f" Your song is empty. Consider starting with {', then add '.join(suggestions)}."
                else:
                    response += " Your song is empty. Please upload some instrument samples to get started."
            elif not has_drums:
                if available_instruments.get('percussion'):
                    drum_options = [inst for inst in available_instruments['percussion'] if 'drum' in inst.lower()]
                    if drum_options:
                        response += f" Consider adding drums for rhythmic foundation. Available: {drum_options[0]}"
                    else:
                        response += f" Consider adding percussion for rhythm. Available: {available_instruments['percussion'][0]}"
                else:
                    response += " Consider uploading drum samples for rhythmic foundation."
            elif not has_bass:
                if available_instruments.get('strings'):
                    bass_options = [inst for inst in available_instruments['strings'] if 'bass' in inst.lower()]
                    if bass_options:
                        response += f" A bass track would strengthen your song's foundation. Available: {bass_options[0]}"
                    else:
                        response += f" Consider adding low-end instruments. Available: {available_instruments['strings'][0]}"
                else:
                    response += " Consider uploading bass samples for low-end foundation."
            elif not has_harmonic:
                response += " Adding piano or guitar chords would provide harmonic structure."
            else:
                response += " Your song has good basic elements. Consider adding melody instruments or effects."
            
            # Default fallback responses for specific keywords
            fallback_responses = {
                'instrument': "Available instruments include piano, guitar, bass, drums, strings, brass, woodwinds, and synthesizers. Each adds different character to your music.",
                'help': "I can help you with chord progressions, adding instruments, creating song sections, adjusting tempo, and more!"
            }
            
            for keyword, answer in fallback_responses.items():
                if keyword in message_lower:
                    response = answer
                    break
        
        if error:
            response += f" (Note: AI assistant temporarily unavailable: {error})"
        
        return {
            'response': response,
            'updated_song_structure': updated_structure if structure_modified else None,
            'provider': 'fallback',
            'success': structure_modified,
            'error': error
        }
    
    def _get_intro_chords_for_key(self, key: str) -> List[str]:
        """Get appropriate intro chord progression for a given key"""
        intro_progressions = {
            'C': ['C_major', 'F_major', 'Am_minor', 'G_major'],
            'G': ['G_major', 'C_major', 'Em_minor', 'D_major'],
            'F': ['F_major', 'Bb_major', 'Dm_minor', 'C_major'],
            'D': ['D_major', 'G_major', 'Bm_minor', 'A_major'],
            'A': ['A_major', 'D_major', 'F#m_minor', 'E_major'],
            'E': ['E_major', 'A_major', 'C#m_minor', 'B_major'],
            'Am': ['Am_minor', 'Dm_minor', 'G_major', 'C_major'],
            'Em': ['Em_minor', 'Am_minor', 'D_major', 'G_major'],
            'Dm': ['Dm_minor', 'Gm_minor', 'C_major', 'F_major']
        }
        return intro_progressions.get(key, intro_progressions['C'])
    
    def _get_chord_progression_for_key(self, key: str) -> List[str]:
        """Get a standard chord progression for a given key"""
        progressions = {
            'C': ['C_major', 'Am_minor', 'F_major', 'G_major'],
            'G': ['G_major', 'Em_minor', 'C_major', 'D_major'],
            'F': ['F_major', 'Dm_minor', 'Bb_major', 'C_major'],
            'D': ['D_major', 'Bm_minor', 'G_major', 'A_major'],
            'A': ['A_major', 'F#m_minor', 'D_major', 'E_major'],
            'E': ['E_major', 'C#m_minor', 'A_major', 'B_major'],
            'Am': ['Am_minor', 'F_major', 'C_major', 'G_major'],
            'Em': ['Em_minor', 'C_major', 'G_major', 'D_major'],
            'Dm': ['Dm_minor', 'Bb_major', 'F_major', 'C_major']
        }
        return progressions.get(key, progressions['C'])
    
    def _get_bass_notes_for_key(self, key: str) -> List[str]:
        """Get appropriate bass notes for a given key"""
        bass_notes = {
            'C': ['C2', 'A2', 'F2', 'G2'],
            'G': ['G2', 'E2', 'C2', 'D2'],
            'F': ['F2', 'D2', 'Bb2', 'C2'],
            'D': ['D2', 'B2', 'G2', 'A2'],
            'A': ['A2', 'F#2', 'D2', 'E2'],
            'E': ['E2', 'C#2', 'A2', 'B2'],
            'Am': ['A2', 'F2', 'C2', 'G2'],
            'Em': ['E2', 'C2', 'G2', 'D2'],
            'Dm': ['D2', 'Bb2', 'F2', 'C2']
        }
        return bass_notes.get(key, bass_notes['C'])

    def chat_with_context(self, message: str, context: Dict, provider: str = 'openai') -> Dict:
        """
        Advanced chat with context and memory (legacy method for compatibility)
        """
        return self.chat_with_music_assistant(message, context.get('song_structure'), provider)
    
    def generate_composition_plan(self, requirements: Dict) -> Dict:
        """
        Generate a detailed composition plan using AI
        """
        try:
            if not self.agent_executor:
                return self._fallback_composition_plan(requirements)
            
            # Create a prompt for composition planning
            planning_message = f"""Please create a composition plan for a song with these requirements:
            - Genre: {requirements.get('genre', 'pop')}
            - Tempo: {requirements.get('tempo', 120)} BPM
            - Key: {requirements.get('key', 'C')}
            - Mood: {requirements.get('mood', 'upbeat')}
            - Duration: {requirements.get('duration', '3-4 minutes')}
            
            Create a complete song structure with sections (intro, verse, chorus, bridge, outro) and suggest appropriate instruments and chord progressions."""
            
            result = self.agent_executor.invoke({"input": planning_message})
            
            # Parse the response into a structured plan
            plan = self._parse_composition_plan(result.get("output", ""))
            
            return {
                'plan': plan,
                'requirements': requirements,
                'success': True
            }
            
        except Exception as e:
            _safe_log_error(f"Composition planning error: {str(e)}")
            return {
                'plan': self._fallback_composition_plan(requirements),
                'requirements': requirements,
                'success': False,
                'error': str(e)
            }
    
    def analyze_project(self, project_data: Dict) -> Dict:
        """
        Analyze a music project and provide feedback
        """
        try:
            if not self.agent_executor:
                return self._fallback_project_analysis(project_data)
            
            analysis_message = f"""Please analyze this music project and provide detailed feedback:
            
            Project data: {json.dumps(project_data, indent=2)}
            
            Provide analysis on:
            - Song structure and arrangement
            - Instrument balance and selection
            - Harmonic content and chord progressions
            - Rhythm and timing
            - Suggestions for improvement
            - Overall score out of 100"""
            
            result = self.agent_executor.invoke({"input": analysis_message})
            
            analysis = self._parse_project_analysis(result.get("output", ""))
            
            return {
                'analysis': analysis,
                'success': True
            }
            
        except Exception as e:
            _safe_log_error(f"Project analysis error: {str(e)}")
            return {
                'analysis': self._fallback_project_analysis(project_data),
                'success': False,
                'error': str(e)
            }
    
    def generate_chord_progression_ai(self, requirements: Dict) -> Dict:
        """
        Generate chord progressions using AI with music theory knowledge
        """
        try:
            if not self.agent_executor:
                return self._fallback_chord_progression(requirements)
            
            chord_message = f"""Generate a chord progression with these specifications:
            - Key: {requirements.get('key', 'C')}
            - Genre: {requirements.get('genre', 'pop')}
            - Number of chords: {requirements.get('num_chords', 4)}
            - Complexity: {requirements.get('complexity', 'simple')}
            - Mood: {requirements.get('mood', 'happy')}
            
            Provide the chord progression in both chord names and Roman numeral analysis."""
            
            result = self.agent_executor.invoke({"input": chord_message})
            
            progression = self._parse_chord_response(result.get("output", ""), requirements)
            
            return {
                'progression': progression,
                'success': True
            }
            
        except Exception as e:
            _safe_log_error(f"Chord generation error: {str(e)}")
            return {
                'progression': self._fallback_chord_progression(requirements),
                'success': False,
                'error': str(e)
            }
    
    def _build_music_system_prompt(self, context: Dict) -> str:
        """Build system prompt for music composition context"""
        return f"""You are an expert music composition assistant for mITy Studio. 
        
        Current context:
        - Available instruments: {context.get('available_instruments', 'piano, guitar, bass, drums, strings')}
        - Current song key: {context.get('key', 'C')}
        - Current tempo: {context.get('tempo', 120)} BPM
        - Genre preference: {context.get('genre', 'pop')}
        
        You help users create, modify, and improve their musical compositions. Always provide practical, actionable advice and respect the JSON song structure format used by the application."""
    
    def _build_composition_prompt(self, requirements: Dict) -> str:
        """Build prompt for composition planning"""
        return f"""Create a detailed composition plan for a song with these requirements:
        
        Genre: {requirements.get('genre', 'pop')}
        Tempo: {requirements.get('tempo', 120)} BPM
        Key: {requirements.get('key', 'C')}
        Mood: {requirements.get('mood', 'upbeat')}
        Duration: {requirements.get('duration', '3-4 minutes')}
        Instruments: {requirements.get('instruments', 'flexible')}
        
        Please provide:
        1. Song structure (sections and their order)
        2. Chord progressions for each section
        3. Tempo mapping
        4. Arrangement suggestions
        5. Instrument recommendations"""
    
    def _extract_structured_response(self, response: str, context: Dict) -> Dict:
        """Extract structured information from AI response"""
        response_lower = response.lower()
        structured = {
            'suggested_actions': [],
            'chord_suggestions': [],
            'instrument_suggestions': [],
            'tempo_suggestions': [],
            'key_suggestions': []
        }
        
        # Extract tempo suggestions
        import re
        tempo_matches = re.findall(r'(\d+)\s*bpm', response_lower)
        if tempo_matches:
            structured['tempo_suggestions'] = [int(t) for t in tempo_matches]
        
        # Extract key suggestions
        keys = ['c major', 'g major', 'f major', 'a minor', 'e minor', 'd minor']
        for key in keys:
            if key in response_lower:
                structured['key_suggestions'].append(key.title())
        
        # Extract action suggestions
        if 'add intro' in response_lower or 'create intro' in response_lower:
            structured['suggested_actions'].append('add_intro')
        
        if 'add bridge' in response_lower or 'create bridge' in response_lower:
            structured['suggested_actions'].append('add_bridge')
        
        if 'add verse' in response_lower:
            structured['suggested_actions'].append('add_verse')
        
        if 'add chorus' in response_lower:
            structured['suggested_actions'].append('add_chorus')
        
        if 'melody' in response_lower:
            structured['suggested_actions'].append('add_melody')
        
        if 'bass' in response_lower:
            structured['suggested_actions'].append('add_bass')
        
        return structured
    
    def _parse_composition_plan(self, response: str) -> Dict:
        """Parse composition plan from AI response"""
        # Try to extract JSON from response first
        json_structure = self._extract_json_from_response(response)
        if json_structure:
            return json_structure
        
        # Fallback to basic parsing
        return {
            'structure': ['Intro', 'Verse 1', 'Chorus', 'Verse 2', 'Chorus', 'Bridge', 'Chorus', 'Outro'],
            'chord_progressions': {
                'verse': ['C', 'Am', 'F', 'G'],
                'chorus': ['F', 'C', 'G', 'Am']
            },
            'tempo_map': [
                {'section': 'Intro', 'tempo': 120},
                {'section': 'Verse', 'tempo': 120},
                {'section': 'Chorus', 'tempo': 120}
            ],
            'arrangement_notes': response
        }
    
    def _parse_project_analysis(self, response: str) -> Dict:
        """Parse project analysis from AI response"""
        # Extract score from response
        import re
        score_match = re.search(r'(\d+)/100|(\d+)%|score[:\s]*(\d+)', response.lower())
        score = 75  # default
        if score_match:
            score = int(score_match.group(1) or score_match.group(2) or score_match.group(3))
        
        return {
            'overall_score': score,
            'recommendations': [
                'Consider adding a bass track for low-end foundation',
                'Add reverb to vocals for depth',
                'Balance the frequency spectrum with EQ'
            ],
            'strengths': [
                'Good rhythm foundation',
                'Clear melodic structure'
            ],
            'areas_for_improvement': [
                'Frequency balance',
                'Dynamic range'
            ],
            'full_analysis': response
        }
    
    def _parse_chord_response(self, response: str, requirements: Dict) -> Dict:
        """Parse chord progression response"""
        # Try to extract JSON first
        json_data = self._extract_json_from_response(response)
        if json_data and 'chords' in json_data:
            return json_data
        
        # Fallback parsing
        genre = requirements.get('genre', 'pop')
        key = requirements.get('key', 'C')
        
        if genre == 'jazz':
            progression = ['Cmaj7', 'Am7', 'Dm7', 'G7']
            roman = ['Imaj7', 'vi7', 'ii7', 'V7']
        else:
            progression = ['C', 'Am', 'F', 'G']
            roman = ['I', 'vi', 'IV', 'V']
        
        return {
            'progression_roman': roman,
            'progression_chords': progression,
            'theory_explanation': f"This is a common {genre} progression in {key}",
            'playing_suggestions': ['Try different inversions', 'Add seventh chords for color'],
            'variations': [['C', 'G', 'Am', 'F']],
            'ai_response': response
        }
    
    def _fallback_composition_plan(self, requirements: Dict) -> Dict:
        """Fallback composition plan when AI is unavailable"""
        return {
            'structure': ['Intro', 'Verse', 'Chorus', 'Verse', 'Chorus', 'Outro'],
            'chord_progressions': {
                'verse': ['C', 'Am', 'F', 'G'],
                'chorus': ['F', 'C', 'G', 'Am']
            },
            'tempo_map': [{'section': 'All', 'tempo': requirements.get('tempo', 120)}],
            'arrangement_notes': 'Basic song structure for ' + requirements.get('genre', 'pop')
        }
    
    def _fallback_chord_progression(self, requirements: Dict) -> Dict:
        """Fallback chord progression when AI is unavailable"""
        return {
            'progression_roman': ['I', 'vi', 'IV', 'V'],
            'progression_chords': ['C', 'Am', 'F', 'G'],
            'theory_explanation': 'Classic pop progression',
            'playing_suggestions': ['Use simple strumming pattern'],
            'variations': [['C', 'G', 'Am', 'F']],
            'ai_response': 'Fallback response - AI service unavailable'
        }
    
    def _fallback_project_analysis(self, project_data: Dict) -> Dict:
        """Fallback project analysis when AI is unavailable"""
        num_tracks = len(project_data.get('tracks', []))
        
        return {
            'overall_score': 70,
            'recommendations': [
                'Add more instruments for fuller sound' if num_tracks < 3 else 'Good instrument variety',
                'Consider adding bass for low-end support',
                'Balance the mix with appropriate volumes'
            ],
            'strengths': [
                'Basic structure in place',
                f'{num_tracks} tracks created'
            ],
            'areas_for_improvement': [
                'Arrangement complexity',
                'Harmonic progression'
            ],
            'full_analysis': 'Basic analysis - AI service unavailable'
        }
    
    def _optimize_song_structure(self, song_structure: Dict) -> Dict:
        """
        Optimize the entire song structure by combining consecutive clips for each track.
        
        Args:
            song_structure: Complete song structure dictionary
            
        Returns:
            Optimized song structure with consecutive clips combined
        """
        try:
            if not song_structure or not isinstance(song_structure, dict):
                return song_structure
                
            optimized_structure = song_structure.copy()
            tracks = optimized_structure.get('tracks', [])
            
            for track in tracks:
                if 'clips' in track and isinstance(track['clips'], list):
                    # Optimize clips for this track
                    track['clips'] = self._combine_consecutive_clips(track['clips'])
            
            # Update the structure timestamp
            optimized_structure['updatedAt'] = datetime.now().isoformat()
            
            return optimized_structure
            
        except Exception as e:
            _safe_log_error(f"Error optimizing song structure: {e}")
            return song_structure
    
    def _combine_consecutive_clips(self, clips: List[Dict]) -> List[Dict]:
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
            _safe_log_error(f"Error combining consecutive clips: {e}")
            # Return original clips if combining fails
            return clips


@tool
def add_lyrics_to_track(song_json: str, track_id: str, lyrics_text: str, start_time: float, 
                       duration: float, voices: List[Dict] = None, simple_mode: bool = False) -> str:
    """
    Add lyrics to a vocal track with advanced multi-voice structure or simple mode.
    
    Args:
        song_json: Current song structure as JSON string
        track_id: ID of the vocal track to add lyrics to
        lyrics_text: The lyrics text (can be multiple lines)
        start_time: Start time in seconds
        duration: Total duration in seconds
        voices: Optional list of voice configurations with voice_id and range
        simple_mode: If True, use simple structure; if False, use advanced multi-voice structure
    
    Returns:
        Updated song structure with lyrics added as clips
    """
    try:
        # Handle both dict and string inputs
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
        
        # Parse lyrics into words/phrases
        lyrics_words = lyrics_text.split()
        
        if not lyrics_words:
            return "Error: No lyrics provided"
        
        # Get song key for note generation
        song_key = song.get('key', 'C')
        
        # Create the lyrics clip with advanced structure
        lyrics_clip = {
            "id": f"clip-{uuid.uuid4().hex[:8]}",
            "trackId": track_id,
            "startTime": start_time,
            "duration": duration,
            "type": "lyrics",
            "instrument": "vocals",
            "volume": 0.8,
            "effects": {"reverb": 0.3, "delay": 0.1, "distortion": 0}
        }
        
        if simple_mode:
            # Simple structure for basic use cases
            # Get melody notes based on song key
            melody_notes = []
            if song_key.startswith('C'):
                base_notes = ["C4", "D4", "E4", "F4", "G4", "A4", "B4"]
            elif song_key.startswith('G'):
                base_notes = ["G4", "A4", "B4", "C5", "D5", "E5", "F#5"]
            elif song_key.startswith('F'):
                base_notes = ["F4", "G4", "A4", "Bb4", "C5", "D5", "E5"]
            else:
                base_notes = ["C4", "D4", "E4", "F4", "G4", "A4", "B4"]
            
            # Assign notes to words
            for i, word in enumerate(lyrics_words):
                note_index = i % len(base_notes)
                melody_notes.append(base_notes[note_index])
            
            # Simple structure
            lyrics_clip.update({
                "text": lyrics_text,
                "notes": melody_notes,
                "chordName": f"{song_key}_major" if not song_key.endswith('m') else f"{song_key[:-1]}_minor"
            })
        else:
            # Advanced multi-voice structure
            if not voices:
                # Load available voices and select appropriate ones
                try:
                    music_tools = MusicCompositionTools()
                    available_voices = music_tools.available_voices
                    
                    # Default voice configuration using actual available voices
                    if available_voices:
                        # Find the best voice for lead vocals (prefer female voice for soprano range)
                        lead_voice = None
                        for voice_id, voice_info in available_voices.items():
                            if voice_info.get('range') in ['soprano', 'alto'] and voice_info.get('trained', False):
                                lead_voice = voice_id
                                break
                        
                        # If no soprano/alto found, use the first available trained voice
                        if not lead_voice:
                            for voice_id, voice_info in available_voices.items():
                                if voice_info.get('trained', False):
                                    lead_voice = voice_id
                                    break
                        
                        # Use the selected voice or fallback to default
                        selected_voice_id = lead_voice or "default"
                        selected_voice_range = available_voices.get(selected_voice_id, {}).get('range', 'soprano')
                        
                        voices = [
                            {"voice_id": selected_voice_id, "range": selected_voice_range, "words_start": 0, "words_count": len(lyrics_words)}
                        ]
                    else:
                        # Fallback to default voice
                        voices = [
                            {"voice_id": "default", "range": "soprano", "words_start": 0, "words_count": len(lyrics_words)}
                        ]
                except Exception as e:
                    _safe_log_error(f"Error loading voices for lyrics: {e}")
                    # Ultimate fallback
                    voices = [
                        {"voice_id": "default", "range": "soprano", "words_start": 0, "words_count": len(lyrics_words)}
                    ]
            
            # Generate voices array
            voices_array = []
            
            for voice_config in voices:
                voice_id = voice_config.get("voice_id", "voice1")
                voice_range = voice_config.get("range", "soprano")
                words_start = voice_config.get("words_start", 0)
                words_count = voice_config.get("words_count", len(lyrics_words))
                
                # Get notes for this voice range
                if voice_range == "soprano":
                    if song_key.startswith('C'):
                        voice_notes = ["E4", "F4", "G4", "A4", "B4", "C5", "D5"]
                    elif song_key.startswith('G'):
                        voice_notes = ["B4", "C5", "D5", "E5", "F#5", "G5", "A5"]
                    else:
                        voice_notes = ["E4", "F4", "G4", "A4", "B4", "C5", "D5"]
                elif voice_range == "alto":
                    if song_key.startswith('C'):
                        voice_notes = ["C4", "D4", "E4", "F4", "G4", "A4", "B4"]
                    elif song_key.startswith('G'):
                        voice_notes = ["G4", "A4", "B4", "C5", "D5", "E5", "F#5"]
                    else:
                        voice_notes = ["C4", "D4", "E4", "F4", "G4", "A4", "B4"]
                elif voice_range == "tenor":
                    if song_key.startswith('C'):
                        voice_notes = ["G3", "A3", "B3", "C4", "D4", "E4", "F4"]
                    elif song_key.startswith('G'):
                        voice_notes = ["D4", "E4", "F#4", "G4", "A4", "B4", "C5"]
                    else:
                        voice_notes = ["G3", "A3", "B3", "C4", "D4", "E4", "F4"]
                elif voice_range == "bass":
                    if song_key.startswith('C'):
                        voice_notes = ["C3", "D3", "E3", "F3", "G3", "A3", "B3"]
                    elif song_key.startswith('G'):
                        voice_notes = ["G3", "A3", "B3", "C4", "D4", "E4", "F#4"]
                    else:
                        voice_notes = ["C3", "D3", "E3", "F3", "G3", "A3", "B3"]
                else:
                    # Default to soprano range
                    voice_notes = ["E4", "F4", "G4", "A4", "B4", "C5", "D5"]
                
                # Create lyrics fragments for this voice
                voice_lyrics = []
                voice_words = lyrics_words[words_start:words_start + words_count]
                
                # Calculate timing for each word
                word_duration = duration / len(voice_words) if voice_words else 1.0
                
                for i, word in enumerate(voice_words):
                    # Determine if word has multiple syllables (simple heuristic)
                    syllable_count = max(1, len([c for c in word if c.lower() in 'aeiou']))
                    
                    if syllable_count > 1:
                        # Multiple notes for multi-syllable words
                        word_notes = []
                        durations = []
                        syllable_duration = word_duration / syllable_count
                        
                        for j in range(syllable_count):
                            note_index = (i + j) % len(voice_notes)
                            word_notes.append(voice_notes[note_index])
                            durations.append(syllable_duration)
                        
                        lyrics_fragment = {
                            "text": word,
                            "notes": word_notes,
                            "start": i * word_duration,
                            "durations": durations
                        }
                    else:
                        # Single note for single syllable words
                        note_index = i % len(voice_notes)
                        lyrics_fragment = {
                            "text": word,
                            "notes": [voice_notes[note_index]],
                            "start": i * word_duration,
                            "duration": word_duration
                        }
                    
                    voice_lyrics.append(lyrics_fragment)
                
                # Add voice to voices array
                voice_obj = {
                    "voice_id": voice_id,
                    "lyrics": voice_lyrics
                }
                voices_array.append(voice_obj)
            
            # Add voices to the clip
            lyrics_clip["voices"] = voices_array
        
        # Add the clip to the target track
        target_track.setdefault("clips", []).append(lyrics_clip)
        
        # Update song metadata
        song["updatedAt"] = datetime.now().isoformat()
        song["duration"] = max(song.get("duration", 0), start_time + duration)
        
        return json.dumps(song, indent=2)
    
    except Exception as e:
        return f"Error adding lyrics: {str(e)}"


@tool
def create_multi_voice_lyrics(song_json: str, track_id: str, lyrics_text: str, start_time: float, 
                             duration: float, voice_parts: List[str] = None) -> str:
    """
    Create advanced multi-voice lyrics with proper voice distribution.
    
    Args:
        song_json: Current song structure as JSON string
        track_id: ID of the vocal track
        lyrics_text: The complete lyrics text
        start_time: Start time in seconds
        duration: Total duration in seconds
        voice_parts: List of voice types (e.g., ["soprano", "alto", "tenor", "bass"])
    
    Returns:
        Updated song structure with multi-voice lyrics
    """
    try:
        # Load available voices to select appropriate ones
        try:
            music_tools = MusicCompositionTools()
            available_voices = music_tools.available_voices
        except Exception as e:
            _safe_log_error(f"Error loading voices: {e}")
            available_voices = {}
        
        # Default voice parts if not provided
        if not voice_parts:
            voice_parts = ["soprano", "alto"]
        
        # Parse lyrics into words
        words = lyrics_text.split()
        
        # Distribute words among voices and assign actual voice IDs
        voices = []
        words_per_voice = len(words) // len(voice_parts)
        
        for i, voice_part in enumerate(voice_parts):
            start_word = i * words_per_voice
            if i == len(voice_parts) - 1:
                # Last voice gets remaining words
                word_count = len(words) - start_word
            else:
                word_count = words_per_voice
            
            # Find appropriate voice ID for this voice part
            selected_voice_id = None
            if available_voices:
                # Look for a voice that matches the desired range
                for voice_id, voice_info in available_voices.items():
                    if voice_info.get('range') == voice_part and voice_info.get('trained', False):
                        selected_voice_id = voice_id
                        break
                
                # If no exact match, find any trained voice
                if not selected_voice_id:
                    for voice_id, voice_info in available_voices.items():
                        if voice_info.get('trained', False):
                            selected_voice_id = voice_id
                            break
            
            # Fallback to default voice naming
            if not selected_voice_id:
                selected_voice_id = f"{voice_part}-01" if voice_part in ["soprano", "alto", "tenor", "bass"] else "default"
            
            voice_config = {
                "voice_id": selected_voice_id,
                "range": voice_part,
                "words_start": start_word,
                "words_count": word_count
            }
            voices.append(voice_config)
        
        # Use the advanced lyrics tool function directly
        return add_lyrics_to_track.func(
            song_json=song_json,
            track_id=track_id,
            lyrics_text=lyrics_text,
            start_time=start_time,
            duration=duration,
            voices=voices,
            simple_mode=False
        )
        
    except Exception as e:
        return f"Error creating multi-voice lyrics: {str(e)}"


@tool
def get_available_voices() -> str:
    """
    Get a list of all available voices that can be used for lyrics and vocals.
    
    Returns:
        JSON string with available voices and their characteristics
    """
    try:
        music_tools = MusicCompositionTools()
        available_voices = music_tools.available_voices
        
        # Format voices for easy reading
        voices_info = {}
        for voice_id, voice_info in available_voices.items():
            voices_info[voice_id] = {
                'name': voice_info.get('name', voice_id),
                'type': voice_info.get('type', 'unknown'),
                'range': voice_info.get('range', 'unknown'),
                'trained': voice_info.get('trained', False),
                'language': voice_info.get('language', 'en')
            }
        
        return json.dumps(voices_info, indent=2)
    
    except Exception as e:
        return f"Error getting available voices: {str(e)}"


