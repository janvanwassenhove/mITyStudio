"""
Music composition tools and utilities for loading instruments, samples, and voices.
"""

import json
from typing import Dict, List, Any
from pathlib import Path

from .utils import safe_log_error

# Avoid importing VoiceService to prevent Flask context issues in background threads
VoiceService = None

# Flask-context-free versions of instrument scanning functions
def get_all_available_instruments_no_flask():
    """
    Get all available instruments from all categories in the sample library
    Flask-context-free version for use in background threads
    """
    try:
        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent.parent.parent
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
        project_root = current_file.parent.parent.parent.parent
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
        project_root = current_file.parent.parent.parent.parent
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
                instruments[category].append(instrument['display_name'])
            
            # Sort instruments alphabetically within each category
            for category in instruments:
                instruments[category].sort()
            
            safe_log_error(f"Loaded {sum(len(insts) for insts in instruments.values())} instruments across {len(instruments)} categories")
            return instruments
            
        except Exception as e:
            safe_log_error(f"Error loading instruments: {e}")
            # Fallback to hardcoded instruments
            return {
                'strings': ['Guitar', 'Bass', 'Violin', 'Cello'],
                'keyboards': ['Piano', 'Synth', 'Organ'],
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
                instrument_name = instrument['name']
                display_name = instrument['display_name']
                
                if category not in samples:
                    samples[category] = {}
                
                # Get chords/samples for this instrument
                chords = get_instrument_chords_no_flask(category, instrument_name)
                samples[category][display_name] = chords
            
            safe_log_error(f"Loaded samples for {len(all_instruments)} instruments")
            return samples
            
        except Exception as e:
            safe_log_error(f"Error loading samples: {e}")
            return {}
    
    def _load_available_voices(self) -> Dict[str, Dict[str, Any]]:
        """Load available voices from voice service"""
        try:
            if VoiceService is None:
                safe_log_error("VoiceService not available")
                return {}
            
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
        return "\n".join(formatted) if formatted else "No instruments available"
    
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
