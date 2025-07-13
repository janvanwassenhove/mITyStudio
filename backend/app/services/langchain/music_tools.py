"""
Music composition tools and utilities for loading instruments, samples, and voices.
"""

import json
from typing import Dict, List, Any
from pathlib import Path

from .utils import safe_log_error

try:
    from ..voice_service import VoiceService
except ImportError:
    VoiceService = None

# Import the standardized instrument scanning functions
try:
    from ...api.ai_routes import get_all_available_instruments, get_available_sample_instruments, get_instrument_chords
except ImportError:
    # Fallback functions if import fails
    def get_all_available_instruments():
        return []
    def get_available_sample_instruments(category):
        return []
    def get_instrument_chords(category, instrument):
        return []


class MusicCompositionTools:
    """Tools for music composition and song structure manipulation"""
    
    def __init__(self):
        self.available_instruments = self._load_available_instruments()
        self.available_samples = self._load_available_samples()
        self.available_voices = self._load_available_voices()
    
    def _load_available_instruments(self) -> Dict[str, List[str]]:
        """Load available instruments from sample library using standardized functions"""
        try:
            all_instruments = get_all_available_instruments()
            
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
            
            return instruments
            
        except Exception as e:
            safe_log_error(f"Error loading instruments: {e}")
            return {}
    
    def _load_available_samples(self) -> Dict[str, Dict[str, List[str]]]:
        """Load available samples from the sample library using standardized functions"""
        try:
            all_instruments = get_all_available_instruments()
            
            samples = {}
            for instrument in all_instruments:
                category = instrument['category']
                instrument_name = instrument['name']
                display_name = instrument['display_name']
                
                if category not in samples:
                    samples[category] = {}
                
                # Get chords/samples for this instrument
                chords = get_instrument_chords(category, instrument_name)
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
