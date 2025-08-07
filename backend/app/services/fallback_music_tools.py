"""
Fallback music tools for LangGraph when the full music tools are not available
"""

from typing import Dict, List, Any


class FallbackMusicTools:
    """Simplified music tools for when the full LangChain tools are not available"""
    
    def __init__(self):
        self.available_instruments = self._get_default_instruments()
        self.available_samples = self._get_default_samples()
        self.available_voices = self._get_default_voices()
    
    def _get_default_instruments(self) -> Dict[str, List[str]]:
        """Provide default instrument lists"""
        return {
            "keyboards": ["piano", "organ", "electric_piano", "synthesizer"],
            "strings": ["guitar", "bass", "violin", "cello"],
            "percussion": ["drums", "tambourine", "shaker", "bells"],
            "woodwinds": ["flute", "clarinet", "saxophone"],
            "brass": ["trumpet", "trombone", "french_horn"],
            "vocal": ["vocals"],
            "synth": ["lead_synth", "pad_synth", "bass_synth"],
            "other": ["harmonica", "accordion"]
        }
    
    def _get_default_samples(self) -> Dict[str, Dict[str, List[str]]]:
        """Provide default sample lists"""
        return {
            "percussion": {"drums": ["kick", "snare", "hihat", "crash"]},
            "melodic": {"piano": ["c4", "d4", "e4", "f4", "g4"]},
            "harmonic": {"guitar": ["c_major", "f_major", "g_major"]}
        }
    
    def _get_default_voices(self) -> Dict[str, Dict[str, Any]]:
        """Provide default voice data"""
        return {
            "soprano01": {"name": "Soprano Voice", "range": "C4-C6"},
            "alto01": {"name": "Alto Voice", "range": "G3-G5"},
            "tenor01": {"name": "Tenor Voice", "range": "C3-C5"},
            "bass01": {"name": "Bass Voice", "range": "E2-E4"}
        }
    
    def format_instruments_for_prompt(self, instruments: Dict[str, List[str]]) -> str:
        """Format instruments for LLM prompts"""
        formatted = []
        for category, instrument_list in instruments.items():
            formatted.append(f"{category.title()}: {', '.join(instrument_list)}")
        return "\n".join(formatted)
    
    def format_voices_for_prompt(self, voices: Dict[str, Dict[str, Any]]) -> str:
        """Format voices for LLM prompts"""
        formatted = []
        for voice_id, voice_data in voices.items():
            name = voice_data.get('name', voice_id)
            range_info = voice_data.get('range', 'Unknown range')
            formatted.append(f"{voice_id}: {name} ({range_info})")
        return "\n".join(formatted)
