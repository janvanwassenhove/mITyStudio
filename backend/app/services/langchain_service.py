"""
LangChain Service
Handles advanced AI interactions using LangChain framework
"""

import os
from typing import Dict, List, Any, Optional
try:
    from langchain_openai import ChatOpenAI
    from langchain_anthropic import ChatAnthropic
except ImportError:
    # Fallback for older langchain versions
    try:
        from langchain.chat_models import ChatOpenAI, ChatAnthropic
    except ImportError:
        # If langchain_community is needed
        from langchain_community.chat_models import ChatOpenAI, ChatAnthropic

from langchain.schema import HumanMessage, SystemMessage
from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferMemory
from langchain.prompts import PromptTemplate
from flask import current_app


class LangChainService:
    """Service for advanced AI interactions using LangChain"""
    
    def __init__(self):
        self.openai_chat = None
        self.anthropic_chat = None
        self.memory = ConversationBufferMemory()
        self._initialize_models()
    
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
                    max_tokens=1000
                )
            
            # Initialize Anthropic
            anthropic_key = os.getenv('ANTHROPIC_API_KEY')
            if anthropic_key:
                self.anthropic_chat = ChatAnthropic(
                    anthropic_api_key=anthropic_key,
                    model="claude-3-sonnet-20240229",
                    temperature=0.7,
                    max_tokens=1000
                )
                
        except Exception as e:
            current_app.logger.error(f"Failed to initialize LangChain models: {str(e)}")
    
    def chat_with_context(self, message: str, context: Dict, provider: str = 'openai') -> Dict:
        """
        Advanced chat with context and memory
        """
        try:
            # Choose model based on provider
            if provider == 'openai' and self.openai_chat:
                chat_model = self.openai_chat
            elif provider == 'anthropic' and self.anthropic_chat:
                chat_model = self.anthropic_chat
            else:
                raise ValueError(f"Provider {provider} not available")
            
            # Build context-aware system message
            system_prompt = self._build_music_system_prompt(context)
            
            # Create conversation chain
            conversation = ConversationChain(
                llm=chat_model,
                memory=self.memory,
                verbose=True
            )
            
            # Add system context to the conversation
            conversation.prompt = PromptTemplate(
                input_variables=["history", "input"],
                template=f"{system_prompt}\n\nConversation History:\n{{history}}\n\nHuman: {{input}}\nAI:"
            )
            
            # Get response
            response = conversation.predict(input=message)
            
            # Extract structured information
            structured_response = self._extract_structured_response(response, context)
            
            return {
                'response': response,
                'structured_data': structured_response,
                'provider': provider,
                'context_used': True
            }
            
        except Exception as e:
            current_app.logger.error(f"LangChain chat error: {str(e)}")
            return {
                'response': "I'm sorry, I'm having trouble processing your request right now.",
                'structured_data': {},
                'provider': provider,
                'context_used': False,
                'error': str(e)
            }
    
    def generate_composition_plan(self, requirements: Dict) -> Dict:
        """
        Generate a detailed composition plan using AI
        """
        try:
            # Choose best available model
            chat_model = self.anthropic_chat or self.openai_chat
            
            if not chat_model:
                raise ValueError("No AI models available")
            
            # Create composition planning prompt
            prompt = self._build_composition_prompt(requirements)
            
            messages = [
                SystemMessage(content="You are an expert music composer and arranger."),
                HumanMessage(content=prompt)
            ]
            
            response = chat_model(messages)
            
            # Parse the structured response
            plan = self._parse_composition_plan(response.content)
            
            return {
                'plan': plan,
                'requirements': requirements,
                'success': True
            }
            
        except Exception as e:
            current_app.logger.error(f"Composition planning error: {str(e)}")
            return {
                'plan': self._fallback_composition_plan(requirements),
                'requirements': requirements,
                'success': False,
                'error': str(e)
            }
    
    def analyze_project_structure(self, project_data: Dict) -> Dict:
        """
        Analyze project structure and provide detailed feedback
        """
        try:
            chat_model = self.anthropic_chat or self.openai_chat
            
            if not chat_model:
                raise ValueError("No AI models available")
            
            # Create analysis prompt
            prompt = self._build_analysis_prompt(project_data)
            
            messages = [
                SystemMessage(content="You are an expert music producer and audio engineer."),
                HumanMessage(content=prompt)
            ]
            
            response = chat_model(messages)
            
            # Parse analysis results
            analysis = self._parse_project_analysis(response.content)
            
            return {
                'analysis': analysis,
                'recommendations': analysis.get('recommendations', []),
                'score': analysis.get('overall_score', 75),
                'success': True
            }
            
        except Exception as e:
            current_app.logger.error(f"Project analysis error: {str(e)}")
            return {
                'analysis': {'error': 'Analysis failed'},
                'recommendations': [],
                'score': 0,
                'success': False,
                'error': str(e)
            }
    
    def suggest_chord_progression_advanced(self, requirements: Dict) -> Dict:
        """
        Generate advanced chord progressions with music theory analysis
        """
        try:
            chat_model = self.anthropic_chat or self.openai_chat
            
            if not chat_model:
                raise ValueError("No AI models available")
            
            prompt = f"""
            Generate a chord progression with the following requirements:
            - Genre: {requirements.get('genre', 'pop')}
            - Key: {requirements.get('key', 'C major')}
            - Mood: {requirements.get('mood', 'happy')}
            - Length: {requirements.get('length', 8)} chords
            - Complexity: {requirements.get('complexity', 'intermediate')}
            
            Please provide:
            1. The chord progression in Roman numeral notation
            2. The actual chord names
            3. Brief music theory explanation
            4. Suggested strumming/playing patterns
            5. Common variations or substitutions
            
            Format your response as JSON with these fields:
            - progression_roman: array of Roman numerals
            - progression_chords: array of chord names
            - theory_explanation: string
            - playing_suggestions: array of suggestions
            - variations: array of alternative progressions
            """
            
            messages = [
                SystemMessage(content="You are a music theory expert and composer."),
                HumanMessage(content=prompt)
            ]
            
            response = chat_model(messages)
            
            # Parse the response
            chord_data = self._parse_chord_response(response.content, requirements)
            
            return {
                'chord_progression': chord_data,
                'success': True
            }
            
        except Exception as e:
            current_app.logger.error(f"Advanced chord generation error: {str(e)}")
            return {
                'chord_progression': self._fallback_chord_progression(requirements),
                'success': False,
                'error': str(e)
            }
    
    def _build_music_system_prompt(self, context: Dict) -> str:
        """Build context-aware system prompt for music assistance"""
        base_prompt = """You are an AI music composition assistant for mITyStudio. 
        You help musicians create, arrange, and produce music. You have deep knowledge of:
        - Music theory and composition
        - Audio production and mixing
        - Various musical genres and styles
        - Digital audio workstations (DAWs)
        - Music software and plugins
        
        You provide practical, actionable advice and can suggest specific implementations."""
        
        if context:
            if context.get('current_project'):
                project = context['current_project']
                base_prompt += f"\n\nCurrent project context:"
                base_prompt += f"\n- Project: {project.get('name', 'Untitled')}"
                base_prompt += f"\n- Genre: {project.get('genre', 'Unknown')}"
                base_prompt += f"\n- Tempo: {project.get('tempo', 'Unknown')} BPM"
                base_prompt += f"\n- Key: {project.get('key', 'Unknown')}"
                base_prompt += f"\n- Tracks: {project.get('track_count', 0)}"
            
            if context.get('recent_actions'):
                base_prompt += f"\n\nRecent actions: {', '.join(context['recent_actions'])}"
        
        return base_prompt
    
    def _build_composition_prompt(self, requirements: Dict) -> str:
        """Build prompt for composition planning"""
        return f"""
        Please create a detailed composition plan for a song with these requirements:
        
        Genre: {requirements.get('genre', 'pop')}
        Mood: {requirements.get('mood', 'neutral')}
        Tempo: {requirements.get('tempo', 120)} BPM
        Key: {requirements.get('key', 'C major')}
        Duration: {requirements.get('duration', '3-4 minutes')}
        Instruments: {', '.join(requirements.get('instruments', ['piano', 'drums', 'bass']))}
        
        Please provide a structured plan including:
        1. Song structure (intro, verse, chorus, etc.)
        2. Chord progressions for each section
        3. Melody suggestions
        4. Rhythm and drum patterns
        5. Arrangement ideas
        6. Production suggestions
        
        Format as a detailed, actionable plan.
        """
    
    def _build_analysis_prompt(self, project_data: Dict) -> str:
        """Build prompt for project analysis"""
        tracks = project_data.get('tracks', [])
        track_info = []
        
        for track in tracks:
            track_info.append(f"- {track.get('name', 'Unnamed')}: {track.get('instrument', 'unknown')}")
        
        return f"""
        Please analyze this music project and provide detailed feedback:
        
        Project Details:
        - Name: {project_data.get('name', 'Untitled')}
        - Genre: {project_data.get('genre', 'unknown')}
        - Tempo: {project_data.get('tempo', 'unknown')} BPM
        - Key: {project_data.get('key', 'unknown')}
        - Duration: {project_data.get('duration', 'unknown')} seconds
        
        Tracks ({len(tracks)}):
        {chr(10).join(track_info)}
        
        Please analyze:
        1. Overall composition structure
        2. Instrumentation balance
        3. Frequency spectrum coverage
        4. Arrangement suggestions
        5. Production recommendations
        6. Potential improvements
        
        Provide an overall score (1-100) and specific actionable recommendations.
        """
    
    def _extract_structured_response(self, response: str, context: Dict) -> Dict:
        """Extract structured data from AI response"""
        # This would implement NLP parsing to extract actionable items
        # For now, return basic structure
        
        structured = {
            'suggested_actions': [],
            'musical_concepts': [],
            'technical_terms': []
        }
        
        # Simple keyword extraction
        response_lower = response.lower()
        
        if 'chord progression' in response_lower:
            structured['suggested_actions'].append('add_chord_progression')
        
        if 'drum' in response_lower or 'beat' in response_lower:
            structured['suggested_actions'].append('add_drums')
        
        if 'bass' in response_lower:
            structured['suggested_actions'].append('add_bass')
        
        return structured
    
    def _parse_composition_plan(self, response: str) -> Dict:
        """Parse composition plan from AI response"""
        # This would implement more sophisticated parsing
        # For now, return structured placeholder
        
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
        # Extract score and recommendations from response
        # This would use more sophisticated NLP in production
        
        return {
            'overall_score': 75,
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
        # In production, this would parse JSON or structured response
        # For now, return example based on requirements
        
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
