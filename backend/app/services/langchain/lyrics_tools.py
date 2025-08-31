"""
LangChain tools for lyrics and voice handling.
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
from .utils import safe_log_error


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
        
        # Create the lyrics clip with exact required structure
        lyrics_clip = {
            "id": f"clip-lyrics-{uuid.uuid4().hex[:8]}",
            "trackId": track_id,
            "startTime": start_time,
            "duration": duration,
            "type": "lyrics",
            "instrument": "vocals",
            "volume": 0.8,
            "effects": {"reverb": 0, "delay": 0, "distortion": 0}
        }
        
        if simple_mode:
            # Simple structure for basic use cases
            melody_notes = _get_melody_notes_for_key(song_key, len(lyrics_words))
            
            # Simple structure - legacy compatibility
            lyrics_clip.update({
                "text": lyrics_text,
                "notes": melody_notes,
                "chordName": f"{song_key}_major" if not song_key.endswith('m') else f"{song_key[:-1]}_minor"
            })
        else:
            # Advanced multi-voice structure - REQUIRED FORMAT
            if not voices:
                voices = _get_default_voice_configuration(lyrics_words)
            
            # Generate voices array following exact specification
            voices_array = []
            
            for voice_config in voices:
                voice_id = voice_config.get("voice_id", "soprano01")
                voice_range = voice_config.get("range", "soprano")
                words_start = voice_config.get("words_start", 0)
                words_count = voice_config.get("words_count", len(lyrics_words))
                
                # Get notes for this voice range
                voice_notes = _get_voice_notes_for_range(voice_range, song_key)
                
                # Create lyrics fragments for this voice using EXACT structure
                voice_lyrics = _create_voice_lyrics_exact_format(
                    lyrics_words[words_start:words_start + words_count],
                    voice_notes,
                    duration,
                    start_time
                )
                
                # Add voice to voices array with exact structure
                voice_obj = {
                    "voice_id": voice_id,
                    "lyrics": voice_lyrics
                }
                voices_array.append(voice_obj)
            
            # Add voices to the clip following exact specification
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
    Create lyrics with multiple voice parts (soprano, alto, tenor, bass).
    
    Args:
        song_json: Current song structure as JSON string
        track_id: ID of the vocal track to add lyrics to
        lyrics_text: The lyrics text
        start_time: Start time in seconds
        duration: Total duration in seconds
        voice_parts: List of voice parts to use (e.g., ["soprano", "alto"])
    
    Returns:
        Updated song structure with multi-voice lyrics
    """
    try:
        if not voice_parts:
            voice_parts = ["soprano", "alto"]  # Default to SATB main parts
        
        # Load available voices
        music_tools = MusicCompositionTools()
        available_voices = music_tools.available_voices
        
        # Parse lyrics into words
        lyrics_words = lyrics_text.split()
        words_per_voice = len(lyrics_words) // len(voice_parts)
        
        voices = []
        for i, voice_part in enumerate(voice_parts):
            # Find appropriate voice for this part
            selected_voice_id = _find_voice_for_range(available_voices, voice_part)
            
            # Calculate word range for this voice
            start_word = i * words_per_voice
            word_count = words_per_voice
            if i == len(voice_parts) - 1:  # Last voice gets remaining words
                word_count = len(lyrics_words) - start_word
            
            voice_config = {
                "voice_id": selected_voice_id,
                "range": voice_part,
                "words_start": start_word,
                "words_count": word_count
            }
            voices.append(voice_config)
        
        # Use the advanced lyrics tool function directly
        return add_lyrics_to_track(
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


@tool
def create_lyrics_track_with_exact_structure(song_json: str, track_name: str = "Lyrics & Vocals", 
                                           lyrics_text: str = "", start_time: float = 0.0, 
                                           duration: float = 4.0, voice_parts: List[str] = None) -> str:
    """
    Create a complete lyrics track with exact JSON structure following the specification.
    
    Args:
        song_json: Current song structure as JSON string
        track_name: Name for the lyrics track (default: "Lyrics & Vocals")
        lyrics_text: Initial lyrics text to add
        start_time: Start time for initial lyrics clip
        duration: Duration for initial lyrics clip
        voice_parts: List of voice parts to use (e.g., ["soprano01", "alto01"])
    
    Returns:
        Updated song structure with correctly formatted lyrics track
    """
    try:
        # Handle both dict and string inputs
        if isinstance(song_json, dict):
            song = song_json
        else:
            song = json.loads(song_json)
        
        # Create lyrics track with exact structure
        track_id = f"track-lyrics-{uuid.uuid4().hex[:8]}"
        lyrics_track = {
            "id": track_id,
            "name": track_name,
            "instrument": "vocals",
            "category": "vocals",
            "volume": 0.8,
            "pan": 0,
            "muted": False,
            "solo": False,
            "clips": [],
            "effects": {"reverb": 0, "delay": 0, "distortion": 0}
        }
        
        # Add the track to the song
        song.setdefault("tracks", []).append(lyrics_track)
        
        # If lyrics text is provided, add initial clip with exact structure
        if lyrics_text.strip():
            # Use default voice parts if not specified
            if not voice_parts:
                voice_parts = ["soprano01"]
                
            # Get song key for note generation
            song_key = song.get('key', 'C')
            
            # Parse lyrics into words
            lyrics_words = lyrics_text.split()
            
            # Create the lyrics clip with exact required structure
            lyrics_clip = {
                "id": f"clip-lyrics-{uuid.uuid4().hex[:8]}",
                "trackId": track_id,
                "startTime": start_time,
                "duration": duration,
                "type": "lyrics",
                "instrument": "vocals",
                "volume": 0.8,
                "effects": {"reverb": 0, "delay": 0, "distortion": 0}
            }
            
            # Create voices array with exact structure
            voices_array = []
            words_per_voice = len(lyrics_words) // len(voice_parts) if voice_parts else len(lyrics_words)
            
            for i, voice_id in enumerate(voice_parts):
                # Calculate word range for this voice
                start_word = i * words_per_voice
                end_word = start_word + words_per_voice
                if i == len(voice_parts) - 1:  # Last voice gets remaining words
                    end_word = len(lyrics_words)
                    
                voice_words = lyrics_words[start_word:end_word]
                if not voice_words:
                    continue
                    
                # Get voice range from voice_id
                voice_range = _get_range_from_voice_id(voice_id)
                voice_notes = _get_voice_notes_for_range(voice_range, song_key)
                
                # Create lyrics fragments with exact format
                voice_lyrics = _create_voice_lyrics_exact_format(
                    voice_words, voice_notes, duration, start_time
                )
                
                # Add voice with exact structure
                voice_obj = {
                    "voice_id": voice_id,
                    "lyrics": voice_lyrics
                }
                voices_array.append(voice_obj)
            
            # Add voices to the clip
            lyrics_clip["voices"] = voices_array
            
            # Add clip to track
            lyrics_track["clips"].append(lyrics_clip)
        
        # Update song metadata
        song["updatedAt"] = datetime.now().isoformat()
        if lyrics_text:
            song["duration"] = max(song.get("duration", 0), start_time + duration)
        
        return json.dumps(song, indent=2)
        
    except Exception as e:
        return f"Error creating lyrics track: {str(e)}"


@tool
def validate_lyrics_json_structure(lyrics_clip_json: str) -> str:
    """
    Validate that a lyrics clip follows the exact required JSON structure.
    
    Args:
        lyrics_clip_json: JSON string of a lyrics clip to validate
        
    Returns:
        Validation result with any issues found
    """
    try:
        if isinstance(lyrics_clip_json, dict):
            clip = lyrics_clip_json
        else:
            clip = json.loads(lyrics_clip_json)
        
        issues = []
        
        # Check required top-level fields
        required_fields = ["id", "trackId", "startTime", "duration", "type", "instrument", "volume", "effects"]
        for field in required_fields:
            if field not in clip:
                issues.append(f"Missing required field: {field}")
        
        # Check clip type and instrument
        if clip.get("type") != "lyrics":
            issues.append(f"Clip type should be 'lyrics', got '{clip.get('type')}'")
        
        if clip.get("instrument") != "vocals":
            issues.append(f"Instrument should be 'vocals', got '{clip.get('instrument')}'")
        
        # Check effects structure
        effects = clip.get("effects", {})
        required_effects = ["reverb", "delay", "distortion"]
        for effect in required_effects:
            if effect not in effects:
                issues.append(f"Missing effect: {effect}")
        
        # Check voices array structure
        if "voices" in clip:
            voices = clip["voices"]
            if not isinstance(voices, list):
                issues.append("'voices' should be an array")
            else:
                for i, voice in enumerate(voices):
                    if not isinstance(voice, dict):
                        issues.append(f"Voice {i} should be an object")
                        continue
                    
                    if "voice_id" not in voice:
                        issues.append(f"Voice {i} missing 'voice_id'")
                    
                    if "lyrics" not in voice:
                        issues.append(f"Voice {i} missing 'lyrics' array")
                        continue
                    
                    # Check lyrics fragments
                    for j, fragment in enumerate(voice["lyrics"]):
                        if not isinstance(fragment, dict):
                            issues.append(f"Voice {i}, fragment {j} should be an object")
                            continue
                        
                        fragment_required = ["text", "notes", "start"]
                        for field in fragment_required:
                            if field not in fragment:
                                issues.append(f"Voice {i}, fragment {j} missing '{field}'")
                        
                        # Check duration vs durations
                        has_duration = "duration" in fragment
                        has_durations = "durations" in fragment
                        
                        if not has_duration and not has_durations:
                            issues.append(f"Voice {i}, fragment {j} must have either 'duration' or 'durations'")
                        elif has_duration and has_durations:
                            issues.append(f"Voice {i}, fragment {j} cannot have both 'duration' and 'durations'")
                        
                        # Check notes array
                        notes = fragment.get("notes", [])
                        if not isinstance(notes, list):
                            issues.append(f"Voice {i}, fragment {j} 'notes' should be an array")
                        elif len(notes) > 1 and has_duration:
                            issues.append(f"Voice {i}, fragment {j} has multiple notes but uses 'duration' instead of 'durations'")
                        elif len(notes) == 1 and has_durations:
                            issues.append(f"Voice {i}, fragment {j} has single note but uses 'durations' instead of 'duration'")
        
        if issues:
            return f"JSON Structure Issues Found:\n" + "\n".join(f"- {issue}" for issue in issues)
        else:
            return "✓ JSON structure is valid and follows the required format."
        
    except json.JSONDecodeError as e:
        return f"Invalid JSON: {str(e)}"
    except Exception as e:
        return f"Validation error: {str(e)}"


def _get_melody_notes_for_key(song_key: str, num_words: int) -> List[str]:
    """Get melody notes based on song key"""
    if song_key.startswith('C'):
        base_notes = ["C4", "D4", "E4", "F4", "G4", "A4", "B4"]
    elif song_key.startswith('G'):
        base_notes = ["G4", "A4", "B4", "C5", "D5", "E5", "F#5"]
    elif song_key.startswith('F'):
        base_notes = ["F4", "G4", "A4", "Bb4", "C5", "D5", "E5"]
    else:
        base_notes = ["C4", "D4", "E4", "F4", "G4", "A4", "B4"]
    
    # Assign notes to words
    melody_notes = []
    for i in range(num_words):
        note_index = i % len(base_notes)
        melody_notes.append(base_notes[note_index])
    
    return melody_notes


def _get_default_voice_configuration(lyrics_words: List[str]) -> List[Dict]:
    """Get default voice configuration"""
    try:
        music_tools = MusicCompositionTools()
        available_voices = music_tools.available_voices
        
        # Default voice configuration using actual available voices
        if available_voices:
            # Find the best voice for lead vocals (prefer female voice for soprano range)
            lead_voice = None
            for voice_id, voice_info in available_voices.items():
                if voice_info.get('range', '').lower() in ['soprano', 'alto'] and voice_info.get('trained', False):
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
            
            return [
                {"voice_id": selected_voice_id, "range": selected_voice_range, "words_start": 0, "words_count": len(lyrics_words)}
            ]
        else:
            return [
                {"voice_id": "default", "range": "soprano", "words_start": 0, "words_count": len(lyrics_words)}
            ]
    except Exception as e:
        safe_log_error(f"Error loading voices for lyrics: {e}")
        return [
            {"voice_id": "default", "range": "soprano", "words_start": 0, "words_count": len(lyrics_words)}
        ]


def _get_voice_notes_for_range(voice_range: str, song_key: str) -> List[str]:
    """Get notes for a specific voice range and key"""
    if voice_range == "soprano":
        if song_key.startswith('C'):
            return ["E4", "F4", "G4", "A4", "B4", "C5", "D5"]
        elif song_key.startswith('G'):
            return ["B4", "C5", "D5", "E5", "F#5", "G5", "A5"]
        else:
            return ["E4", "F4", "G4", "A4", "B4", "C5", "D5"]
    elif voice_range == "alto":
        if song_key.startswith('C'):
            return ["C4", "D4", "E4", "F4", "G4", "A4", "B4"]
        elif song_key.startswith('G'):
            return ["G4", "A4", "B4", "C5", "D5", "E5", "F#5"]
        else:
            return ["C4", "D4", "E4", "F4", "G4", "A4", "B4"]
    elif voice_range == "tenor":
        if song_key.startswith('C'):
            return ["G3", "A3", "B3", "C4", "D4", "E4", "F4"]
        elif song_key.startswith('G'):
            return ["D4", "E4", "F#4", "G4", "A4", "B4", "C5"]
        else:
            return ["G3", "A3", "B3", "C4", "D4", "E4", "F4"]
    elif voice_range == "bass":
        if song_key.startswith('C'):
            return ["C3", "D3", "E3", "F3", "G3", "A3", "B3"]
        elif song_key.startswith('G'):
            return ["G3", "A3", "B3", "C4", "D4", "E4", "F#4"]
        else:
            return ["C3", "D3", "E3", "F3", "G3", "A3", "B3"]
    else:
        # Default to soprano range
        return ["E4", "F4", "G4", "A4", "B4", "C5", "D5"]


def _create_voice_lyrics_exact_format(voice_words: List[str], voice_notes: List[str], 
                                     duration: float, start_time: float, section_id: str = None) -> List[Dict]:
    """Create lyrics fragments for a voice following EXACT JSON specification format with extended structure"""
    voice_lyrics = []
    
    # Calculate timing for each word
    word_duration = duration / len(voice_words) if voice_words else 1.0
    
    for i, word in enumerate(voice_words):
        # Determine if word has multiple syllables (simple heuristic)
        syllable_count = max(1, len([c for c in word if c.lower() in 'aeiou']))
        
        if syllable_count > 1:
            # Multi-syllable word - split across notes following exact format
            syllable_duration = word_duration / syllable_count
            syllables = [word[:len(word)//2], word[len(word)//2:]]  # Simple split
            
            # Follow exact format: notes array + durations array for multi-note
            fragment = {
                "text": word,
                "notes": voice_notes[:len(syllables)],
                "start": i * word_duration,
                "durations": [syllable_duration] * len(syllables)
            }
        else:
            # Single syllable - follow exact format: single note + duration (not array)
            fragment = {
                "text": word,
                "notes": [voice_notes[i % len(voice_notes)]],
                "start": i * word_duration,
                "duration": word_duration  # Single duration for single note
            }
        
        # Add extended structure: syllables breakdown
        fragment["syllables"] = _generate_syllable_breakdown_for_word(word, fragment.get("notes", []), 
                                                                     fragment.get("durations", fragment.get("duration", word_duration)))
        
        # Add phonemes for TTS/singing engines
        fragment["phonemes"] = _generate_phonemes_for_word(word)
        
        voice_lyrics.append(fragment)
    
    return voice_lyrics


def _create_voice_lyrics(voice_words: List[str], voice_notes: List[str], 
                        duration: float, start_time: float) -> List[Dict]:
    """Create lyrics fragments for a voice"""
    voice_lyrics = []
    
    # Calculate timing for each word
    word_duration = duration / len(voice_words) if voice_words else 1.0
    
    for i, word in enumerate(voice_words):
        # Determine if word has multiple syllables (simple heuristic)
        syllable_count = max(1, len([c for c in word if c.lower() in 'aeiou']))
        
        if syllable_count > 1:
            # Multi-syllable word - split across notes
            syllable_duration = word_duration / syllable_count
            syllables = [word[:len(word)//2], word[len(word)//2:]]  # Simple split
            durations = [syllable_duration] * len(syllables)
            notes = voice_notes[:len(syllables)]
        else:
            # Single syllable
            syllables = [word]
            durations = [word_duration]
            notes = [voice_notes[i % len(voice_notes)]]
        
        fragment = {
            "text": word,
            "notes": notes,
            "start": i * word_duration,
            "durations": durations if len(durations) > 1 else durations[0]
        }
        voice_lyrics.append(fragment)
    
    return voice_lyrics


def _generate_syllable_breakdown_for_word(word: str, notes: List[str], durations) -> List[Dict[str, Any]]:
    """
    Generate syllable breakdown for a single word with note mapping.
    
    Args:
        word: Word to split into syllables
        notes: List of notes for this word
        durations: Duration(s) for the notes
        
    Returns:
        List of syllable dictionaries with note mapping
    """
    try:
        # Simple syllable detection (can be enhanced with proper phonetic libraries)
        word_syllables = _split_word_into_syllables(word)
        syllables = []
        
        # Ensure durations is always a list
        if not isinstance(durations, list):
            durations = [durations]
        
        note_index = 0
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
            else:
                note_indices = [0]  # Fallback to first note
            
            duration = durations[note_indices[0]] if note_indices[0] < len(durations) else 0.3
            
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
        safe_log_error(f"Error generating syllable breakdown for word '{word}': {e}")
        return [{"t": word, "noteIdx": [0], "dur": 1.0}]


def _split_word_into_syllables(word: str) -> List[str]:
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


def _generate_phonemes_for_word(word: str) -> List[str]:
    """
    Generate IPA phonemes for a single word for TTS/singing engines.
    This is a basic implementation - for production use, consider proper IPA libraries.
    
    Args:
        word: The word to convert to phonemes
        
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
        
        word_lower = word.lower()
        phonemes = []
        
        i = 0
        while i < len(word_lower):
            # Check for two-character combinations first
            if i + 1 < len(word_lower):
                two_char = word_lower[i:i+2]
                if two_char in phoneme_map:
                    phonemes.append(phoneme_map[two_char])
                    i += 2
                    continue
            
            # Single character
            char = word_lower[i]
            if char in phoneme_map:
                phonemes.append(phoneme_map[char])
            else:
                phonemes.append(char)  # Keep unknown characters as-is
            i += 1
        
        return phonemes
        
    except Exception as e:
        safe_log_error(f"Error generating phonemes for word '{word}': {e}")
        # Fallback: return characters as basic phonemes
        return list(word.lower())


def _find_voice_for_range(available_voices: Dict[str, Dict], voice_range: str) -> str:
    """Find appropriate voice for a given range"""
    # Look for exact range match
    for voice_id, voice_info in available_voices.items():
        if voice_info.get('range', '').lower() == voice_range.lower():
            return voice_id
    
    # Fallback to any available voice
    if available_voices:
        return list(available_voices.keys())[0]
    
    # Ultimate fallback
    return "default"


def _get_range_from_voice_id(voice_id: str) -> str:
    """Extract voice range from voice_id"""
    voice_id_lower = voice_id.lower()
    if 'soprano' in voice_id_lower:
        return 'soprano'
    elif 'alto' in voice_id_lower:
        return 'alto'
    elif 'tenor' in voice_id_lower:
        return 'tenor'
    elif 'bass' in voice_id_lower:
        return 'bass'
    else:
        return 'soprano'  # Default


@tool
def integrate_ai_lyrics_response(song_json: str, ai_response: str, target_track_id: str = None) -> str:
    """
    Integrate AI-generated lyrics JSON response into the song structure.
    Automatically detects and applies lyrics JSON from AI assistant responses.
    
    Args:
        song_json: Current song structure as JSON string
        ai_response: AI assistant response that may contain lyrics JSON
        target_track_id: Optional specific track ID to add lyrics to
        
    Returns:
        Updated song structure with integrated lyrics, or error message
    """
    try:
        # Handle both dict and string inputs
        if isinstance(song_json, dict):
            song = song_json
        else:
            song = json.loads(song_json)
        
        # Try to extract JSON from AI response
        extracted_json = _extract_lyrics_json_from_response(ai_response)
        
        if not extracted_json:
            return "No valid lyrics JSON found in AI response to integrate."
        
        # Determine what type of JSON we extracted
        integration_result = _integrate_extracted_json(song, extracted_json, target_track_id)
        
        if integration_result["success"]:
            # Update song metadata
            song["updatedAt"] = datetime.now().isoformat()
            return json.dumps(song, indent=2)
        else:
            return f"Integration failed: {integration_result['error']}"
            
    except Exception as e:
        return f"Error integrating AI lyrics response: {str(e)}"


@tool
def apply_ai_generated_lyrics(song_json: str, lyrics_json: str, integration_mode: str = "auto") -> str:
    """
    Apply AI-generated lyrics JSON directly to song structure with validation.
    
    Args:
        song_json: Current song structure as JSON string
        lyrics_json: AI-generated lyrics JSON (track or clip format)
        integration_mode: "auto", "new_track", "existing_track", or "clip_only"
        
    Returns:
        Updated song structure with applied lyrics
    """
    try:
        # Handle both dict and string inputs
        if isinstance(song_json, dict):
            song = song_json
        else:
            song = json.loads(song_json)
        
        if isinstance(lyrics_json, str):
            lyrics_data = json.loads(lyrics_json)
        else:
            lyrics_data = lyrics_json
        
        # Validate the lyrics JSON structure first
        validation_result = _validate_ai_lyrics_structure(lyrics_data)
        if not validation_result["valid"]:
            return f"Invalid lyrics JSON structure: {validation_result['errors']}"
        
        # Apply based on integration mode
        if integration_mode == "auto":
            result = _auto_integrate_lyrics(song, lyrics_data)
        elif integration_mode == "new_track":
            result = _integrate_as_new_track(song, lyrics_data)
        elif integration_mode == "existing_track":
            result = _integrate_to_existing_track(song, lyrics_data)
        elif integration_mode == "clip_only":
            result = _integrate_clip_only(song, lyrics_data)
        else:
            return f"Unknown integration mode: {integration_mode}"
        
        if result["success"]:
            # Update song metadata
            song["updatedAt"] = datetime.now().isoformat()
            return json.dumps(song, indent=2)
        else:
            return f"Integration failed: {result['error']}"
            
    except Exception as e:
        return f"Error applying AI generated lyrics: {str(e)}"


def _extract_lyrics_json_from_response(response: str) -> dict:
    """Extract lyrics JSON from AI response text"""
    try:
        # Look for JSON blocks in the response
        import re
        
        # Pattern to find JSON blocks
        json_patterns = [
            r'```json\s*([\s\S]*?)\s*```',  # JSON code blocks
            r'```\s*([\s\S]*?)\s*```',      # Generic code blocks
            r'\{[\s\S]*\}',                  # Direct JSON objects
        ]
        
        for pattern in json_patterns:
            matches = re.findall(pattern, response)
            for match in matches:
                try:
                    # Try to parse as JSON
                    json_data = json.loads(match)
                    
                    # Check if it looks like lyrics data
                    if _is_lyrics_json(json_data):
                        return json_data
                        
                except json.JSONDecodeError:
                    continue
        
        return None
        
    except Exception:
        return None


def _is_lyrics_json(data: dict) -> bool:
    """Check if JSON data contains lyrics structure"""
    if not isinstance(data, dict):
        return False
    
    # Check for track structure with vocals
    if (data.get("instrument") == "vocals" or 
        data.get("category") == "vocals" or
        "clips" in data):
        return True
    
    # Check for clip structure with lyrics
    if (data.get("type") == "lyrics" and
        data.get("instrument") == "vocals"):
        return True
    
    # Check for voices array (direct lyrics structure)
    if "voices" in data and isinstance(data["voices"], list):
        return True
    
    return False


def _validate_ai_lyrics_structure(data: dict) -> dict:
    """Validate AI-generated lyrics structure"""
    try:
        errors = []
        
        # If it's a track structure
        if "clips" in data:
            if data.get("instrument") != "vocals":
                errors.append("Track instrument should be 'vocals'")
            if data.get("category") != "vocals":
                errors.append("Track category should be 'vocals'")
            
            # Validate clips
            for i, clip in enumerate(data.get("clips", [])):
                clip_errors = _validate_lyrics_clip(clip)
                if clip_errors:
                    errors.extend([f"Clip {i}: {err}" for err in clip_errors])
        
        # If it's a clip structure
        elif data.get("type") == "lyrics":
            clip_errors = _validate_lyrics_clip(data)
            errors.extend(clip_errors)
        
        # If it's just voices array
        elif "voices" in data:
            voice_errors = _validate_voices_array(data["voices"])
            errors.extend(voice_errors)
        
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }
        
    except Exception as e:
        return {
            "valid": False,
            "errors": [f"Validation error: {str(e)}"]
        }


def _validate_lyrics_clip(clip: dict) -> list:
    """Validate a single lyrics clip"""
    errors = []
    
    required_fields = ["type", "instrument"]
    for field in required_fields:
        if field not in clip:
            errors.append(f"Missing required field: {field}")
    
    if clip.get("type") != "lyrics":
        errors.append("Clip type must be 'lyrics'")
    
    if clip.get("instrument") != "vocals":
        errors.append("Clip instrument must be 'vocals'")
    
    if "voices" in clip:
        voice_errors = _validate_voices_array(clip["voices"])
        errors.extend(voice_errors)
    
    return errors


def _validate_voices_array(voices: list) -> list:
    """Validate voices array structure"""
    errors = []
    
    if not isinstance(voices, list):
        return ["Voices must be an array"]
    
    for i, voice in enumerate(voices):
        if not isinstance(voice, dict):
            errors.append(f"Voice {i} must be an object")
            continue
        
        if "voice_id" not in voice:
            errors.append(f"Voice {i} missing voice_id")
        
        if "lyrics" not in voice:
            errors.append(f"Voice {i} missing lyrics array")
            continue
        
        # Validate lyrics fragments
        for j, fragment in enumerate(voice["lyrics"]):
            fragment_errors = _validate_lyrics_fragment(fragment)
            if fragment_errors:
                errors.extend([f"Voice {i}, fragment {j}: {err}" for err in fragment_errors])
    
    return errors


def _validate_lyrics_fragment(fragment: dict) -> list:
    """Validate a single lyrics fragment"""
    errors = []
    
    required_fields = ["text", "notes", "start"]
    for field in required_fields:
        if field not in fragment:
            errors.append(f"Missing {field}")
    
    # Check duration/durations logic
    has_duration = "duration" in fragment
    has_durations = "durations" in fragment
    
    if not has_duration and not has_durations:
        errors.append("Must have either 'duration' or 'durations'")
    elif has_duration and has_durations:
        errors.append("Cannot have both 'duration' and 'durations'")
    
    # Check notes array consistency
    notes = fragment.get("notes", [])
    if isinstance(notes, list):
        if len(notes) > 1 and has_duration:
            errors.append("Multiple notes require 'durations' array")
        elif len(notes) == 1 and has_durations:
            errors.append("Single note should use 'duration' field")
    
    return errors


def _integrate_extracted_json(song: dict, lyrics_data: dict, target_track_id: str = None) -> dict:
    """Integrate extracted lyrics JSON into song"""
    try:
        # Determine integration strategy based on data structure
        if "clips" in lyrics_data:
            # It's a complete track
            return _integrate_as_new_track(song, lyrics_data)
        elif lyrics_data.get("type") == "lyrics":
            # It's a clip
            return _integrate_clip_only(song, lyrics_data, target_track_id)
        elif "voices" in lyrics_data:
            # It's a voices structure - create a clip
            clip_data = {
                "id": f"clip-lyrics-{uuid.uuid4().hex[:8]}",
                "type": "lyrics",
                "instrument": "vocals",
                "volume": 0.8,
                "startTime": 0.0,
                "duration": 4.0,
                "effects": {"reverb": 0, "delay": 0, "distortion": 0},
                "voices": lyrics_data["voices"]
            }
            return _integrate_clip_only(song, clip_data, target_track_id)
        else:
            return {"success": False, "error": "Unknown lyrics JSON structure"}
            
    except Exception as e:
        return {"success": False, "error": str(e)}


def _auto_integrate_lyrics(song: dict, lyrics_data: dict) -> dict:
    """Automatically determine best integration method"""
    # Check if there are existing vocal tracks
    vocal_tracks = [track for track in song.get("tracks", []) 
                   if track.get("category") == "vocals" or track.get("instrument") == "vocals"]
    
    if vocal_tracks and "clips" not in lyrics_data:
        # Add to existing vocal track
        return _integrate_to_existing_track(song, lyrics_data)
    else:
        # Create new track
        return _integrate_as_new_track(song, lyrics_data)


def _integrate_as_new_track(song: dict, lyrics_data: dict) -> dict:
    """Integrate as a new vocal track"""
    try:
        if "clips" in lyrics_data:
            # It's already a complete track
            track = lyrics_data.copy()
            if "id" not in track:
                track["id"] = f"track-lyrics-{uuid.uuid4().hex[:8]}"
        else:
            # Create track from clip/voices data
            track = {
                "id": f"track-lyrics-{uuid.uuid4().hex[:8]}",
                "name": "AI Generated Lyrics",
                "instrument": "vocals",
                "category": "vocals",
                "volume": 0.8,
                "pan": 0,
                "muted": False,
                "solo": False,
                "clips": [],
                "effects": {"reverb": 0, "delay": 0, "distortion": 0}
            }
            
            # Create clip from the data
            if lyrics_data.get("type") == "lyrics":
                clip = lyrics_data.copy()
            else:
                clip = {
                    "id": f"clip-lyrics-{uuid.uuid4().hex[:8]}",
                    "type": "lyrics",
                    "instrument": "vocals",
                    "volume": 0.8,
                    "startTime": 0.0,
                    "duration": 4.0,
                    "effects": {"reverb": 0, "delay": 0, "distortion": 0}
                }
                if "voices" in lyrics_data:
                    clip["voices"] = lyrics_data["voices"]
            
            clip["trackId"] = track["id"]
            track["clips"].append(clip)
        
        # Add track to song
        song.setdefault("tracks", []).append(track)
        
        return {"success": True}
        
    except Exception as e:
        return {"success": False, "error": str(e)}


def _integrate_to_existing_track(song: dict, lyrics_data: dict, track_id: str = None) -> dict:
    """Integrate to existing vocal track"""
    try:
        # Find target track
        target_track = None
        if track_id:
            target_track = next((track for track in song.get("tracks", []) 
                               if track.get("id") == track_id), None)
        else:
            # Find first vocal track
            target_track = next((track for track in song.get("tracks", []) 
                               if track.get("category") == "vocals" or track.get("instrument") == "vocals"), None)
        
        if not target_track:
            return {"success": False, "error": "No suitable vocal track found"}
        
        # Create clip from lyrics data
        if lyrics_data.get("type") == "lyrics":
            clip = lyrics_data.copy()
        else:
            clip = {
                "id": f"clip-lyrics-{uuid.uuid4().hex[:8]}",
                "type": "lyrics",
                "instrument": "vocals",
                "volume": 0.8,
                "startTime": 0.0,
                "duration": 4.0,
                "effects": {"reverb": 0, "delay": 0, "distortion": 0}
            }
            if "voices" in lyrics_data:
                clip["voices"] = lyrics_data["voices"]
        
        clip["trackId"] = target_track["id"]
        target_track.setdefault("clips", []).append(clip)
        
        return {"success": True}
        
    except Exception as e:
        return {"success": False, "error": str(e)}


def _integrate_clip_only(song: dict, clip_data: dict, target_track_id: str = None) -> dict:
    """Integrate as clip only to existing track"""
    try:
        # Find target track
        target_track = None
        if target_track_id:
            target_track = next((track for track in song.get("tracks", []) 
                               if track.get("id") == target_track_id), None)
        else:
            # Find first vocal track
            target_track = next((track for track in song.get("tracks", []) 
                               if track.get("category") == "vocals" or track.get("instrument") == "vocals"), None)
        
        if not target_track:
            return {"success": False, "error": "No suitable vocal track found for clip integration"}
        
        # Prepare clip
        clip = clip_data.copy()
        clip["trackId"] = target_track["id"]
        if "id" not in clip:
            clip["id"] = f"clip-lyrics-{uuid.uuid4().hex[:8]}"
        
        # Add clip to track
        target_track.setdefault("clips", []).append(clip)
        
        return {"success": True}
        
    except Exception as e:
        return {"success": False, "error": str(e)}
