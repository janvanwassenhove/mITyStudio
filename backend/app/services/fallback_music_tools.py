"""
Fallback music tools for LangGraph when the full music tools are not available
"""

import os
import glob
from typing import Dict, List, Any
from app.api.sample_routes import get_user_samples_for_agents


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
