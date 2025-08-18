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
        
        logger = self._get_logger()
        
        if openai_key:
            try:
                # Create OpenAI client with explicit minimal configuration
                # to avoid any parameter conflicts from environment or global state
                self.openai_client = openai.OpenAI(
                    api_key=openai_key
                )
                logger.info("OpenAI client initialized successfully")
            except Exception as e:
                logger.error(f"OpenAI client initialization failed: {e}")
                # Set to None but continue - we can still use Anthropic
                self.openai_client = None
        else:
            logger.info("No OpenAI API key provided")
            self.openai_client = None
        
        if anthropic_key:
            try:
                self.anthropic_client = anthropic.Anthropic(api_key=anthropic_key)
                logger.info("Anthropic client initialized successfully")
            except Exception as e:
                logger.error(f"Anthropic client initialization failed: {e}")
                self.anthropic_client = None
        else:
            logger.info("No Anthropic API key provided")
            self.anthropic_client = None
            
        # Ensure at least one client is available
        if not self.openai_client and not self.anthropic_client:
            logger.warning("No AI clients available - service will use fallback responses")
    
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
        Generate AI chat response using direct OpenAI/Anthropic clients
        """
        if context is None:
            context = {}
            
        # Check if user is asking about samples specifically
        if self._is_sample_question(message):
            return self._handle_sample_question(message, provider, model, context)
            
        try:
            logger = self._get_logger()
            logger.info(f"AI chat request - Provider: {provider}, Model: {model}")
            
            # Use direct AI clients for all requests (LangChain temporarily disabled)
            if provider == 'anthropic' and self.anthropic_client:
                return self._anthropic_chat(message, model, context)
            elif provider == 'openai' and self.openai_client:
                return self._openai_chat(message, model, context)
            elif self.anthropic_client:
                # Fallback to Anthropic if requested provider is not available
                logger.info(f"Falling back to Anthropic since {provider} is not available")
                return self._anthropic_chat(message, model, context)
            elif self.openai_client:
                # Fallback to OpenAI if Anthropic is not available
                logger.info(f"Falling back to OpenAI since {provider} is not available")
                return self._openai_chat(message, model, context)
            else:
                logger.warning(f"No AI clients available")
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

        AVAILABLE SAMPLE LIBRARY:
        The studio has an extensive sample library with instruments organized by categories:
        - Brass: trumpet, trombone, french_horn, tuba
        - Keyboards: piano, electric_piano, organ, synth
        - Percussion: drums, timpani, xylophone, marimba  
        - Strings: violin, viola, cello, double_bass, guitar, electric_guitar
        - Synth: synth_lead, synth_pad, synth_bass, synth_arp
        - Vocal: various vocal samples and voice types
        - Woodwinds: flute, clarinet, saxophone, oboe

        Each instrument has chord samples in multiple keys and variations. Always suggest 
        instruments that are actually available in the sample library.

        CURRENT PROJECT CONTEXT:"""
        
        if context:
            if context.get('tracks'):
                tracks = context.get('tracks', [])
                base_prompt += f"\n- Current project has {len(tracks)} tracks"
                instruments = [track.get('instrument', 'unknown') for track in tracks]
                base_prompt += f"\n- Current instruments: {', '.join(set(instruments))}"
            
            if context.get('tempo'):
                base_prompt += f"\n- Tempo: {context['tempo']} BPM"
                
            if context.get('key'):
                base_prompt += f"\n- Key: {context['key']}"
                
            if context.get('song_structure'):
                structure = context.get('song_structure', {})
                if structure.get('sections'):
                    sections = [section.get('name', 'Unknown') for section in structure.get('sections', [])]
                    base_prompt += f"\n- Song sections: {', '.join(sections)}"

        base_prompt += """

        When appropriate, suggest actionable items that can be implemented in the DAW.
        Be helpful, creative, and knowledgeable about music production.

        IMPORTANT: When users ask about instruments, chord progressions, or song structure,
        be aware of what's currently available in their project and what instruments
        are available in the sample library.

CRITICAL: When creating song text, lyrics, or vocals, you MUST provide them in the following exact JSON structure:

LYRICS TRACK STRUCTURE:
```json
{
  "id": "track-lyrics",
  "name": "Lyrics & Vocals", 
  "instrument": "vocals",
  "category": "vocals",
  "volume": 0.8,
  "pan": 0,
  "muted": false,
  "solo": false,
  "clips": [...],
  "effects": { "reverb": 0, "delay": 0, "distortion": 0 }
}
```

LYRICS CLIP STRUCTURE (REQUIRED FORMAT):
```json
{
  "id": "clip-lyrics-1",
  "trackId": "track-lyrics", 
  "startTime": 4,
  "duration": 2,
  "type": "lyrics",
  "instrument": "vocals",
  "volume": 0.8,
  "effects": { "reverb": 0, "delay": 0, "distortion": 0 },
  "voices": [
    {
      "voice_id": "soprano01",
      "lyrics": [
        {
          "text": "Shine",
          "notes": ["E4", "F4"],
          "start": 0.0,
          "durations": [0.4, 0.4]
        },
        {
          "text": "on", 
          "notes": ["G4"],
          "start": 1.0,
          "duration": 0.6
        }
      ]
    }
  ]
}
```

IMPORTANT RULES FOR LYRICS:
- ALWAYS provide lyrics in the above JSON format when asked to create lyrics or vocals
- Use "voices" array for multi-voice structure
- Each voice has "voice_id" and "lyrics" array
- Each lyric fragment has "text", "notes", "start", and either "duration" (single note) OR "durations" (multiple notes)
- For single notes: use "duration" (number)
- For multiple notes: use "durations" (array of numbers)
- Always set effects to { "reverb": 0, "delay": 0, "distortion": 0 } unless specified
- Use proper voice_ids like "soprano01", "alto01", "tenor01", "bass01"
- Generate appropriate musical notes (e.g., C4, D4, E4, F4, G4, A4, B4) based on the song key
- Calculate start times and durations that make musical sense"""
        
        if context and context.get('tempo'):
            base_prompt += f"\n- Use the current tempo ({context['tempo']} BPM) to calculate appropriate durations for lyrics timing."
        if context and context.get('key'):
            base_prompt += f"\n- Generate notes that fit the current key ({context['key']}) for the lyrics."
        
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
    
    def _is_music_related(self, message: str, context: Dict = None) -> bool:
        """Check if the message is music-related and should use LangChain tools"""
        
        # First, check if we have song structure context - strong indicator
        if context and 'song_structure' in context:
            return True
        
        # Define music-specific keywords (more specific to avoid false positives)
        music_keywords = [
            # Specific composition terms
            'chord progression', 'melody', 'harmony', 'rhythm pattern', 'beat', 'tempo', 
            'musical key', 'scale', 'chord', 'progression',
            'verse', 'chorus', 'bridge', 'intro', 'outro', 'song structure',
            
            # Musical instruments (specific contexts)
            'guitar', 'piano', 'drums', 'bass guitar', 'violin', 'vocals', 'synthesizer', 
            'keyboard', 'trumpet', 'saxophone', 'flute', 'organ', 'string section',
            
            # Music production terms
            'music track', 'mix music', 'master track', 'audio effect', 'reverb', 
            'musical arrangement', 'song composition', 'music production',
            
            # Song/music specific phrases
            'my song', 'this track', 'music piece', 'composition', 'arrange music',
            'produce music', 'record music', 'musical instrument', 'song writing',
            'music theory', 'musical note', 'music studio', 'audio recording'
        ]
        
        message_lower = message.lower()
        
        # Check for specific music phrases and keywords
        for keyword in music_keywords:
            if keyword in message_lower:
                return True
        
        # Also check for individual instrument names when used in musical context
        instruments = ['guitar', 'piano', 'drums', 'bass', 'violin', 'vocals', 'synth', 'keyboard']
        music_contexts = ['add', 'suggest', 'use', 'play', 'include', 'need', 'want', 'help with']
        
        for instrument in instruments:
            if instrument in message_lower:
                for context_word in music_contexts:
                    if context_word in message_lower:
                        return True
        
        # Check for musical action words combined with general terms
        music_actions = ['compose', 'arrange', 'mix', 'produce', 'create music', 'write song']
        for action in music_actions:
            if action in message_lower:
                return True
        
        # Not music-related
        return False
    
    def _langchain_music_chat(self, message: str, provider: str, model: str, context: Dict) -> Dict:
        """Use LangChain service for enhanced music assistance"""
        try:
            # Import LangChain service conditionally to avoid startup errors
            from app.services.langchain_service import LangChainService
            
            langchain_service = LangChainService()
            
            # Extract song structure from context
            song_structure = context.get('song_structure')
            if not song_structure and context.get('tracks'):
                # Build basic song structure from tracks if available
                song_structure = {
                    'tracks': context.get('tracks', []),
                    'tempo': context.get('tempo', 120),
                    'key': context.get('key', 'C'),
                    'sections': context.get('sections', [])
                }
            
            # Use LangChain service for music-aware chat
            result = langchain_service.chat_with_music_assistant(
                message=message,
                song_structure=song_structure,
                provider=provider
            )
            
            # Transform LangChain response to match expected format
            return {
                'content': result['response'],
                'actions': self._extract_actions_from_response(result['response']),
                'timestamp': datetime.utcnow().isoformat(),
                'provider': provider,
                'model': model,
                'updated_song_structure': result.get('updated_song_structure'),
                'tools_used': result.get('tools_used', []),
                'success': result.get('success', True)
            }
            
        except (ImportError, RuntimeError) as e:
            # LangChain service not available due to dependency issues
            # Provide music-aware fallback response instead of failing
            logger = self._get_logger()
            logger.warning(f"LangChain not available, using music-aware fallback: {e}")
            return self._music_aware_fallback(message, context, provider, model)
        except Exception as e:
            # Any other error with LangChain - also use fallback
            logger = self._get_logger()
            logger.error(f"LangChain service error, using fallback: {str(e)}")
            return self._music_aware_fallback(message, context, provider, model)

    def _music_aware_fallback(self, message: str, context: Dict, provider: str, model: str) -> Dict:
        """Provide music-aware fallback responses when LangChain is unavailable"""
        
        # Analyze the song context if available
        song_structure = context.get('song_structure', {})
        tracks = song_structure.get('tracks', [])
        tempo = song_structure.get('tempo', 120)
        key = song_structure.get('key', 'C')
        
        message_lower = message.lower()
        
        # Generate context-aware responses based on the request type
        if 'instrument' in message_lower or 'suggest' in message_lower:
            if tracks:
                existing_instruments = [track.get('instrument', 'unknown') for track in tracks]
                response = f"I can see your song has {len(tracks)} track(s) with {', '.join(existing_instruments)}. "
                
                if 'drum' in message_lower:
                    response += "Consider uploading drum samples for rhythmic foundation."
                elif 'bass' in message_lower:
                    response += "Bass would complement your existing tracks well."
                elif 'guitar' in message_lower:
                    response += "Guitar could add harmonic richness to your composition."
                elif 'piano' in message_lower:
                    response += "Piano could provide melodic foundation."
                else:
                    response += "Consider adding drums for rhythm, bass for foundation, or lead instruments for melody."
            else:
                response = "For a new song, start with a rhythm section (drums), add bass for foundation, then layer melodic instruments."
        
        elif 'chord' in message_lower or 'progression' in message_lower:
            if key:
                response = f"For a song in {key}, try these chord progressions: {key}-Am-F-G (pop), {key}-F-G-Am (emotional), or {key}-Em-F-G (uplifting)."
            else:
                response = "Popular chord progressions include C-Am-F-G, Am-F-C-G, or Em-C-G-D. These work well in most genres."
        
        elif 'tempo' in message_lower:
            current_tempo = f" Your current tempo is {tempo} BPM." if tempo else ""
            response = f"Tempo suggestions: Ballad (60-80 BPM), Pop (120-140 BPM), Rock (120-160 BPM), Dance (120-130 BPM).{current_tempo}"
        
        elif 'structure' in message_lower:
            response = "Common song structures: Verse-Chorus-Verse-Chorus-Bridge-Chorus, or Intro-Verse-Chorus-Verse-Chorus-Outro."
        
        elif 'mix' in message_lower or 'volume' in message_lower:
            response = "Mixing tips: Start with levels (drums loud, bass clear, vocals prominent), add EQ to separate frequencies, use reverb for space."
        
        else:
            # Generic music help
            response = f"I can help with your music composition! "
            if tracks:
                response += f"Your song currently has {len(tracks)} tracks. "
            response += "Ask me about chord progressions, song structure, instrument suggestions, or mixing tips."
        
        # Add note about limited functionality
        response += " (Note: AI assistant temporarily unavailable: Agent not available)"
        
        return {
            'content': response,
            'actions': [],
            'timestamp': datetime.utcnow().isoformat(),
            'provider': provider,
            'model': model,
            'tools_used': [],
            'updated_song_structure': None,
            'success': False  # Indicate this is a fallback response
        }

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

    def _contains_lyrics_json(self, content: str) -> bool:
        """Check if the AI response contains lyrics JSON structure"""
        try:
            import re
            
            # Look for JSON patterns that might contain lyrics
            json_patterns = [
                r'```json\s*([\s\S]*?)\s*```',  # JSON code blocks
                r'```\s*([\s\S]*?)\s*```',      # Generic code blocks
                r'\{[\s\S]*?"voices"\s*:[\s\S]*?\}',  # Direct voices structure
                r'\{[\s\S]*?"type"\s*:\s*"lyrics"[\s\S]*?\}',  # Lyrics clip structure
                r'\{[\s\S]*?"instrument"\s*:\s*"vocals"[\s\S]*?\}',  # Vocals instrument
                r'\{[\s\S]*?"category"\s*:\s*"vocals"[\s\S]*?\}'     # Vocals category
            ]
            
            for pattern in json_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE | re.DOTALL)
                for match in matches:
                    try:
                        # Try to parse as JSON
                        json_data = json.loads(match)
                        
                        # Check if it contains lyrics-related structures
                        if self._is_lyrics_json_structure(json_data):
                            return True
                            
                    except json.JSONDecodeError:
                        continue
            
            # Also check for explicit mentions of lyrics with structured content
            lyrics_indicators = [
                r'lyrics?\s*:',
                r'voices?\s*:',
                r'"text"\s*:',
                r'"notes"\s*:',
                r'"duration"?\s*:',
                r'voice_id'
            ]
            
            json_like_content = re.search(r'\{[\s\S]*\}', content)
            if json_like_content:
                json_content = json_like_content.group()
                if any(re.search(indicator, json_content, re.IGNORECASE) for indicator in lyrics_indicators):
                    # Try to find complete JSON structures
                    potential_jsons = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', content)
                    for potential_json in potential_jsons:
                        try:
                            parsed = json.loads(potential_json)
                            if self._is_lyrics_json_structure(parsed):
                                return True
                        except json.JSONDecodeError:
                            continue
            
            return False
            
        except Exception:
            return False
    
    def _is_lyrics_json_structure(self, data: dict) -> bool:
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
            # Validate that voices contain lyrics structure
            for voice in data["voices"]:
                if isinstance(voice, dict):
                    if "voice_id" in voice and "lyrics" in voice:
                        lyrics = voice["lyrics"]
                        if isinstance(lyrics, list) and lyrics:
                            # Check if lyrics contain proper structure
                            sample_lyric = lyrics[0]
                            if (isinstance(sample_lyric, dict) and 
                                "text" in sample_lyric and 
                                "notes" in sample_lyric):
                                return True
            return True
        
        # Check for lyrics array directly (in case it's a voice object)
        if "lyrics" in data and isinstance(data["lyrics"], list):
            if data["lyrics"]:
                sample_lyric = data["lyrics"][0]
                if (isinstance(sample_lyric, dict) and 
                    "text" in sample_lyric and 
                    "notes" in sample_lyric):
                    return True
        
        # Check for individual lyric fragment
        if (isinstance(data, dict) and 
            "text" in data and 
            "notes" in data and 
            ("duration" in data or "durations" in data)):
            return True
        
        return False
    
    def _extract_lyrics_json_data(self, content: str) -> dict:
        """Extract lyrics JSON data from AI response"""
        try:
            import re
            
            # Pattern to find JSON blocks with improved matching
            json_patterns = [
                r'```json\s*([\s\S]*?)\s*```',  # JSON code blocks
                r'```\s*([\s\S]*?)\s*```',      # Generic code blocks
                r'\{(?:[^{}]|(?:\{(?:[^{}]|\{[^{}]*\})*\}))*\}',  # Nested JSON objects
            ]
            
            found_jsons = []
            
            for pattern in json_patterns:
                matches = re.findall(pattern, content, re.DOTALL)
                for match in matches:
                    try:
                        # Try to parse as JSON
                        json_data = json.loads(match)
                        
                        # Check if it contains lyrics data
                        if self._is_lyrics_json_structure(json_data):
                            found_jsons.append({
                                'json': json_data,
                                'raw': match,
                                'integration_mode': 'auto'
                            })
                            
                    except json.JSONDecodeError:
                        continue
            
            # If we found multiple JSON objects, prefer the most complete one
            if found_jsons:
                # Sort by completeness (prefer tracks over clips over fragments)
                def json_completeness_score(json_obj):
                    data = json_obj['json']
                    score = 0
                    
                    # Track structure gets highest score
                    if 'clips' in data and data.get('instrument') == 'vocals':
                        score += 100
                    
                    # Clip structure gets medium score
                    elif data.get('type') == 'lyrics' and 'voices' in data:
                        score += 50
                    
                    # Voice/lyrics array gets lower score
                    elif 'voices' in data or 'lyrics' in data:
                        score += 25
                    
                    # Add bonus for completeness
                    if 'startTime' in data:
                        score += 10
                    if 'duration' in data:
                        score += 10
                    if 'effects' in data:
                        score += 5
                    
                    return score
                
                found_jsons.sort(key=json_completeness_score, reverse=True)
                return found_jsons[0]
            
            return {}
            
        except Exception:
            return {}

    def _is_sample_question(self, message: str) -> bool:
        """Check if user is asking about available samples"""
        message_lower = message.lower()
        sample_keywords = ['samples', 'sample', 'audio files', 'loops', 'beats']
        question_words = ['what', 'which', 'show', 'list', 'available', 'have', 'can i use', 'can use']
        
        # Check if message contains sample-related keywords and question words
        has_sample_keyword = any(keyword in message_lower for keyword in sample_keywords)
        has_question_word = any(word in message_lower for word in question_words)
        
        return has_sample_keyword and has_question_word

    def _handle_sample_question(self, message: str, provider: str, model: str, context: Dict) -> Dict:
        """Enhanced handler for questions about available samples using AI metadata"""
        try:
            # Import locally to avoid circular import
            from app.api.sample_routes import get_user_samples_for_agents
            
            # Get enhanced user samples from the backend
            user_samples_data = get_user_samples_for_agents()
            
            if user_samples_data and user_samples_data.get('all_samples'):
                all_samples = user_samples_data['all_samples']
                summary = user_samples_data.get('summary', {})
                
                # Analyze the user's question to provide targeted recommendations
                message_lower = message.lower()
                
                # Initialize response content
                sample_list = []
                recommendations = []
                
                # Check for specific requests
                if any(word in message_lower for word in ['vocal', 'voice', 'singing']):
                    vocal_samples = [s for s in all_samples if s.get('track_type') in ['vocals', 'vocals_and_instrumentals']]
                    if vocal_samples:
                        sample_list.append("🎤 **Vocal Samples:**")
                        for sample in vocal_samples[:5]:
                            sample_list.append(self._format_enhanced_sample(sample))
                        recommendations.append("Try layering vocal samples with instrumentals to create depth in your track.")
                
                elif any(word in message_lower for word in ['drum', 'beat', 'rhythm']):
                    drum_samples = [s for s in all_samples if 'drums' in s.get('primary_category', '').lower() or 'drum' in ' '.join(s.get('instrument_tags', [])).lower()]
                    if drum_samples:
                        sample_list.append("🥁 **Drum & Percussion:**")
                        for sample in drum_samples[:5]:
                            sample_list.append(self._format_enhanced_sample(sample))
                        recommendations.append("For strong rhythms, try combining kick and snare patterns with hi-hat loops.")
                
                elif any(word in message_lower for word in ['energetic', 'upbeat', 'high energy']):
                    energetic_samples = [s for s in all_samples if s.get('energy_level', 0) > 0.7]
                    if energetic_samples:
                        sample_list.append("⚡ **High Energy Samples:**")
                        for sample in energetic_samples[:5]:
                            sample_list.append(self._format_enhanced_sample(sample))
                        recommendations.append("High energy samples work great for drops, choruses, and dance sections.")
                
                elif any(word in message_lower for word in ['chill', 'relaxed', 'ambient']):
                    chill_samples = [s for s in all_samples if s.get('vibe') in ['chill', 'smooth', 'dreamy'] or s.get('energy_level', 0) < 0.4]
                    if chill_samples:
                        sample_list.append("😌 **Chill & Ambient:**")
                        for sample in chill_samples[:5]:
                            sample_list.append(self._format_enhanced_sample(sample))
                        recommendations.append("Chill samples are perfect for verses, intros, and atmospheric layers.")
                
                elif any(word in message_lower for word in ['bass', 'low end']):
                    bass_samples = [s for s in all_samples if 'bass' in s.get('primary_category', '').lower() or 'bass' in ' '.join(s.get('instrument_tags', [])).lower()]
                    if bass_samples:
                        sample_list.append("🔊 **Bass Samples:**")
                        for sample in bass_samples[:5]:
                            sample_list.append(self._format_enhanced_sample(sample))
                        recommendations.append("Strong bass lines form the foundation of most modern music genres.")
                
                # If no specific category found, show a overview
                if not sample_list:
                    # Group by categories
                    categories = user_samples_data.get('by_category', {})
                    total_samples = summary.get('total_samples', 0)
                    
                    sample_list.append(f"🎵 **Your Sample Library ({total_samples} samples):**\n")
                    
                    for category, samples in list(categories.items())[:4]:  # Show top 4 categories
                        if samples:
                            sample_list.append(f"**{category.title()} ({len(samples)} samples):**")
                            for sample in samples[:3]:  # Top 3 per category
                                sample_list.append(self._format_enhanced_sample(sample))
                            if len(samples) > 3:
                                sample_list.append(f"  • ... and {len(samples) - 3} more\n")
                
                # Add intelligent recommendations based on sample analysis
                if summary.get('has_vocals', 0) > 0 and summary.get('instrumentals_only', 0) > 0:
                    recommendations.append("You have both vocals and instrumentals - try combining them for rich, layered tracks!")
                
                if summary.get('avg_bpm', 0) > 0:
                    avg_bpm = int(summary['avg_bpm'])
                    if avg_bpm > 130:
                        recommendations.append(f"Your samples average {avg_bpm} BPM - great for energetic dance and electronic music!")
                    elif avg_bpm < 100:
                        recommendations.append(f"Your samples average {avg_bpm} BPM - perfect for hip-hop, chill, and downtempo styles!")
                    else:
                        recommendations.append(f"Your samples average {avg_bpm} BPM - versatile for pop, rock, and contemporary styles!")
                
                # Check for genre diversity
                genres = list(user_samples_data.get('by_genre', {}).keys())
                if len(genres) > 3:
                    recommendations.append(f"You have samples across {len(genres)} genres - try mixing styles for unique sounds!")
                
                # Build final response
                content = "\n".join(sample_list)
                
                if recommendations:
                    content += f"\n\n💡 **AI Recommendations:**\n• " + "\n• ".join(recommendations)
                
                content += "\n\n🎵 Click the play button next to any sample to preview it, or use the + button to add it to a new track!"
                
            else:
                content = """I don't see any uploaded audio samples in your project yet. 

To use samples in your music, you can:

1. **Upload Audio Files**: Go to the Sample Library and upload your audio files
2. **Automatic AI Tagging**: Once uploaded, I'll automatically analyze your samples for:
   - Track type (vocals, instrumentals, or both)
   - Vibe & mood (energetic, chill, dark, etc.)
   - Instrument detection (drums, bass, guitar, etc.)
   - Genre classification and key detection
   - BPM and energy level analysis

3. **Smart Recommendations**: I'll suggest the best samples based on the style you're creating

Would you like to upload some samples so I can help you create music with them?"""

            return {
                'content': content,
                'actions': [],
                'timestamp': datetime.utcnow().isoformat(),
                'provider': provider,
                'model': model
            }
            
        except Exception as e:
            # Fallback response
            return {
                'content': "I'm having trouble accessing your sample library right now. Please try refreshing the page or check if you have any samples uploaded in the Sample Library section.",
                'actions': [],
                'timestamp': datetime.utcnow().isoformat(),
                'provider': provider,
                'model': model
            }
    
    def _format_enhanced_sample(self, sample: Dict) -> str:
        """Format a sample with enhanced AI metadata for display"""
        name = sample.get('name', 'Unknown Sample')
        duration = sample.get('duration', 0)
        bpm = sample.get('bpm')
        vibe = sample.get('vibe')
        track_type = sample.get('track_type')
        key = sample.get('key')
        
        # Format duration
        minutes = int(duration // 60)
        seconds = int(duration % 60)
        duration_str = f"{minutes}:{seconds:02d}"
        
        # Build sample info
        info_parts = [duration_str]
        if bpm:
            info_parts.append(f"{int(bpm)} BPM")
        if key:
            info_parts.append(key)
        if vibe and vibe != 'unknown':
            info_parts.append(vibe.replace('_', ' ').title())
        
        # Add track type indicator
        type_emoji = ""
        if track_type == 'vocals':
            type_emoji = "🎤 "
        elif track_type == 'instrumentals':
            type_emoji = "🎵 "
        elif track_type == 'vocals_and_instrumentals':
            type_emoji = "🎤🎵 "
        
        return f"  • {type_emoji}**{name}** ({', '.join(info_parts)})"
