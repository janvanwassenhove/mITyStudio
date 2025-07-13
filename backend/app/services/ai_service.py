"""
AI Service
Handles AI-powered music composition and chat interactions
"""

import os
import json
import random
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
import openai
import anthropic
from flask import current_app


class AIService:
    """Service for AI interactions and music generation"""
    
    def __init__(self):
        self.openai_client = None
        self.anthropic_client = None
        self._initialize_clients()
    
    def _get_logger(self):
        """Get logger that works both inside and outside Flask context"""
        try:
            return current_app.logger
        except RuntimeError:
            # Outside Flask context, use basic logger
            return logging.getLogger(__name__)
    
    def _initialize_clients(self):
        """Initialize AI service clients"""
        openai_key = os.getenv('OPENAI_API_KEY')
        anthropic_key = os.getenv('ANTHROPIC_API_KEY')
        
        if openai_key:
            self.openai_client = openai.OpenAI(api_key=openai_key)
        
        if anthropic_key:
            self.anthropic_client = anthropic.Anthropic(api_key=anthropic_key)
    
    def _map_anthropic_model(self, model_id: str) -> str:
        """Map frontend model ID to actual Anthropic model name"""
        model_mapping = {
            'claude-4-sonnet': 'claude-3-5-sonnet-20241022',
            'claude-3-7-sonnet': 'claude-3-5-sonnet-20241022',
            'claude-3-5-sonnet-20241022': 'claude-3-5-sonnet-20241022',
            'claude-3-5-sonnet-20240620': 'claude-3-5-sonnet-20240620',
            'claude-3-5-haiku-20241022': 'claude-3-5-haiku-20241022',
            'claude-3-opus-20240229': 'claude-3-opus-20240229',
            'claude-3-sonnet-20240229': 'claude-3-sonnet-20240229',
            'claude-3-haiku-20240307': 'claude-3-haiku-20240307',
            'claude-2.1': 'claude-2.1',
            'claude-2.0': 'claude-2.0',
            'claude-instant-1.2': 'claude-instant-1.2'
        }
        return model_mapping.get(model_id, 'claude-3-5-sonnet-20241022')
    
    def _map_openai_model(self, model_id: str) -> str:
        """Map frontend model ID to actual OpenAI model name"""
        model_mapping = {
            'gpt-4o': 'gpt-4o',
            'gpt-4o-mini': 'gpt-4o-mini',
            'gpt-4-turbo': 'gpt-4-turbo',
            'gpt-4-turbo-preview': 'gpt-4-turbo-preview',
            'gpt-4-0125-preview': 'gpt-4-0125-preview',
            'gpt-4-1106-preview': 'gpt-4-1106-preview',
            'gpt-4': 'gpt-4',
            'gpt-4-0613': 'gpt-4-0613',
            'gpt-3.5-turbo': 'gpt-3.5-turbo',
            'gpt-3.5-turbo-0125': 'gpt-3.5-turbo-0125',
            'gpt-3.5-turbo-1106': 'gpt-3.5-turbo-1106',
            'gpt-3.5-turbo-16k': 'gpt-3.5-turbo-16k',
            'gpt-3.5-turbo-instruct': 'gpt-3.5-turbo-instruct'
        }
        return model_mapping.get(model_id, 'gpt-4o')
    
    def check_service_status(self) -> Dict[str, bool]:
        """Check which AI services are available"""
        return {
            'anthropic': bool(self.anthropic_client),
            'openai': bool(self.openai_client),
            'google': bool(os.getenv('GOOGLE_API_KEY')),
            'mistral': bool(os.getenv('MISTRAL_API_KEY')),
            'xai': bool(os.getenv('XAI_API_KEY'))
        }
    
    def chat_completion(self, message: str, provider: str = 'anthropic', 
                       model: str = 'claude-4-sonnet', context: Dict = None) -> Dict:
        """
        Generate AI chat response
        """
        if context is None:
            context = {}
            
        try:
            logger = self._get_logger()
            logger.info(f"AI chat request - Provider: {provider}, Model: {model}")
            
            if provider == 'anthropic' and self.anthropic_client:
                return self._anthropic_chat(message, model, context)
            elif provider == 'openai' and self.openai_client:
                return self._openai_chat(message, model, context)
            else:
                logger.warning(f"Provider {provider} not available or not configured")
                return self._fallback_response(message, context)
        
        except Exception as e:
            logger = self._get_logger()
            logger.error(f"AI chat error: {str(e)}")
            return self._fallback_response(message, context)
    
    def _anthropic_chat(self, message: str, model: str, context: Dict) -> Dict:
        """Handle Anthropic/Claude chat"""
        system_prompt = self._build_system_prompt(context)
        actual_model = self._map_anthropic_model(model)
        logger = self._get_logger()
        logger.info(f"Using Anthropic model: {actual_model}")
        
        response = self.anthropic_client.messages.create(
            model=actual_model,
            max_tokens=1000,
            system=system_prompt,
            messages=[{"role": "user", "content": message}]
        )
        
        content = response.content[0].text
        actions = self._extract_actions_from_response(content)
        
        return {
            'content': content,
            'actions': actions,
            'timestamp': datetime.utcnow().isoformat(),
            'provider': 'anthropic',
            'model': model
        }
    
    def _openai_chat(self, message: str, model: str, context: Dict) -> Dict:
        """Handle OpenAI/GPT chat"""
        system_prompt = self._build_system_prompt(context)
        actual_model = self._map_openai_model(model)
        logger = self._get_logger()
        logger.info(f"Using OpenAI model: {actual_model}")
        
        response = self.openai_client.chat.completions.create(
            model=actual_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message}
            ],
            max_tokens=1000
        )
        
        content = response.choices[0].message.content
        actions = self._extract_actions_from_response(content)
        
        return {
            'content': content,
            'actions': actions,
            'timestamp': datetime.utcnow().isoformat(),
            'provider': 'openai',
            'model': model
        }
    
    def _build_system_prompt(self, context: Dict = None) -> str:
        """Build system prompt for AI chat"""
        base_prompt = """You are an AI music composition assistant for mITyStudio. 
        You help users create music by providing advice on composition, arrangement, 
        production techniques, and music theory. You can suggest chord progressions, 
        melodies, instruments, and effects.
        
        When appropriate, suggest actionable items that can be implemented in the DAW.
        Be helpful, creative, and knowledgeable about music production."""
        
        if context:
            if context.get('tracks'):
                base_prompt += f"\n\nCurrent project has {len(context['tracks'])} tracks."
            if context.get('tempo'):
                base_prompt += f" Tempo: {context['tempo']} BPM."
            if context.get('key'):
                base_prompt += f" Key: {context['key']}."
        
        return base_prompt
    
    def _extract_actions_from_response(self, content: str) -> List[Dict]:
        """Extract actionable items from AI response"""
        actions = []
        
        # Look for specific patterns that suggest actions
        if "add" in content.lower() and ("chord" in content.lower() or "progression" in content.lower()):
            actions.append({
                'label': 'Add Chord Progression',
                'action': 'add_chord_progression',
                'icon': 'Plus'
            })
        
        if "add" in content.lower() and ("drum" in content.lower() or "beat" in content.lower()):
            actions.append({
                'label': 'Add Drum Pattern',
                'action': 'add_drum_pattern',
                'icon': 'Plus'
            })
        
        if "add" in content.lower() and "bass" in content.lower():
            actions.append({
                'label': 'Add Bass Track',
                'action': 'add_bass_track',
                'icon': 'Plus'
            })
        
        # Check for lyrics JSON in response
        if self._contains_lyrics_json(content):
            actions.append({
                'label': 'Add Lyrics to Song',
                'action': 'add_lyrics_json',
                'icon': 'Music',
                'data': self._extract_lyrics_json_data(content)
            })
        
        if "add" in content.lower() and ("lyrics" in content.lower() or "vocals" in content.lower()):
            actions.append({
                'label': 'Add Vocals',
                'action': 'add_vocals',
                'icon': 'Mic'
            })
        
        return actions
    
    def _fallback_response(self, message: str, context: Dict) -> Dict:
        """Fallback response when AI services are unavailable"""
        fallback_responses = [
            "I'd love to help you with your music! Unfortunately, AI services are currently unavailable. Try checking your API keys in the environment variables.",
            "AI services are temporarily unavailable. In the meantime, consider starting with a basic chord progression like C-Am-F-G!",
            "AI chat is offline right now. For music composition tips, try exploring different scales or adding some rhythm tracks to your project."
        ]
        
        content = random.choice(fallback_responses)
        
        return {
            'content': content,
            'actions': [],
            'timestamp': datetime.utcnow().isoformat(),
            'provider': 'fallback',
            'model': 'local'
        }
    
    def generate_chord_progression(self, genre: str, key: str, mood: str, complexity: str) -> Dict:
        """Generate chord progression based on parameters"""
        # Predefined chord progressions by genre
        progressions = {
            'pop': {
                'simple': ['I', 'V', 'vi', 'IV'],
                'complex': ['I', 'V', 'vi', 'iii', 'IV', 'I', 'IV', 'V']
            },
            'jazz': {
                'simple': ['ii7', 'V7', 'Imaj7'],
                'complex': ['Imaj7', 'vi7', 'ii7', 'V7', 'iii7', 'VI7', 'ii7', 'V7']
            },
            'rock': {
                'simple': ['i', 'VI', 'III', 'VII'],
                'complex': ['i', 'vi', 'III', 'VII', 'VI', 'IV', 'V', 'i']
            }
        }
        
        # Get progression pattern
        pattern = progressions.get(genre, progressions['pop']).get(complexity, ['I', 'V', 'vi', 'IV'])
        
        # Convert to actual chords based on key
        chord_map = self._get_chord_map(key)
        actual_chords = [chord_map.get(roman, roman) for roman in pattern]
        
        return {
            'chords': actual_chords,
            'pattern': pattern,
            'key': key,
            'genre': genre,
            'mood': mood,
            'complexity': complexity
        }
    
    def generate_melody(self, scale: str, key: str, tempo: int, style: str, chord_progression: List[str]) -> Dict:
        """Generate melody based on parameters"""
        # This is a simplified melody generation
        # In a real implementation, this would use more sophisticated AI models
        
        scales = {
            'major': [0, 2, 4, 5, 7, 9, 11],
            'minor': [0, 2, 3, 5, 7, 8, 10],
            'pentatonic': [0, 2, 4, 7, 9],
            'blues': [0, 3, 5, 6, 7, 10]
        }
        
        scale_notes = scales.get(scale, scales['major'])
        
        # Generate simple melody pattern
        melody_notes = []
        for i in range(16):  # 16 notes
            note_index = i % len(scale_notes)
            melody_notes.append(scale_notes[note_index])
        
        return {
            'notes': melody_notes,
            'scale': scale,
            'key': key,
            'tempo': tempo,
            'style': style,
            'duration': 16  # beats
        }
    
    def analyze_song_structure(self, tracks: List[Dict], structure: Dict) -> Dict:
        """Analyze song structure and provide feedback"""
        analysis = {
            'track_count': len(tracks),
            'instruments': [track.get('instrument', 'unknown') for track in tracks],
            'balance_score': 0.8,  # Simplified scoring
            'suggestions': [],
            'score': 75
        }
        
        # Add suggestions based on analysis
        if len(tracks) < 3:
            analysis['suggestions'].append("Consider adding more tracks for a fuller sound")
        
        if len(tracks) > 8:
            analysis['suggestions'].append("Many tracks - focus on mixing and arrangement")
        
        # Check for common instruments
        instruments = analysis['instruments']
        if 'drums' not in instruments:
            analysis['suggestions'].append("Add a drum track for rhythm foundation")
        
        if 'bass' not in instruments:
            analysis['suggestions'].append("Add a bass track for low-end foundation")
        
        return analysis
    
    def _is_monophonic_instrument(self, instrument: str, category: str = None) -> bool:
        """
        Check if an instrument is monophonic (single note) or polyphonic (can play chords)
        """
        monophonic_instruments = {
            'woodwinds': ['flute', 'saxophone', 'clarinet', 'oboe', 'bassoon', 'recorder'],
            'brass': ['trumpet', 'trombone', 'french horn', 'tuba', 'cornet'],
            'strings': ['violin', 'viola', 'cello', 'double bass'],  # Bowed strings are typically monophonic
            'general': ['flute', 'saxophone', 'trumpet', 'trombone', 'violin', 'cello', 'lead', 'solo']
        }
        
        instrument_lower = instrument.lower()
        
        # Check by category first
        if category and category.lower() in monophonic_instruments:
            category_instruments = monophonic_instruments[category.lower()]
            if any(mono_inst in instrument_lower for mono_inst in category_instruments):
                return True
        
        # Check general monophonic instruments
        for mono_inst in monophonic_instruments['general']:
            if mono_inst in instrument_lower:
                return True
        
        # Special cases for instrument names containing descriptive words
        if any(word in instrument_lower for word in ['lead', 'solo', 'melody', 'single']):
            return True
            
        return False
    
    def _get_polyphonic_alternatives(self, instrument: str, category: str = None) -> List[str]:
        """
        Suggest polyphonic alternatives for monophonic instruments
        """
        alternatives = {
            'woodwinds': ['piano', 'guitar', 'strings'],
            'brass': ['piano', 'guitar', 'strings'],
            'strings': ['piano', 'guitar'],  # For bowed strings
            'general': ['piano', 'guitar', 'strings', 'synth']
        }
        
        if category and category.lower() in alternatives:
            return alternatives[category.lower()]
        
        return alternatives['general']

    def suggest_instruments(self, genre: str, existing_instruments: List[str], mood: str, tempo: int, 
                          context: Dict = None, available_instruments: List[Dict] = None) -> Dict:
        """Suggest instruments based on context and available sample library"""
        
        # If we have available instruments, use them for suggestions
        if available_instruments:
            available_names = [inst['name'] for inst in available_instruments]
            category_mapping = {inst['name']: inst['category'] for inst in available_instruments}
            self._get_logger().info(f"Using available instruments: {available_names}")
        else:
            # Fallback to hardcoded suggestions
            available_names = ['guitar', 'piano', 'bass', 'drums', 'vocals', 'synth']
            category_mapping = {}
        
        # Updated instrument suggestions to match the sample library structure
        instrument_suggestions = {
            'pop': ['guitar', 'piano', 'bass', 'drums', 'vocals', 'synth'],
            'rock': ['guitar', 'electric_guitar', 'bass', 'drums', 'vocals'],
            'folk': ['guitar', 'acoustic_guitar', 'piano', 'vocals', 'strings'],
            'jazz': ['piano', 'guitar', 'bass', 'drums', 'saxophone', 'trumpet'],
            'electronic': ['synth', 'synth_lead', 'synth_pad', 'bass_synth', 'drums'],
            'classical': ['piano', 'strings', 'violin', 'cello', 'flute'],
            'country': ['guitar', 'acoustic_guitar', 'banjo', 'fiddle', 'vocals'],
            'blues': ['guitar', 'piano', 'bass', 'drums', 'harmonica'],
            'reggae': ['guitar', 'bass', 'drums', 'keyboard', 'vocals'],
            'funk': ['bass', 'guitar', 'drums', 'keyboard', 'vocals']
        }
        
        genre_instruments = instrument_suggestions.get(genre.lower(), instrument_suggestions['pop'])
        
        # Filter to only include instruments we actually have samples for
        available_genre_instruments = [inst for inst in genre_instruments if inst in available_names]
        missing_instruments = [inst for inst in available_genre_instruments if inst not in existing_instruments]
        
        # If no genre-specific instruments available, suggest any available instruments
        if not missing_instruments and available_instruments:
            missing_instruments = [inst['name'] for inst in available_instruments if inst['name'] not in existing_instruments][:5]
        
        # Prioritize based on mood and tempo
        mood_weights = {
            'happy': ['guitar', 'piano', 'synth'],
            'sad': ['piano', 'strings', 'guitar'],
            'energetic': ['drums', 'guitar', 'synth'],
            'calm': ['piano', 'strings', 'guitar'],
            'aggressive': ['guitar', 'bass', 'drums'],
            'romantic': ['piano', 'strings', 'guitar']
        }
        
        mood_preferred = mood_weights.get(mood.lower(), [])
        
        # Filter mood preferences to available instruments
        available_mood_preferred = [inst for inst in mood_preferred if inst in available_names]
        
        # Sort missing instruments by mood preference
        sorted_suggestions = []
        for pref in available_mood_preferred:
            if pref in missing_instruments:
                sorted_suggestions.append(pref)
                missing_instruments.remove(pref)
        sorted_suggestions.extend(missing_instruments)
        
        reasoning = f"For {genre} music with a {mood} mood"
        if tempo:
            if tempo > 140:
                reasoning += f" and fast tempo ({tempo} BPM)"
            elif tempo < 80:
                reasoning += f" and slow tempo ({tempo} BPM)"
            else:
                reasoning += f" and moderate tempo ({tempo} BPM)"
        
        reasoning += f", I recommend these instruments from your available sample library:"
        
        return {
            'suggestions': sorted_suggestions[:5],  # Top 5 suggestions
            'reasoning': reasoning,
            'available_count': len(available_names) if available_instruments else 0,
            'genre_matches': len(available_genre_instruments) if available_instruments else 0
        }
    
    def _get_chord_map(self, key: str) -> Dict[str, str]:
        """Get chord mapping for a given key"""
        # Simplified chord mapping
        major_keys = {
            'C': {'I': 'C', 'ii': 'Dm', 'iii': 'Em', 'IV': 'F', 'V': 'G', 'vi': 'Am', 'vii°': 'Bdim'},
            'G': {'I': 'G', 'ii': 'Am', 'iii': 'Bm', 'IV': 'C', 'V': 'D', 'vi': 'Em', 'vii°': 'F#dim'},
            'F': {'I': 'F', 'ii': 'Gm', 'iii': 'Am', 'IV': 'Bb', 'V': 'C', 'vi': 'Dm', 'vii°': 'Edim'}
        }
        
        return major_keys.get(key, major_keys['C'])
