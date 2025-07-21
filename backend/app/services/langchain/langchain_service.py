"""
LangChain Service
Handles advanced AI interactions using LangChain framework with React Agent for music composition
"""

import os
import json
import re
from typing import Dict, List, Any, Optional
from datetime import datetime
import uuid

try:
    from langchain_openai import ChatOpenAI
    from langchain_anthropic import ChatAnthropic
    from langchain.agents import create_react_agent, AgentExecutor
    from langchain.tools import BaseTool, tool
    from langchain.schema import HumanMessage, SystemMessage
    from langchain.prompts import PromptTemplate
    from langchain.memory import ConversationBufferMemory
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.tools import Tool
except ImportError:
    # Fallback for older langchain versions
    try:
        from langchain.chat_models import ChatOpenAI, ChatAnthropic
        from langchain.agents import create_react_agent, AgentExecutor
        from langchain.tools import BaseTool, tool
        from langchain.schema import HumanMessage, SystemMessage
        from langchain.prompts import PromptTemplate
        from langchain.memory import ConversationBufferMemory
        from langchain_core.prompts import ChatPromptTemplate
    except ImportError:
        # Basic fallback without advanced features
        ChatOpenAI = None
        ChatAnthropic = None
        create_react_agent = None
        AgentExecutor = None
        BaseTool = None

from .utils import safe_log_error, get_chord_progression_for_key, get_intro_chords_for_key, get_bass_notes_for_key
from .music_tools import MusicCompositionTools
from .song_tools import *
from .lyrics_tools import *


class LangChainService:
    """Service for advanced AI interactions using LangChain with React Agent"""
    
    def __init__(self):
        self.chat_openai = None
        self.chat_anthropic = None
        self.agent_executor = None
        self.memory = None
        
        # Initialize models and agent
        self._initialize_models()
        self._setup_react_agent()

    def _initialize_models(self):
        """Initialize LangChain models"""
        try:
            # OpenAI setup with error handling for proxy issues
            openai_api_key = os.getenv('OPENAI_API_KEY')
            if openai_api_key and ChatOpenAI:
                try:
                    # Initialize with minimal parameters to avoid proxy conflicts
                    self.chat_openai = ChatOpenAI(
                        openai_api_key=openai_api_key,
                        model_name="gpt-4",
                        temperature=0.7,
                        max_retries=2
                    )
                except Exception as e:
                    safe_log_error(f"ChatOpenAI initialization failed: {e}")
                    self.chat_openai = None
                
            # Anthropic setup
            anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')
            if anthropic_api_key and ChatAnthropic:
                try:
                    # Initialize with minimal parameters to avoid proxy conflicts
                    self.chat_anthropic = ChatAnthropic(
                        anthropic_api_key=anthropic_api_key,
                        model="claude-3-sonnet-20240229",
                        temperature=0.7,
                        max_retries=2
                    )
                except Exception as e:
                    safe_log_error(f"ChatAnthropic initialization failed: {e}")
                    self.chat_anthropic = None
                
        except Exception as e:
            safe_log_error(f"Error initializing LangChain models: {e}")
    
    def _setup_react_agent(self):
        """Setup the React Agent with music composition tools"""
        try:
            # Choose the primary model
            if self.chat_anthropic:
                llm = self.chat_anthropic
            elif self.chat_openai:
                llm = self.chat_openai
            else:
                safe_log_error("No LangChain models available")
                return

            # Collect all tools
            tools = [
                analyze_song_structure,
                get_available_instruments,
                get_available_samples,
                create_track,
                add_clip_to_track,
                generate_chord_progression,
                create_song_section,
                modify_song_structure,
                add_lyrics_to_track,
                create_multi_voice_lyrics,
                create_lyrics_track_with_exact_structure,
                validate_lyrics_json_structure,
                integrate_ai_lyrics_response,
                apply_ai_generated_lyrics,
                get_available_voices
            ]
            
            # Create agent prompt with detailed JSON structure specification
            try:
                from langchain import hub
                prompt = hub.pull("hwchase17/react")
            except ImportError:
                # Fallback prompt with detailed lyrics JSON structure specification
                prompt = ChatPromptTemplate.from_messages([
                    ("system", """You are a music composition assistant. You help users create, modify, and enhance their musical compositions.

CRITICAL: When generating lyrics and vocals, you MUST follow this exact JSON structure for lyrics tracks and clips:

LYRICS TRACK STRUCTURE:
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

LYRICS CLIP STRUCTURE (REQUIRED FORMAT):
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

IMPORTANT RULES FOR LYRICS:
- Use "voices" array for multi-voice structure
- Each voice has "voice_id" and "lyrics" array
- Each lyric fragment has "text", "notes", "start", and either "duration" (single note) OR "durations" (multiple notes)
- For single notes: use "duration" (number)
- For multiple notes: use "durations" (array of numbers)
- Always set effects to { "reverb": 0, "delay": 0, "distortion": 0 } unless specified
- Use proper voice_ids like "soprano01", "alto01", "tenor01", "bass01"

AI INTEGRATION FEATURES:
- When you generate lyrics JSON, the user can automatically integrate it into their song
- Use integrate_ai_lyrics_response to detect and apply JSON from responses
- Use apply_ai_generated_lyrics for direct JSON application
- Always offer integration options when providing lyrics JSON
- Validate structure before integration using validate_lyrics_json_structure

You have access to the following tools:
{tools}

Use the tools to help users with their music composition needs. Always use tools when appropriate to provide accurate information about available instruments, create tracks, add clips, generate chord progressions, and manage song structure.

Tool names: {tool_names}

Question: {input}
Thought: {agent_scratchpad}"""),
                    ("human", "{input}")
                ])
            
            # Create the agent
            try:
                agent = create_react_agent(llm, tools, prompt)
            except Exception as e:
                safe_log_error(f"Error creating React agent: {e}")
                try:
                    # Fallback agent creation for older versions
                    from langchain.agents import initialize_agent, AgentType
                    agent = initialize_agent(
                        tools, llm, agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION, verbose=False
                    )
                except ImportError:
                    safe_log_error("Could not create agent with fallback method")
                    return
            
            # Create the agent executor
            self.agent_executor = AgentExecutor(
                agent=agent,
                tools=tools,
                verbose=False,
                max_iterations=5,
                handle_parsing_errors=True,
                return_intermediate_steps=True
            )
            
        except Exception as e:
            try:
                safe_log_error(f"React agent setup failed: {e}")
            except RuntimeError:
                print(f"React agent setup failed: {e}")
    
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
                return self._fallback_response(message, song_structure, "Agent not available")
            
            # Build enhanced context with song structure analysis
            input_context = self._build_enhanced_context(message, song_structure)
            
            # Execute the agent with better error handling
            try:
                result = self.agent_executor.invoke({"input": input_context})
                response = result.get("output", "I couldn't process that request.")
                
                # Try to extract updated song structure from response
                updated_structure = self._extract_json_from_response(response)
                
                return {
                    'response': response,
                    'updated_song_structure': updated_structure,
                    'provider': provider,
                    'success': True
                }
                
            except StopIteration as e:
                safe_log_error(f"Agent execution stopped: {e}")
                return self._fallback_response(message, song_structure, "Agent execution stopped")
            
            except Exception as agent_error:
                safe_log_error(f"Agent execution error: {agent_error}")
                return self._fallback_response(message, song_structure, str(agent_error))
            
        except Exception as e:
            safe_log_error(f"Music assistant chat error: {str(e)}")
            return self._fallback_response(message, song_structure, str(e))

    def _build_enhanced_context(self, message: str, song_structure: Dict = None) -> str:
        """Build enhanced context that includes song structure analysis and guidance for the agent"""
        context_parts = [message]
        
        # Add JSON structure reminder for lyrics
        context_parts.append(f"\n\nIMPORTANT: When creating lyrics and vocals, ALWAYS use the exact JSON structure specified in the system prompt.")
        context_parts.append("For lyrics clips, use the 'voices' array format with proper voice_ids (soprano01, alto01, etc.).")
        context_parts.append("Use 'duration' for single notes and 'durations' array for multiple notes per lyric fragment.")
        
        # Add integration guidance
        context_parts.append("\nAI INTEGRATION: When you provide lyrics JSON, offer integration options:")
        context_parts.append("- Use integrate_ai_lyrics_response to auto-detect and apply JSON from your responses")
        context_parts.append("- Use apply_ai_generated_lyrics for direct JSON application with validation")
        context_parts.append("- Always validate structure before integration")
        
        if song_structure:
            # Add current song structure
            context_parts.append(f"\n\nCURRENT SONG STRUCTURE:")
            context_parts.append(json.dumps(song_structure, indent=2))
            
            # Add analysis prompt to guide the agent
            analysis_prompt = self._build_song_analysis_prompt(song_structure)
            context_parts.append(f"\n\nSONG ANALYSIS CONTEXT:")
            context_parts.append(analysis_prompt)
            
            # Check if there are existing lyrics tracks and provide guidance
            lyrics_tracks = [track for track in song_structure.get('tracks', []) 
                           if track.get('category') == 'vocals' or track.get('instrument') == 'vocals']
            
            if lyrics_tracks:
                context_parts.append(f"\n\nEXISTING LYRICS TRACKS: {len(lyrics_tracks)} found")
                context_parts.append("When modifying existing lyrics, maintain the exact JSON structure.")
                context_parts.append("Consider using 'existing_track' integration mode for new lyrics.")
            else:
                context_parts.append(f"\n\nNO LYRICS TRACKS FOUND - Use create_lyrics_track_with_exact_structure tool for new lyrics.")
                context_parts.append("Or use 'new_track' integration mode when applying AI-generated lyrics.")
        else:
            context_parts.append(f"\n\nNO CURRENT SONG STRUCTURE - Please create a new song structure if the user wants to add musical elements.")
            context_parts.append("For lyrics, use create_lyrics_track_with_exact_structure to ensure proper JSON formatting.")
            context_parts.append("Or generate lyrics JSON and offer integration with 'new_track' mode.")
        
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
                missing_elements.append('drums/percussion for rhythm')
            if not any('bass' in inst.lower() for inst in instruments):
                missing_elements.append('bass for low-end foundation')
            if not any(cat in ['keyboards', 'strings'] for cat in categories):
                missing_elements.append('harmonic instruments (piano/guitar) for chords')
                
            if missing_elements:
                analysis_parts.append(f"Missing elements: {', '.join(missing_elements)}")
            
            # Clip analysis
            total_clips = sum(len(track.get('clips', [])) for track in tracks)
            if total_clips > 0:
                analysis_parts.append(f"Song has {total_clips} clips with musical content")
            else:
                analysis_parts.append("Song structure exists but needs musical content (clips)")
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
            json_pattern = r'\{[\s\S]*\}'
            matches = re.findall(json_pattern, response)
            
            for match in matches:
                try:
                    return json.loads(match)
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
        response += self._handle_specific_requests(message_lower, updated_structure, available_instruments, 
                                                 has_drums, has_bass, has_harmonic)
        
        if error:
            response += f" (Note: AI assistant temporarily unavailable: {error})"
        
        return {
            'response': response,
            'updated_song_structure': updated_structure if structure_modified else None,
            'provider': 'fallback',
            'success': structure_modified,
            'error': error
        }
    
    def _handle_specific_requests(self, message_lower: str, updated_structure: Dict, 
                                available_instruments: Dict, has_drums: bool, has_bass: bool, 
                                has_harmonic: bool) -> str:
        """Handle specific music requests in fallback mode"""
        response = ""
        
        if 'intro' in message_lower or 'add intro' in message_lower:
            response += "I'll add an intro section to your song."
            # Implementation for intro would go here
            
        elif ('chord' in message_lower and ('progression' in message_lower or 'add' in message_lower)) or 'harmony' in message_lower:
            if has_harmonic:
                response += "I can see you already have harmonic instruments. I'll add complementary chords."
            else:
                response += "I'll add a harmonic foundation with chord progressions."
            # Implementation for chords would go here
            
        elif 'bass' in message_lower and 'add' in message_lower:
            if has_bass:
                response += "I see you already have bass. I'll add a complementary bass line."
            else:
                response += "Adding a bass track will provide a solid foundation."
            # Implementation for bass would go here
            
        elif 'drums' in message_lower and 'add' in message_lower:
            if has_drums:
                response += "I see you have drums. I'll add a complementary percussion element."
            else:
                response += "Drums will give your song rhythm and energy."
            # Implementation for drums would go here
            
        elif 'lyrics' in message_lower or 'vocal' in message_lower or 'sing' in message_lower:
            response += "I'll help you add lyrics to your song."
            # Implementation for lyrics would go here
            
        elif 'tempo' in message_lower:
            response = "You can adjust the tempo in your song structure."
            # Try to extract tempo from message
            tempo_match = re.search(r'(\d+)\s*bpm', message_lower)
            if tempo_match:
                new_tempo = int(tempo_match.group(1))
                updated_structure['tempo'] = new_tempo
                updated_structure["updatedAt"] = datetime.now().isoformat()
                response += f" I've set your song tempo to {new_tempo} BPM."
            else:
                response += " Most pop songs are 110-130 BPM, while ballads are typically 60-90 BPM."
        
        else:
            # Context-aware general responses
            response += self._get_contextual_suggestions(updated_structure, available_instruments, 
                                                       has_drums, has_bass, has_harmonic)
        
        return response
    
    def _get_contextual_suggestions(self, updated_structure: Dict, available_instruments: Dict,
                                  has_drums: bool, has_bass: bool, has_harmonic: bool) -> str:
        """Get contextual suggestions based on current song state"""
        existing_tracks = updated_structure.get('tracks', [])
        
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
                return f" Your song is empty. Consider starting with {', then add '.join(suggestions)}."
            else:
                return " Your song is empty. Please upload some instrument samples to get started."
        
        elif not has_drums:
            if available_instruments.get('percussion'):
                drum_options = [inst for inst in available_instruments['percussion'] if 'drum' in inst.lower()]
                if drum_options:
                    return f" Consider adding drums for rhythmic foundation. Available: {drum_options[0]}"
                else:
                    return f" Consider adding percussion for rhythm. Available: {available_instruments['percussion'][0]}"
            else:
                return " Consider uploading drum samples for rhythmic foundation."
        
        elif not has_bass:
            if available_instruments.get('strings'):
                bass_options = [inst for inst in available_instruments['strings'] if 'bass' in inst.lower()]
                if bass_options:
                    return f" A bass track would strengthen your song's foundation. Available: {bass_options[0]}"
                else:
                    return f" Consider adding low-end instruments. Available: {available_instruments['strings'][0]}"
            else:
                return " Consider uploading bass samples for low-end foundation."
        
        elif not has_harmonic:
            return " Adding piano or guitar chords would provide harmonic structure."
        
        else:
            return " Your song has good basic elements. Consider adding melody instruments or effects."

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
                    # Import from song_tools
                    from .song_tools import combine_consecutive_clips
                    track['clips'] = combine_consecutive_clips(track['clips'])
            
            # Update the structure timestamp
            optimized_structure['updatedAt'] = datetime.now().isoformat()
            
            return optimized_structure
            
        except Exception as e:
            safe_log_error(f"Error optimizing song structure: {e}")
            return song_structure

    # Legacy compatibility methods
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
            safe_log_error(f"Composition planning error: {str(e)}")
            return {
                'plan': self._fallback_composition_plan(requirements),
                'requirements': requirements,
                'success': False,
                'error': str(e)
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
    
    def chat_with_auto_integration(self, message: str, song_structure: Dict = None, provider: str = 'anthropic', auto_integrate: bool = True) -> Dict:
        """
        Chat with the music assistant and automatically integrate any lyrics JSON found in responses.
        
        Args:
            message: User's message
            song_structure: Current song structure as dict
            provider: AI provider to use
            auto_integrate: Whether to automatically integrate lyrics JSON from responses
        
        Returns:
            Dict with response, updated song structure, and integration status
        """
        try:
            # Get initial response from agent
            result = self.chat_with_music_assistant(message, song_structure, provider)
            
            if not result.get('success', False) or not auto_integrate:
                return result
            
            # Check if the response contains lyrics JSON to integrate
            response_text = result.get('response', '')
            
            if song_structure and self._response_contains_lyrics_json(response_text):
                try:
                    # Try to integrate any lyrics JSON found in the response
                    from .lyrics_tools import integrate_ai_lyrics_response
                    
                    integration_result = integrate_ai_lyrics_response(
                        song_json=song_structure,
                        ai_response=response_text
                    )
                    
                    # Check if integration was successful
                    if not integration_result.startswith("Error") and not integration_result.startswith("No valid"):
                        # Parse the integrated song structure
                        try:
                            integrated_song = json.loads(integration_result)
                            result['updated_song_structure'] = integrated_song
                            result['auto_integrated'] = True
                            result['integration_message'] = "✓ Lyrics JSON automatically integrated into song structure"
                        except json.JSONDecodeError:
                            result['auto_integrated'] = False
                            result['integration_message'] = "⚠ Integration attempted but result not valid JSON"
                    else:
                        result['auto_integrated'] = False
                        result['integration_message'] = f"⚠ Auto-integration failed: {integration_result}"
                        
                except Exception as e:
                    result['auto_integrated'] = False
                    result['integration_message'] = f"⚠ Auto-integration error: {str(e)}"
            else:
                result['auto_integrated'] = False
                result['integration_message'] = "No lyrics JSON found in response to integrate"
            
            return result
            
        except Exception as e:
            safe_log_error(f"Chat with auto-integration error: {str(e)}")
            # Fallback to regular chat
            return self.chat_with_music_assistant(message, song_structure, provider)

    def _response_contains_lyrics_json(self, response: str) -> bool:
        """Check if response contains lyrics JSON that could be integrated"""
        try:
            # Look for JSON patterns that might contain lyrics
            import re
            
            # Check for JSON blocks
            json_patterns = [
                r'```json\s*([\s\S]*?)\s*```',
                r'```\s*([\s\S]*?)\s*```',
                r'\{[\s\S]*"voices"\s*:[\s\S]*\}',
                r'\{[\s\S]*"type"\s*:\s*"lyrics"[\s\S]*\}',
                r'\{[\s\S]*"instrument"\s*:\s*"vocals"[\s\S]*\}'
            ]
            
            for pattern in json_patterns:
                if re.search(pattern, response, re.IGNORECASE):
                    return True
            
            return False
            
        except Exception:
            return False
