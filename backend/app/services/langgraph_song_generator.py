"""
LangGraph-based Multi-Agent Song Generation System

This module implements a comprehensive multi-agent workflow for generating
DAW-compatible song JSON structures using LangGraph and ChatOpenAI.

The system considers all user-provided inputs from the generate song dialog 
and builds up the final JSON structure step by step using specialized agents.

AGENT WORKFLOW:
1. ComposerAgent - Defines global musical parameters: tempo, key, timeSignature, duration
2. ArrangementAgent - Determines song structure and decides track types
3. LyricsAgent - Generates lyrics based on style_tags and inspiration
4. VocalAgent - Assigns available voices and creates polyphonic vocal clips
5. InstrumentAgent - Selects instruments/samples and creates melodic/harmonic/percussive content
6. EffectsAgent - Adds reverb, delay, distortion effects per track/clip
7. ReviewAgent - Evaluates for schema completeness, musical coherence, resource validity
8. DesignAgent - Creates album cover concept and generates image using DALL-E-3
9. QAAgent - Final validation, fixes missing fields, validates against schema

INSTRUMENT & SAMPLE AWARENESS SYSTEM:
- All agents are aware of available_instruments, available_samples, and available_voices
- ArrangementAgent: Plans tracks using ONLY available instruments from the categorized lists
- InstrumentAgent: Creates clips using ONLY available instruments and samples
- VocalAgent: Assigns ONLY available voices to vocal tracks
- System validates instrument/sample selections and provides fallbacks if invalid
- JSON structure follows mITyStudio schema exactly:
  * Melodic instruments: type="synth", notes array directly in clip (NO wrapper)
  * Percussion/drums: type="sample", sampleUrl
  * Vocals: type="lyrics", voices array with lyrics and notes

The system respects the existing mITyStudio JSON schema and integrates with
available voices, instruments, and samples.
"""

import json
import uuid
import asyncio
import logging
import os
import random
import traceback
import re
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

try:
    from langchain_openai import ChatOpenAI
    from langchain_anthropic import ChatAnthropic
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_core.prompts import ChatPromptTemplate
    from langgraph.graph import StateGraph, END
    from langgraph.graph.state import CompiledStateGraph
except ImportError as e:
    print(f"Warning: LangGraph dependencies not available: {e}")
    ChatOpenAI = None
    ChatAnthropic = None
    StateGraph = None
    END = None

# Always import the fallback tools first
from .fallback_music_tools import FallbackMusicTools
from .fallback_utils import safe_log_error

# Try to import the full music tools
MusicCompositionTools = None
generate_intelligent_default_notes = None
try:
    from .langchain.music_tools import MusicCompositionTools, generate_intelligent_default_notes
    print("Successfully imported full MusicCompositionTools and pattern generation")
except Exception as e:
    print(f"Warning: Full music tools not available, using fallbacks: {e}")
    # Import pattern generation separately if needed
    try:
        from .langchain.music_tools import generate_intelligent_default_notes
        print("Successfully imported pattern generation")
    except Exception as e2:
        print(f"Warning: Pattern generation not available: {e2}")
        # Create a simple fallback
        def generate_intelligent_default_notes(instrument, key='C', style='pop'):
            """Simple fallback pattern generation"""
            if 'bass' in instrument.lower():
                return ["C2", "G2", "F2", "G2"]
            elif 'piano' in instrument.lower():
                return ["C4", "E4", "G4", "C5"]
            elif 'drum' in instrument.lower():
                return ["C4", "C4", "E4", "C4"]  # Kick-snare pattern
            else:
                return ["C4", "D4", "E4", "F4"]  # Simple melody

# Try to import the full utils (but we already have fallback)
try:
    from .langchain.utils import safe_log_error as full_safe_log_error
    safe_log_error = full_safe_log_error  # Use the full version if available
except Exception as e:
    pass  # Keep using fallback

logger = logging.getLogger(__name__)

# Global LLM instances to avoid Flask context issues
_global_openai_llm = None
_global_anthropic_llm = None
_llm_initialization_attempted = False

def _initialize_global_llms():
    """Initialize global LLM instances outside of Flask context"""
    global _global_openai_llm, _global_anthropic_llm, _llm_initialization_attempted
    
    if _llm_initialization_attempted:
        return
    
    _llm_initialization_attempted = True
    print("🔧 INITIALIZING GLOBAL LLMs...")
    logger.info("Initializing global LLM instances...")
    
    # Get API keys from environment (both env vars and .env file are checked by os.getenv)
    openai_key = os.getenv('OPENAI_API_KEY')
    anthropic_key = os.getenv('ANTHROPIC_API_KEY')
    
    print(f"🔑 Keys available - OpenAI: {bool(openai_key)} (len: {len(openai_key) if openai_key else 0}), Anthropic: {bool(anthropic_key)} (len: {len(anthropic_key) if anthropic_key else 0})")
    
    # Verify LangChain imports are available
    if not ChatOpenAI:
        print("❌ ChatOpenAI not available - LangChain OpenAI package not installed")
        return
    if not ChatAnthropic:
        print("❌ ChatAnthropic not available - LangChain Anthropic package not installed")  
        return
    
    # Initialize OpenAI LLM with default parameters - model will be overridden per instance
    if ChatOpenAI and openai_key and not openai_key.startswith('your-'):
        try:
            print("🚀 Creating global OpenAI LLM...")
            # Use available model for global instance - actual model selection happens per-instance
            _global_openai_llm = ChatOpenAI(
                api_key=openai_key,
                model="gpt-4o-mini",  # Use available model instead of non-existent gpt-5
                temperature=0.7,
                max_retries=2,
                timeout=120  # Increased to 2 minutes for complex song generation tasks
            )
            print("✅ Global OpenAI LLM initialized successfully")
            logger.info("✓ Global OpenAI LLM initialized successfully")
        except Exception as e:
            print(f"❌ Global OpenAI LLM initialization failed: {e}")
            logger.error(f"✗ Global OpenAI LLM initialization failed: {e}")
            # Try alternative initialization without timeout
            try:
                print("🔄 Retrying OpenAI LLM with basic parameters...")
                _global_openai_llm = ChatOpenAI(
                    api_key=openai_key,
                    model="gpt-4o",  # Try gpt-4o instead
                    temperature=0.7,
                    timeout=120  # Increased timeout for fallback as well
                )
                print("✅ Global OpenAI LLM initialized with alternative parameters")
                logger.info("✓ Global OpenAI LLM initialized with alternative parameters")
            except Exception as e2:
                print(f"❌ Alternative OpenAI LLM initialization also failed: {e2}")
                logger.error(f"✗ Alternative OpenAI LLM initialization failed: {e2}")
    else:
        if openai_key and openai_key.startswith('your-'):
            print("⚠️ OpenAI API key not configured - using placeholder value")
        else:
            print(f"⚠️ OpenAI LLM not available - ChatOpenAI: {ChatOpenAI is not None}, Key: {bool(openai_key)}")
    
    # Initialize Anthropic LLM with minimal parameters
    if ChatAnthropic and anthropic_key and not anthropic_key.startswith('your-'):
        try:
            print("🚀 Creating global Anthropic LLM...")
            # Use minimal parameters to avoid compatibility issues
            _global_anthropic_llm = ChatAnthropic(
                api_key=anthropic_key,
                model="claude-3-5-sonnet-20241022",
                temperature=0.7,
                max_retries=2,
                timeout=120  # Increased to 2 minutes for complex song generation tasks
            )
            print("✅ Global Anthropic LLM initialized successfully")
            logger.info("✓ Global Anthropic LLM initialized successfully")
        except Exception as e:
            print(f"❌ Global Anthropic LLM initialization failed: {e}")
            logger.error(f"✗ Global Anthropic LLM initialization failed: {e}")
            # Try alternative initialization
            try:
                print("🔄 Retrying Anthropic LLM with basic parameters...")
                _global_anthropic_llm = ChatAnthropic(
                    api_key=anthropic_key,
                    model="claude-3-5-haiku-20241022",  # Try different model
                    temperature=0.7,
                    timeout=120  # Increased timeout for fallback as well
                )
                print("✅ Global Anthropic LLM initialized with alternative parameters")
                logger.info("✓ Global Anthropic LLM initialized with alternative parameters")
            except Exception as e2:
                print(f"❌ Alternative Anthropic LLM initialization also failed: {e2}")
                logger.error(f"✗ Alternative Anthropic LLM initialization failed: {e2}")
    else:
        if anthropic_key and anthropic_key.startswith('your-'):
            print("⚠️ Anthropic API key not configured - using placeholder value")
        else:
            print(f"⚠️ Anthropic LLM not available - ChatAnthropic: {ChatAnthropic is not None}, Key: {bool(anthropic_key)}")
    
    print(f"🏁 Global LLM initialization complete - OpenAI: {bool(_global_openai_llm)}, Anthropic: {bool(_global_anthropic_llm)}")

# Force initialization when module is imported
def _force_initialization():
    """Force global LLM initialization when module loads"""
    try:
        _initialize_global_llms()
    except Exception as e:
        print(f"Warning: Global LLM initialization failed during module import: {e}")

# Only attempt initialization if we have the dependencies
if ChatOpenAI and ChatAnthropic:
    _force_initialization()

def ensure_global_llms_initialized():
    """Ensure global LLMs are initialized - can be called from Flask routes"""
    global _global_openai_llm, _global_anthropic_llm, _llm_initialization_attempted
    
    if _global_openai_llm is not None or _global_anthropic_llm is not None:
        return True  # Already have at least one LLM
    
    print("🔄 Ensuring global LLMs are initialized...")
    
    # Reset the flag to force re-initialization
    _llm_initialization_attempted = False
    _initialize_global_llms()
    
    return bool(_global_openai_llm or _global_anthropic_llm)


class AgentDecision(Enum):
    """Possible decisions from agents for workflow control"""
    CONTINUE = "continue"
    REVISE = "revise"
    COMPLETE = "complete"


@dataclass
class SongGenerationRequest:
    """Input parameters for song generation from the frontend dialog"""
    # Fields with default_factory must come after regular default fields
    song_idea: str = ""
    custom_style: str = ""
    lyrics_option: str = "automatically"  # automatically, custom, instrumental
    custom_lyrics: str = ""
    is_instrumental: bool = False
    duration: str = ""  # e.g., "2 minutes", "4 bars"
    song_key: str = ""  # e.g., "C", "G", "Am"
    selected_provider: str = "anthropic"  # Default to anthropic to match frontend
    selected_model: str = "claude-4-sonnet"  # Default to claude-4-sonnet to match frontend
    mood: str = ""  # emotional mood derived from style_tags and song_idea
    style_tags: List[str] = field(default_factory=list)


@dataclass
class SongState:
    """Shared state passed between all agents"""
    # Input parameters
    request: SongGenerationRequest = field(default_factory=SongGenerationRequest)
    
    # Available resources
    available_instruments: Dict[str, List[str]] = field(default_factory=dict)
    available_samples: Dict[str, Dict[str, List[str]]] = field(default_factory=dict)
    available_voices: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # User-uploaded samples with metadata
    available_user_samples: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    sample_metadata: Dict[str, Any] = field(default_factory=dict)  # Complete sample data
    
    # Progressive song structure building
    song_metadata: Dict[str, Any] = field(default_factory=dict)
    global_params: Dict[str, Any] = field(default_factory=dict)
    arrangement: Dict[str, Any] = field(default_factory=dict)
    lyrics: Dict[str, Any] = field(default_factory=dict)
    vocal_assignments: Dict[str, Any] = field(default_factory=dict)
    instrumental_content: Dict[str, Any] = field(default_factory=dict)
    effects_config: Dict[str, Any] = field(default_factory=dict)
    album_art: Dict[str, Any] = field(default_factory=dict)
    
    # Review and QA
    review_notes: List[str] = field(default_factory=list)
    qa_corrections: List[str] = field(default_factory=list)
    qa_feedback: List[str] = field(default_factory=list)
    qa_restart_agent: str = ""  # Which agent to restart from based on QA feedback
    qa_restart_count: int = 0   # Track number of QA restarts
    max_qa_restarts: int = 2    # Limit QA restarts to prevent infinite loops
    is_ready_for_export: bool = False
    
    # User approval process
    user_approval_data: Dict[str, Any] = field(default_factory=dict)  # QA feedback summary for user
    user_decision: str = ""  # User decision: 'accept', 'improve', or ''
    
    # Final output
    final_song_json: Dict[str, Any] = field(default_factory=dict)
    
    # Workflow control
    current_agent: str = ""
    previous_agent: str = ""  # Track which agent called the current one
    revision_count: int = 0
    max_revisions: int = 3
    
    # Error tracking
    errors: List[str] = field(default_factory=list)


class LangGraphSongGenerator:
    """Main class for the multi-agent song generation system"""
    
    def __init__(self, openai_api_key: str = None, anthropic_api_key: str = None, 
                 provider: str = "openai", model: str = "gpt-5"):  # Default to GPT-5
        self.openai_api_key = openai_api_key
        self.anthropic_api_key = anthropic_api_key
        self.provider = provider
        self.model = model
        # Use full MusicCompositionTools now that initialization is safe
        if MusicCompositionTools:
            self.music_tools = MusicCompositionTools()
            print("Using full MusicCompositionTools")
        else:
            self.music_tools = FallbackMusicTools()
            print("Using FallbackMusicTools")
        self.llm = None  # Main LLM for song generation
        self.openai_llm = None  # Dedicated OpenAI LLM for album covers
        self.graph: Optional[CompiledStateGraph] = None
        self.progress_callback = None  # Store progress callback for agents to use
        
        logger.info(f"LangGraphSongGenerator init - Provider: {provider}, Model: {model}")
        logger.info(f"Keys available in init - OpenAI: {bool(openai_api_key)}, Anthropic: {bool(anthropic_api_key)}")
        logger.info(f"Global LLMs available - OpenAI: {bool(_global_openai_llm)}, Anthropic: {bool(_global_anthropic_llm)}")
        
        # Use global LLM instances instead of creating new ones
        self._use_global_llms()
        
        logger.info(f"After using global LLMs - LLM available: {self.llm is not None}")
        
        # Log the actual provider and model being used
        if self.llm:
            llm_class_name = self.llm.__class__.__name__
            logger.info(f"✓ Using {llm_class_name} for song generation with user's selected provider: {provider}, model: {model}")
        else:
            logger.error(f"✗ No LLM available for provider: {provider}, model: {model}")
        
        if self.openai_llm:
            logger.info("✓ OpenAI LLM available for album cover generation (design phase)")
        else:
            logger.warning("✗ No OpenAI LLM available - album cover generation will be limited")
        
        if self.llm:
            try:
                logger.info("Attempting to build LangGraph workflow...")
                self._build_graph()
                logger.info(f"Graph built successfully: {self.graph is not None}")
                if self.graph:
                    logger.info("✓ LangGraph multi-agent system ready")
                else:
                    logger.error("✗ Graph compilation returned None")
            except ImportError as e:
                logger.error(f"Failed to build graph - import error: {e}")
                safe_log_error(f"Graph building failed (imports): {e}")
                self.graph = None
            except Exception as e:
                logger.error(f"Failed to build graph - general error: {e}")
                safe_log_error(f"Graph building failed (general): {e}")
                self.graph = None
        else:
            logger.error("Cannot build graph - no LLM available")
            logger.error(f"LLM selection failed - Provider: {self.provider}, Global OpenAI: {bool(_global_openai_llm)}, Global Anthropic: {bool(_global_anthropic_llm)}")
    
    def _use_global_llms(self) -> None:
        """Use pre-initialized global LLM instances to avoid Flask context issues"""
        global _global_openai_llm, _global_anthropic_llm
        
        # Instead of using global LLMs, create new ones with user's selected model
        # This ensures we respect the user's provider and model choice from the dialog
        
        # Get API keys from environment
        openai_key = self.openai_api_key or os.getenv('OPENAI_API_KEY')
        anthropic_key = self.anthropic_api_key or os.getenv('ANTHROPIC_API_KEY')
        
        logger.info(f"🔧 Creating LLMs with user selection - Provider: {self.provider}, Model: {self.model}")
        logger.info(f"🔑 Dependencies available - ChatAnthropic: {ChatAnthropic is not None}, ChatOpenAI: {ChatOpenAI is not None}")
        logger.info(f"🗝️ Keys available - OpenAI: {bool(openai_key)}, Anthropic: {bool(anthropic_key)}")
        
        # Reset LLM to ensure clean state
        self.llm = None
        
        # Create main LLM based on user's selected provider and model
        if self.provider.lower() == "anthropic":
            logger.info(f"🎯 User selected ANTHROPIC provider")
            if ChatAnthropic and anthropic_key and not anthropic_key.startswith('your-'):
                try:
                    mapped_model = self._map_anthropic_model(self.model)
                    logger.info(f"🚀 Creating Anthropic LLM with model: {mapped_model}")
                    self.llm = ChatAnthropic(
                        api_key=anthropic_key,
                        model=mapped_model,
                        temperature=0.7,
                        max_retries=2,
                        timeout=120
                    )
                    logger.info(f"✅ SUCCESS: Created Anthropic LLM ({type(self.llm).__name__}) with model: {mapped_model}")
                except Exception as e:
                    logger.error(f"❌ FAILED to create Anthropic LLM: {e}")
                    logger.error(f"❌ Exception type: {type(e).__name__}")
                    # Don't fallback to OpenAI for user's Anthropic selection - this is the bug!
                    if _global_anthropic_llm:
                        self.llm = _global_anthropic_llm
                        logger.info("🔄 Using global Anthropic LLM as fallback")
                    else:
                        logger.error("❌ No Anthropic LLM available (global or created)")
            else:
                if anthropic_key and anthropic_key.startswith('your-'):
                    logger.error("❌ Anthropic API key not configured - using placeholder value")
                else:
                    logger.error(f"❌ Cannot create Anthropic LLM - ChatAnthropic: {ChatAnthropic is not None}, Key: {bool(anthropic_key)}")
                if _global_anthropic_llm:
                    self.llm = _global_anthropic_llm
                    logger.info("🔄 Using global Anthropic LLM")
                else:
                    logger.error("❌ No Anthropic options available")
        elif self.provider.lower() == "openai":
            logger.info(f"🎯 User selected OPENAI provider")
            if ChatOpenAI and openai_key and not openai_key.startswith('your-'):
                try:
                    mapped_model = self._map_openai_model(self.model)
                    logger.info(f"🚀 Creating OpenAI LLM with model: {mapped_model}")
                    self.llm = ChatOpenAI(
                        api_key=openai_key,
                        model=mapped_model,
                        temperature=0.7,
                        max_retries=2,
                        timeout=120
                    )
                    logger.info(f"✅ SUCCESS: Created OpenAI LLM ({type(self.llm).__name__}) with model: {mapped_model}")
                except Exception as e:
                    logger.error(f"❌ FAILED to create OpenAI LLM: {e}")
                    logger.error(f"❌ Exception type: {type(e).__name__}")
                    # Fallback to global if available
                    if _global_openai_llm:
                        self.llm = _global_openai_llm
                        logger.info("🔄 Using global OpenAI LLM as fallback")
                    else:
                        logger.error("❌ No OpenAI LLM available (global or created)")
            else:
                if openai_key and openai_key.startswith('your-'):
                    logger.error("❌ OpenAI API key not configured - using placeholder value")
                else:
                    logger.error(f"❌ Cannot create OpenAI LLM - ChatOpenAI: {ChatOpenAI is not None}, Key: {bool(openai_key)}")
                if _global_openai_llm:
                    self.llm = _global_openai_llm
                    logger.info("🔄 Using global OpenAI LLM")
                else:
                    logger.error("❌ No OpenAI options available")
        else:
            logger.error(f"❌ UNKNOWN provider: {self.provider}")
        
        # Final fallback only if no LLM was created and user didn't get their preference
        if self.llm is None:
            logger.warning(f"⚠️ No LLM created for user's choice ({self.provider}), trying emergency fallbacks...")
            if _global_anthropic_llm:
                self.llm = _global_anthropic_llm
                logger.info("🆘 Emergency fallback to global Anthropic LLM")
            elif _global_openai_llm:
                self.llm = _global_openai_llm
                logger.info("🆘 Emergency fallback to global OpenAI LLM")
            else:
                logger.error("🚨 NO LLMs available at all!")
                # Check if it's a key issue and provide helpful message
                if openai_key and openai_key.startswith('your-') and anthropic_key and anthropic_key.startswith('your-'):
                    logger.error("💡 SOLUTION: Please configure your API keys in the .env file")
                    logger.error("   1. Copy .env.example to backend/.env")
                    logger.error("   2. Add your API keys (get them from provider websites)")
                    logger.error("   3. Restart the server")
        
        # Log final result
        if self.llm:
            llm_type = type(self.llm).__name__
            logger.info(f"🎉 FINAL LLM: {llm_type} (user wanted: {self.provider})")
        else:
            logger.error(f"💥 FINAL LLM: None (user wanted: {self.provider})")
        
        # Always use OpenAI for album cover generation (design phase) if available
        if ChatOpenAI and openai_key and not openai_key.startswith('your-'):
            try:
                # For design phase, always use OpenAI with a good model for image generation
                self.openai_llm = ChatOpenAI(
                    api_key=openai_key,
                    model="gpt-4o",  # Use available model for best image generation prompts
                    temperature=0.7,
                    max_retries=2,
                    timeout=120
                )
                logger.info("✓ Created dedicated OpenAI LLM for album cover generation")
            except Exception as e:
                logger.error(f"Failed to create OpenAI LLM for album covers: {e}")
                if _global_openai_llm:
                    self.openai_llm = _global_openai_llm
                    logger.info("✓ Using global OpenAI LLM for album covers")
        else:
            if _global_openai_llm:
                self.openai_llm = _global_openai_llm
                logger.info("✓ Using global OpenAI LLM for album covers")
            else:
                logger.warning("✗ No OpenAI LLM available - album cover generation will be limited")
    
    async def _safe_progress_callback(self, message: str, progress: int, agent: str = None, restart_reason: str = None, restart_attempt: int = None, **kwargs):
        """Safely call progress callback whether it's async or sync"""
        if self.progress_callback:
            try:
                if asyncio.iscoroutinefunction(self.progress_callback):
                    await self.progress_callback(message, progress, agent, restart_reason, restart_attempt, **kwargs)
                else:
                    self.progress_callback(message, progress, agent, restart_reason, restart_attempt, **kwargs)
            except Exception as e:
                logger.warning(f"Progress callback failed: {e}")
    
    def _calculate_restart_adjusted_progress(self, base_progress: int, state: SongState) -> int:
        """
        Calculate progress percentage accounting for QA restarts
        When agents are restarted due to QA feedback, progress needs adjustment
        """
        if state.qa_restart_count == 0:
            return base_progress
        
        # Reduce progress based on restart count to show rework
        # Each restart reduces apparent progress by 10% to indicate rework
        adjustment = min(state.qa_restart_count * 10, 30)  # Max 30% reduction
        adjusted_progress = max(base_progress - adjustment, 0)
        
        return adjusted_progress

    async def _call_llm_safely(self, prompt: str, max_retries: int = 3) -> str:
        """
        Call LLM with proper message format for both OpenAI and Anthropic
        Includes retry logic for API overload and rate limiting
        """
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                # Check if LLM is available
                if self.llm is None:
                    print(f"ERROR: LLM is None in _call_llm_safely!")
                    print(f"Global LLMs status - OpenAI: {bool(_global_openai_llm)}, Anthropic: {bool(_global_anthropic_llm)}")
                    raise ValueError("LLM is not initialized - cannot make API call")
                
                # Add comprehensive logging to track LLM usage
                llm_type = type(self.llm).__name__
                llm_model = getattr(self.llm, 'model', getattr(self.llm, 'model_name', 'unknown'))
                print(f"🔍 CALLING LLM (Attempt {attempt + 1}/{max_retries}): {llm_type} | Model: {llm_model} | User wanted: {self.provider}")
                
                # Check if we're using Anthropic LLM (either by provider or by actual LLM instance)
                is_anthropic = (self.provider == "anthropic" or 
                              (hasattr(self.llm, '__class__') and 'anthropic' in self.llm.__class__.__module__.lower()))
                
                if is_anthropic:
                    # Anthropic requires HumanMessage, use system prompt in a user message
                    messages = [HumanMessage(content=prompt)]
                    logger.debug("Using HumanMessage for Anthropic")
                else:
                    # OpenAI can handle SystemMessage
                    messages = [SystemMessage(content=prompt)]
                    logger.debug("Using SystemMessage for OpenAI")
                
                # Try async first, fallback to sync if needed
                response = None
                if hasattr(self.llm, 'ainvoke'):
                    try:
                        ainvoke_result = self.llm.ainvoke(messages)
                        if ainvoke_result is None:
                            raise ValueError("ainvoke returned None")
                        response = await ainvoke_result
                    except Exception as async_error:
                        print(f"DEBUG: Async call failed: {async_error}, trying sync...")
                        # Fallback to sync call
                        if hasattr(self.llm, 'invoke'):
                            response = await asyncio.get_event_loop().run_in_executor(
                                None, self.llm.invoke, messages
                            )
                        else:
                            raise async_error
                elif hasattr(self.llm, 'invoke'):
                    response = await asyncio.get_event_loop().run_in_executor(
                        None, self.llm.invoke, messages
                    )
                else:
                    raise ValueError("LLM has neither ainvoke nor invoke methods")
                
                if not response or not hasattr(response, 'content'):
                    raise ValueError("LLM returned invalid response object")
                
                content = response.content
                if not content or not content.strip():
                    raise ValueError("LLM returned empty or whitespace-only content")
                    
                print(f"✅ LLM call successful on attempt {attempt + 1}")
                return content.strip()
                
            except Exception as e:
                last_exception = e
                error_str = str(e).lower()
                status_code = getattr(e, 'status_code', None)
                
                # Check for specific error types that warrant retry
                is_retryable = (
                    status_code == 529 or  # Anthropic overload
                    "overloaded" in error_str or
                    "rate limit" in error_str or
                    "too many requests" in error_str or
                    "service unavailable" in error_str or
                    "internal server error" in error_str or
                    "timeout" in error_str or
                    "connection" in error_str
                )
                
                if is_retryable and attempt < max_retries - 1:
                    # Calculate exponential backoff with jitter
                    base_delay = 2 ** attempt  # 1, 2, 4 seconds
                    jitter = random.uniform(0.5, 1.5)  # Add randomness
                    delay = base_delay * jitter
                    
                    print(f"🔄 Retryable error on attempt {attempt + 1}: {e}")
                    print(f"⏳ Waiting {delay:.1f} seconds before retry...")
                    
                    # Try fallback provider if available and this is Anthropic overload
                    if status_code == 529 and self.provider == "anthropic" and _global_openai_llm:
                        print("🔄 Anthropic overloaded (529), trying OpenAI fallback...")
                        original_llm = self.llm
                        try:
                            self.llm = _global_openai_llm
                            # Don't wait for fallback attempt
                            continue
                        except Exception as fallback_error:
                            print(f"❌ OpenAI fallback failed: {fallback_error}")
                            self.llm = original_llm  # Restore original
                    
                    await asyncio.sleep(delay)
                    continue
                else:
                    # Non-retryable error or max retries reached
                    print(f"❌ Non-retryable error or max retries reached: {e}")
                    break
        
        # If we get here, all retries failed
        print(f"🚨 All {max_retries} attempts failed. Last error: {last_exception}")
        
        # Provide specific error messages
        if last_exception:
            error_str = str(last_exception).lower()
            status_code = getattr(last_exception, 'status_code', None)
            
            if status_code == 529:
                raise Exception("Anthropic API is currently overloaded (Error 529). Please try again in a few minutes or switch to OpenAI provider.")
            elif "timeout" in error_str or "timed out" in error_str:
                raise TimeoutError("LLM request timed out after multiple attempts. The AI model took too long to respond. Please try again with a simpler prompt.")
            elif "rate limit" in error_str:
                raise Exception("API rate limit exceeded after multiple attempts. Please wait longer and try again.")
            else:
                raise Exception(f"LLM failed after {max_retries} attempts: {last_exception}")
        
        # If we get here, all retries failed
        print(f"🚨 All {max_retries} attempts failed. Last error: {last_exception}")
        
        # Provide specific error messages
        if last_exception:
            error_str = str(last_exception).lower()
            status_code = getattr(last_exception, 'status_code', None)
            
            if status_code == 529:
                raise Exception("Anthropic API is currently overloaded (Error 529). Please try again in a few minutes or switch to OpenAI provider.")
            elif "timeout" in error_str or "timed out" in error_str:
                raise TimeoutError("LLM request timed out after multiple attempts. The AI model took too long to respond. Please try again with a simpler prompt.")
            elif "rate limit" in error_str:
                raise Exception("API rate limit exceeded after multiple attempts. Please wait longer and try again.")
            else:
                raise Exception(f"LLM failed after {max_retries} attempts: {last_exception}")
        else:
            raise Exception(f"LLM failed after {max_retries} attempts with unknown error")
    
    def _safe_json_parse(self, json_text: str, fallback_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Safely parse JSON with cleanup and fallback handling
        """
        try:
            # First attempt: direct parsing
            return json.loads(json_text)
        except json.JSONDecodeError as e:
            logger.warning(f"Initial JSON parse failed: {e}")
            
            # Second attempt: Clean common issues
            try:
                # Remove any markdown code block markers
                cleaned = json_text.strip()
                if cleaned.startswith("```json"):
                    cleaned = cleaned[7:]
                if cleaned.startswith("```"):
                    cleaned = cleaned[3:]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                
                # Remove any trailing commas before closing braces/brackets
                cleaned = re.sub(r',(\s*[}\]])', r'\1', cleaned)
                
                # Try parsing the cleaned version
                return json.loads(cleaned)
            except json.JSONDecodeError as e2:
                logger.error(f"Cleaned JSON parse also failed: {e2}")
                logger.error(f"Original text: {json_text[:200]}...")
                
                # Return fallback or empty dict
                if fallback_data:
                    logger.info("Using fallback data due to JSON parsing failure")
                    return fallback_data
                else:
                    logger.warning("No fallback data available, returning empty dict")
                    return {}
    
    def _format_style_tags(self, style_tags: List[Any]) -> str:
        """
        Safely format style tags, handling both string and dict formats
        """
        if not style_tags:
            return ""
        
        formatted_tags = []
        for tag in style_tags:
            if isinstance(tag, str):
                formatted_tags.append(tag)
            elif isinstance(tag, dict):
                # Handle dict format - try to extract a string representation
                if 'name' in tag:
                    formatted_tags.append(tag['name'])
                elif 'value' in tag:
                    formatted_tags.append(tag['value'])
                elif 'label' in tag:
                    formatted_tags.append(tag['label'])
                else:
                    # Fallback: use the first string value found
                    for key, value in tag.items():
                        if isinstance(value, str):
                            formatted_tags.append(value)
                            break
            else:
                # Convert other types to string
                formatted_tags.append(str(tag))
        
        return ', '.join(formatted_tags)
    
    def _ensure_string_list(self, items: List[Any]) -> List[str]:
        """
        Ensure all items in a list are strings, converting as needed
        """
        if not items:
            return []
        
        string_items = []
        for item in items:
            if isinstance(item, str):
                string_items.append(item)
            elif isinstance(item, dict):
                # Handle dict format - try to extract a string representation
                if 'message' in item:
                    string_items.append(item['message'])
                elif 'issue' in item:
                    string_items.append(item['issue'])
                elif 'description' in item:
                    string_items.append(item['description'])
                else:
                    # Fallback: use the first string value found or convert to string
                    found_string = False
                    for key, value in item.items():
                        if isinstance(value, str) and value.strip():
                            string_items.append(value)
                            found_string = True
                            break
                    if not found_string:
                        string_items.append(str(item))
            else:
                # Convert other types to string
                string_items.append(str(item))
        
        return string_items
    
    def _initialize_llms(self) -> None:
        """Initialize LLM clients based on provider selection"""
        logger.info(f"Initializing LLMs - Provider: {self.provider}, Model: {self.model}")
        logger.info(f"ChatOpenAI available: {ChatOpenAI is not None}")
        logger.info(f"ChatAnthropic available: {ChatAnthropic is not None}")
        logger.info(f"OpenAI API key available: {self.openai_api_key is not None}")
        logger.info(f"Anthropic API key available: {self.anthropic_api_key is not None}")
        
        # Initialize main LLM for song generation
        try:
            if self.provider == "anthropic" and ChatAnthropic and self.anthropic_api_key:
                try:
                    actual_model = self._map_anthropic_model(self.model)
                    logger.info(f"Attempting to create Anthropic LLM with model: {actual_model}")
                    self.llm = ChatAnthropic(
                        api_key=self.anthropic_api_key,
                        model=actual_model,
                        temperature=0.7
                    )
                    logger.info(f"Successfully initialized Anthropic LLM with model: {actual_model}")
                except Exception as e:
                    logger.error(f"Failed to initialize Anthropic LLM: {e}")
                    logger.error(f"Exception type: {type(e).__name__}")
                    logger.error(f"Exception args: {e.args}")
                    safe_log_error(f"Failed to initialize Anthropic LLM: {e}")
                    # Fallback to OpenAI if available
                    if ChatOpenAI and self.openai_api_key:
                        try:
                            actual_model = self._map_openai_model(self.model)
                            logger.info(f"Attempting fallback to OpenAI LLM with model: {actual_model}")
                            self.llm = ChatOpenAI(
                                api_key=self.openai_api_key,
                                model_name=actual_model,
                                temperature=0.7
                            )
                            logger.info(f"Fallback to OpenAI LLM successful with model: {actual_model}")
                        except Exception as fallback_e:
                            logger.error(f"OpenAI fallback also failed: {fallback_e}")
                            logger.error(f"Fallback exception type: {type(fallback_e).__name__}")
                            logger.error(f"Fallback exception args: {fallback_e.args}")
            elif self.provider == "openai" and ChatOpenAI and self.openai_api_key:
                try:
                    actual_model = self._map_openai_model(self.model)
                    logger.info(f"Attempting to create OpenAI LLM with model: {actual_model}")
                    self.llm = ChatOpenAI(
                        api_key=self.openai_api_key,
                        model_name=actual_model,
                        temperature=0.7
                    )
                    logger.info(f"Successfully initialized OpenAI LLM with model: {actual_model}")
                except Exception as e:
                    logger.error(f"Failed to initialize OpenAI LLM: {e}")
                    logger.error(f"Exception type: {type(e).__name__}")
                    logger.error(f"Exception args: {e.args}")
                    safe_log_error(f"OpenAI LLM initialization failed: {e}")
            else:
                logger.info("Provider doesn't match or dependencies missing, trying fallback initialization")
                # Fallback to any available provider
                if ChatOpenAI and self.openai_api_key:
                    try:
                        logger.info("Attempting fallback to OpenAI LLM with gpt-4")
                        self.llm = ChatOpenAI(
                            api_key=self.openai_api_key,
                            model_name="gpt-4",
                            temperature=0.7
                        )
                        logger.info("Fallback to OpenAI LLM with gpt-4 successful")
                    except Exception as e:
                        logger.error(f"OpenAI fallback failed: {e}")
                        logger.error(f"Exception type: {type(e).__name__}")
                        logger.error(f"Exception args: {e.args}")
                elif ChatAnthropic and self.anthropic_api_key:
                    try:
                        logger.info("Attempting fallback to Anthropic LLM with claude-3-5-sonnet")
                        self.llm = ChatAnthropic(
                            api_key=self.anthropic_api_key,
                            model="claude-3-5-sonnet-20241022",
                            temperature=0.7
                        )
                        logger.info("Fallback to Anthropic LLM with claude-3-5-sonnet successful")
                    except Exception as e:
                        logger.error(f"Anthropic fallback failed: {e}")
                        logger.error(f"Exception type: {type(e).__name__}")
                        logger.error(f"Exception args: {e.args}")
                else:
                    logger.error(f"No LLM could be initialized - ChatOpenAI: {ChatOpenAI is not None}, ChatAnthropic: {ChatAnthropic is not None}, OpenAI key: {self.openai_api_key is not None}, Anthropic key: {self.anthropic_api_key is not None}")
        except Exception as e:
            logger.error(f"Outer exception during LLM initialization: {e}")
            logger.error(f"Outer exception type: {type(e).__name__}")
            logger.error(f"Outer exception args: {e.args}")
            safe_log_error(f"LLM initialization failed: {e}")
            self.llm = None
        
        # Always initialize OpenAI LLM for album cover generation if available
        if ChatOpenAI and self.openai_api_key:
            try:
                logger.info("Attempting to initialize dedicated OpenAI LLM for album cover generation")
                self.openai_llm = ChatOpenAI(
                    api_key=self.openai_api_key,
                    model_name="gpt-4",  # Use a stable model for album covers
                    temperature=0.7
                )
                logger.info("Successfully initialized dedicated OpenAI LLM for album cover generation")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI LLM for album covers: {e}")
                logger.error(f"Album cover exception type: {type(e).__name__}")
                logger.error(f"Album cover exception args: {e.args}")
                self.openai_llm = None
        else:
            logger.warning("OpenAI LLM not available - album cover generation may fail")
    
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
            'claude-3-haiku-20240307': 'claude-3-haiku-20240307'
        }
        return model_mapping.get(model_id, 'claude-3-5-sonnet-20241022')
    
    def _map_openai_model(self, model_id: str) -> str:
        """Map frontend model ID to actual OpenAI model name"""
        model_mapping = {
            # GPT-4o Family (Available)
            'chatgpt-4o-latest': 'chatgpt-4o-latest',
            'gpt-4o': 'gpt-4o',
            'gpt-4o-2024-11-20': 'gpt-4o-2024-11-20',
            'gpt-4o-2024-08-06': 'gpt-4o-2024-08-06',
            'gpt-4o-2024-05-13': 'gpt-4o-2024-05-13',
            'gpt-4o-mini': 'gpt-4o-mini',
            'gpt-4o-mini-2024-07-18': 'gpt-4o-mini-2024-07-18',
            # GPT-4 Family (Available)
            'gpt-4-turbo': 'gpt-4-turbo',
            'gpt-4-turbo-2024-04-09': 'gpt-4-turbo-2024-04-09',
            'gpt-4-turbo-preview': 'gpt-4-turbo-preview',
            'gpt-4-0125-preview': 'gpt-4-0125-preview',
            'gpt-4-1106-preview': 'gpt-4-1106-preview',
            'gpt-4': 'gpt-4',
            'gpt-4-0613': 'gpt-4-0613',
            # GPT-3.5 Family (Available)
            'gpt-3.5-turbo': 'gpt-3.5-turbo',
            'gpt-3.5-turbo-0125': 'gpt-3.5-turbo-0125',
            'gpt-3.5-turbo-1106': 'gpt-3.5-turbo-1106',
            'gpt-3.5-turbo-16k': 'gpt-3.5-turbo-16k',
            'gpt-3.5-turbo-instruct': 'gpt-3.5-turbo-instruct',
            # o1 Family (Available)
            'o1-pro': 'o1-pro',
            'o1': 'o1',
            'o1-2024-12-17': 'o1-2024-12-17',
            'o1-mini': 'o1-mini',
            'o1-mini-2024-09-12': 'o1-mini-2024-09-12',
            # Future models - map to available alternatives
            'gpt-5': 'gpt-4o',  # Map future models to current best
            'gpt-5-mini': 'gpt-4o-mini',
            'gpt-5-nano': 'gpt-4o-mini',
            'gpt-4.1': 'gpt-4o',
            'gpt-4.1-mini': 'gpt-4o-mini'
        }
        return model_mapping.get(model_id, 'gpt-4o-mini')  # Default to gpt-4o-mini as it's cost effective
    
    def _build_graph(self) -> None:
        """Build the LangGraph workflow"""
        if not StateGraph:
            raise ImportError("LangGraph not available")
        
        # Create the state graph
        workflow = StateGraph(SongState)
        
        # Add all agent nodes
        workflow.add_node("composer", self._composer_agent)
        workflow.add_node("arranger", self._arrangement_agent)  # Renamed to avoid conflict with state field
        workflow.add_node("lyricist", self._lyrics_agent)  # Renamed to avoid conflict with state field
        workflow.add_node("vocal", self._vocal_agent)
        workflow.add_node("instrument", self._instrument_agent)
        workflow.add_node("effects", self._effects_agent)
        workflow.add_node("review", self._review_agent)
        workflow.add_node("design", self._design_agent)
        workflow.add_node("qa", self._qa_agent)
        
        # Define the workflow edges
        workflow.set_entry_point("composer")
        
        # Linear progression with conditional paths for instrumental tracks
        workflow.add_edge("composer", "arranger")
        
        # Conditional edge: Skip lyrics/vocal agents for instrumental tracks
        workflow.add_conditional_edges(
            "arranger",
            self._arrangement_decision,
            {
                "skip_lyrics_vocal": "instrument",  # Skip lyrics and vocal agents for instrumental tracks
                "include_lyrics_vocal": "lyricist"    # Include lyrics and vocal agents for non-instrumental tracks
            }
        )
        
        # Conditional edge: Skip vocal agent for instrumental tracks (in case we reach lyrics)
        workflow.add_conditional_edges(
            "lyricist",
            self._vocal_decision,
            {
                "skip_vocal": "instrument",  # Skip vocal agent for instrumental tracks
                "include_vocal": "vocal"     # Include vocal agent for non-instrumental tracks
            }
        )
        
        workflow.add_edge("vocal", "instrument")
        workflow.add_edge("instrument", "effects")
        workflow.add_edge("effects", "review")
        
        # Review decision point
        workflow.add_conditional_edges(
            "review",
            self._review_decision,
            {
                "revise": "composer",  # Go back to composer for major revisions
                "continue": "design"
            }
        )
        
        workflow.add_edge("design", "qa")
        
        # QA decision point - can restart specific agents based on feedback
        workflow.add_conditional_edges(
            "qa",
            self._qa_decision,
            {
                "complete": END,           # Song validation passed
                "user_review": "user_approval",      # Let user decide on improvements
                "restart_composer": "composer",       # Restart from composer for tempo/key issues
                "restart_arrangement": "arranger", # Restart from arranger for structure issues
                "restart_lyrics": "lyricist",           # Restart from lyrics for lyric issues
                "restart_vocal": "vocal",             # Restart from vocal for voice/vocal issues
                "restart_instrument": "instrument",   # Restart from instrument for instrumental issues
                "restart_effects": "effects",         # Restart from effects for effects issues
                "restart_design": "design"            # Restart from design for album art issues
            }
        )
        
        # Add user approval node
        workflow.add_node("user_approval", self._user_approval_agent)
        
        # User approval decision point
        workflow.add_conditional_edges(
            "user_approval",
            self._user_approval_decision,
            {
                "accept": END,             # User accepts current version
                "restart_composer": "composer",       # User wants to restart from composer
                "restart_arrangement": "arranger", # User wants to restart from arranger
                "restart_lyrics": "lyricist",           # User wants to restart from lyrics
                "restart_vocal": "vocal",             # User wants to restart from vocal
                "restart_instrument": "instrument",   # User wants to restart from instrument
                "restart_effects": "effects",         # User wants to restart from effects
                "restart_design": "design"            # User wants to restart from design
            }
        )
        
        # Compile the graph
        self.graph = workflow.compile()
    
    def _arrangement_decision(self, state: SongState) -> str:
        """
        Decision function to determine whether to include lyrics/vocal processing after arrangement
        Returns 'skip_lyrics_vocal' for instrumental tracks, 'include_lyrics_vocal' for vocal tracks
        """
        logger.info(f"🎵 Arrangement Decision: Evaluating - is_instrumental={state.request.is_instrumental}")
        logger.info(f"🎵 Arrangement Decision: Current agent={state.current_agent}, Previous agent={getattr(state, 'previous_agent', 'unknown')}")
        logger.info(f"🎵 Arrangement Decision: QA restart count={getattr(state, 'qa_restart_count', 0)}")
        
        if state.request.is_instrumental:
            logger.info("🎵 Workflow: Skipping lyrics and vocal agents - instrumental track selected")
            logger.info("🎵 Workflow Routing: arrangement → instrument (bypassing lyrics/vocal)")
            return "skip_lyrics_vocal"
        else:
            logger.info("🎤 Workflow: Including lyrics and vocal agents - vocal track selected")
            logger.info("🎤 Workflow Routing: arrangement → lyrics → vocal → instrument")
            return "include_lyrics_vocal"
    
    def _vocal_decision(self, state: SongState) -> str:
        """
        Decision function to determine whether to include vocal processing
        Returns 'skip_vocal' for instrumental tracks, 'include_vocal' for vocal tracks
        """
        logger.info(f"🎵 Vocal Decision: Evaluating - is_instrumental={state.request.is_instrumental}")
        
        if state.request.is_instrumental:
            logger.info("🎵 Workflow: Skipping vocal agent - instrumental track selected")
            return "skip_vocal"
        else:
            logger.info("🎤 Workflow: Including vocal agent - vocal track selected")
            return "include_vocal"
    
    async def generate_song(self, request: SongGenerationRequest, progress_callback=None) -> Dict[str, Any]:
        """Generate a complete song structure using the multi-agent system"""
        if not self.graph:
            # Provide specific error messages based on the issue
            if not ChatOpenAI and not ChatAnthropic:
                raise RuntimeError("LangChain dependencies not available. Please install: pip install langchain-openai langchain-anthropic")
            elif not self.llm:
                # Check API keys
                openai_key = os.getenv('OPENAI_API_KEY')
                anthropic_key = os.getenv('ANTHROPIC_API_KEY')
                
                if (not openai_key or openai_key.startswith('your-')) and (not anthropic_key or anthropic_key.startswith('your-')):
                    raise RuntimeError("API keys not configured. Please set OPENAI_API_KEY or ANTHROPIC_API_KEY in your .env file. Get keys from: OpenAI (https://platform.openai.com/api-keys) or Anthropic (https://console.anthropic.com/account/keys)")
                else:
                    raise RuntimeError("Failed to initialize AI models. Check your API keys and internet connection.")
            else:
                raise RuntimeError("Graph not initialized. Check dependencies and API key.")
        
        # Store progress callback for agents to use
        self.progress_callback = progress_callback
        
        # Add progress tracking
        await self._safe_progress_callback("Initializing song generation...", 0)
        
        # Initialize state with available resources
        # IMPORTANT: All agents must ONLY use instruments/samples from these available resources
        # - available_instruments: Dict[category, List[instrument_names]] - instruments by category
        # - available_samples: Dict[category, Dict[group, List[sample_names]]] - samples by category/group  
        # - available_voices: Dict[voice_id, voice_info] - voice data with ranges
        # - available_user_samples: Dict[category, List[sample_info]] - user-uploaded samples with metadata
        # Agents should validate all instrument/sample selections against these lists
        # PRIORITY: Agents should prioritize and suggest user-uploaded samples when appropriate
        
        # Get comprehensive sample data including user uploads
        all_samples_data = self.music_tools.get_all_available_samples()
        
        initial_state = SongState(
            request=request,
            available_instruments=self.music_tools.available_instruments,
            available_samples=self.music_tools.available_samples,
            available_voices=self.music_tools.available_voices,
            available_user_samples=all_samples_data.get('user_samples', {}),
            sample_metadata=all_samples_data  # Complete sample data for agents
        )
        
        try:
            await self._safe_progress_callback("Starting multi-agent workflow...", 10)
            
            # Run the workflow with timeout and recursion limit
            import asyncio
            try:
                # Configure recursion limit to prevent infinite loops
                config = {"recursion_limit": 50}  # Increase from default 25 to allow for reasonable revisions
                
                print(f"DEBUG: About to invoke graph with state type: {type(initial_state)}")
                print(f"DEBUG: Graph type: {type(self.graph)}")
                print(f"DEBUG: Graph has ainvoke: {hasattr(self.graph, 'ainvoke')}")
                print(f"DEBUG: Graph object: {self.graph}")
                
                # Check what graph.ainvoke returns before awaiting
                graph_invocation = self.graph.ainvoke(initial_state, config=config)
                print(f"DEBUG: Graph ainvoke returned: {type(graph_invocation)} - {graph_invocation}")
                
                if graph_invocation is None:
                    print("ERROR: Graph ainvoke returned None!")
                    raise ValueError("Graph ainvoke returned None - workflow execution failed")
                
                final_state = await asyncio.wait_for(
                    graph_invocation, 
                    timeout=420.0  # Increased to 7 minutes to match frontend timeout
                )
                print(f"DEBUG: Graph execution completed successfully")
            except asyncio.TimeoutError:
                logger.error("Song generation timed out after 7 minutes")
                return {
                    "success": False,
                    "error": "Song generation timed out after 7 minutes. Please try with a simpler request, shorter duration, or different AI provider.",
                    "timeout": True
                }
            except Exception as e:
                if "recursion limit" in str(e).lower():
                    logger.error(f"Song generation hit recursion limit: {e}")
                    return {
                        "success": False,
                        "error": "Song generation workflow exceeded maximum iterations. This might indicate complex requirements or system issues.",
                        "recursion_error": True
                    }
                else:
                    # Enhanced error logging for string join errors
                    import traceback
                    error_msg = str(e)
                    full_traceback = traceback.format_exc()
                    
                    if "expected str instance, dict found" in error_msg:
                        logger.error(f"String join error detected: {error_msg}")
                        logger.error(f"Full traceback for string join error: {full_traceback}")
                        
                        # Try to extract the specific location from the traceback
                        traceback_lines = full_traceback.split('\n')
                        for i, line in enumerate(traceback_lines):
                            if 'langgraph_song_generator.py' in line and i + 1 < len(traceback_lines):
                                logger.error(f"Error occurred at: {line}")
                                logger.error(f"Next line: {traceback_lines[i + 1]}")
                                break
                    
                    logger.error(f"Graph execution error: {error_msg}")
                    logger.error(f"Full error traceback: {full_traceback}")
                    raise  # Re-raise other exceptions
            
            await self._safe_progress_callback("Processing final results...", 90)
            
            # Handle both object and dict returns from LangGraph
            if isinstance(final_state, dict):
                is_ready = final_state.get('is_ready_for_export', False)
                final_song_json = final_state.get('final_song_json', {})
                album_art = final_state.get('album_art', '')
                review_notes = final_state.get('review_notes', [])
                qa_corrections = final_state.get('qa_corrections', [])
                errors = final_state.get('errors', [])
                user_approval_data = final_state.get('user_approval_data', None)
            else:
                is_ready = final_state.is_ready_for_export
                final_song_json = final_state.final_song_json
                album_art = final_state.album_art
                review_notes = final_state.review_notes
                qa_corrections = final_state.qa_corrections
                errors = final_state.errors
                user_approval_data = getattr(final_state, 'user_approval_data', None)
            
            await self._safe_progress_callback("Song generation completed!", 100)
            
            # Check if we're in a user approval state (waiting for user decision)
            user_approval_pending = getattr(final_state, 'user_approval_pending', False) if hasattr(final_state, 'user_approval_pending') else final_state.get('user_approval_pending', False)
            qa_feedback = final_state.get('qa_feedback', []) if isinstance(final_state, dict) else getattr(final_state, 'qa_feedback', [])
            
            if user_approval_data or (user_approval_pending and qa_feedback):
                # We're at the user approval node - this is not an error, it's expected
                logger.info("🤖 Generation reached user approval phase - waiting for user decision")
                logger.info(f"🤖 User approval data exists: {bool(user_approval_data)}")
                logger.info(f"🤖 User approval pending: {user_approval_pending}")
                logger.info(f"🤖 QA feedback items: {len(qa_feedback)}")
                
                return {
                    "success": True,
                    "user_approval_required": True,
                    "user_approval_data": user_approval_data,
                    "qa_feedback": qa_feedback,
                    "qa_corrections": qa_corrections,
                    "song_structure": final_song_json,
                    "review_notes": review_notes,
                    "album_art": album_art
                }
            elif is_ready and final_song_json:
                return {
                    "success": True,
                    "song_structure": final_song_json,
                    "album_art": album_art,
                    "review_notes": review_notes,
                    "qa_corrections": qa_corrections
                }
            else:
                detailed_errors = errors if errors else ["No specific errors reported"]
                logger.error(f"Song generation failed validation: is_ready={is_ready}, has_song_json={bool(final_song_json)}")
                logger.error(f"Validation errors: {detailed_errors}")
                return {
                    "success": False,
                    "error": f"Song generation failed validation: {'; '.join(str(err) for err in detailed_errors[:3])}",
                    "errors": errors,
                    "review_notes": review_notes,
                    "debug_info": {
                        "is_ready_for_export": is_ready,
                        "has_final_song_json": bool(final_song_json),
                        "final_song_structure_keys": list(final_song_json.keys()) if isinstance(final_song_json, dict) else "Not a dict"
                    }
                }
                
        except Exception as e:
            safe_log_error(f"Error in song generation workflow: {e}")
            return {
                "success": False,
                "error": str(e),
                "errors": [str(e)]
            }

    async def handle_user_approval_decision(self, session_id: str, user_decision: str) -> Dict[str, Any]:
        """
        Handle user approval decision and continue the workflow
        
        Args:
            session_id: Unique identifier for the generation session
            user_decision: 'accept' to accept current version, 'improve' to request improvements
            
        Returns:
            Dict with success status and continuation results
        """
        # In a real implementation, you would store session state in a database
        # For now, this is a placeholder for the structure
        
        # This method would:
        # 1. Retrieve the stored session state from database/cache
        # 2. Set the user_decision in the state
        # 3. Continue the workflow from the user_approval node
        # 4. Return the final result
        
        logger.info(f"🤖 User Approval Handler: Received decision '{user_decision}' for session {session_id}")
        
        # Placeholder response - in real implementation this would continue the workflow
        return {
            "success": True,
            "message": f"User decision '{user_decision}' received. Workflow continuation not yet implemented.",
            "requires_frontend_integration": True,
            "next_steps": [
                "Store workflow state in session management system",
                "Implement workflow continuation from user_approval node", 
                "Add frontend UI for user approval decisions",
                "Create API endpoint for user decision submission"
            ]
        }
    
    def get_user_approval_summary(self, session_id: str) -> Dict[str, Any]:
        """
        Get the current QA feedback summary for user approval
        
        Returns the QA evaluation results formatted for user decision making
        """
        # In a real implementation, this would retrieve from session storage
        return {
            "session_id": session_id,
            "qa_feedback": [],
            "current_quality": "unknown",
            "improvement_areas": [],
            "requires_session_management": True
        }
    
    # ============================================================================
    # AGENT IMPLEMENTATIONS
    # ============================================================================
    
    async def _composer_agent(self, state: SongState) -> SongState:
        """
        ComposerAgent: Defines global musical parameters
        - tempo, key, timeSignature, estimated duration
        """
        state.current_agent = "composer"
        logger.info("🎼 ComposerAgent: Starting composition parameters...")
        
        # Send progress update if callback is available
        if self.progress_callback:
            try:
                base_progress = 15
                adjusted_progress = self._calculate_restart_adjusted_progress(base_progress, state)
                restart_message = f" (restart {state.qa_restart_count})" if state.qa_restart_count > 0 else ""
                await self._safe_progress_callback(f"Composer: Setting tempo, key, and structure...{restart_message}", adjusted_progress, "composer")
            except Exception as e:
                logger.warning(f"Progress callback failed: {e}")
        
        # Map user duration preference to actual seconds/bars
        duration_mapping = {
            'short': {'seconds': 120, 'bars': 32},    # 2 minutes
            'medium': {'seconds': 180, 'bars': 48},   # 3 minutes  
            'long': {'seconds': 300, 'bars': 80}      # 5 minutes
        }
        
        preferred_duration = duration_mapping.get(state.request.duration, {'seconds': 180, 'bars': 48})
        
        # Build QA feedback context if this is a restart
        qa_context = ""
        if state.qa_restart_count > 0 and state.qa_feedback:
            qa_context = f"""
🔄 QA RESTART CONTEXT (Attempt {state.qa_restart_count + 1}):
Previous iteration had issues that need addressing:
{chr(10).join(f"- {str(feedback)}" for feedback in self._ensure_string_list(state.qa_feedback))}

Please specifically address these issues in your composition choices.
"""
        
        prompt = f"""You are a professional music composer. Based on the song request, define the global musical parameters.

{qa_context}
Song Request:
- Idea: {state.request.song_idea}
- Style Tags: {self._format_style_tags(state.request.style_tags)}
- Custom Style: {state.request.custom_style}
- Duration Preference: {state.request.duration or 'Not specified'} (target: ~{preferred_duration['seconds']} seconds)
- Key Preference: {state.request.song_key or 'Not specified'}
- Instrumental: {state.request.is_instrumental}

Available Instruments:
{self.music_tools.format_instruments_for_prompt(state.available_instruments)}

Define the global musical parameters that will guide the entire song creation process. 
Consider the style requirements carefully - different genres have distinct characteristics.

Respond ONLY with a JSON object:
{{
    "tempo": 120,
    "key": "C",
    "timeSignature": [4, 4],
    "duration": {preferred_duration['seconds']},
    "estimated_bars": {preferred_duration['bars']},
    "reasoning": "Brief explanation of choices based on style and requirements"
}}

Style-specific tempo guidelines:
- Ballad/Slow: 60-80 BPM
- Pop/Rock: 120-140 BPM  
- EDM/Dance: 128-140 BPM
- Hip-Hop: 70-140 BPM
- Jazz: 120-180 BPM
- Classical: Variable 60-120 BPM

Key selection guidelines:
- Major keys: Happy, bright, uplifting moods
- Minor keys: Sad, dark, mysterious, intense moods
- Consider vocal range if not instrumental
- Honor user preference if specified
"""
        
        try:
            logger.info("🎼 ComposerAgent: Starting composition parameters generation...")
            response = await self._call_llm_safely(prompt)
            logger.info("🎼 ComposerAgent: Received LLM response, parsing JSON...")
            
            # Create fallback data for composer agent
            fallback_data = {
                "tempo": 120,
                "key": state.request.song_key or "C",
                "timeSignature": [4, 4],
                "duration": preferred_duration['seconds'],
                "estimated_bars": preferred_duration['bars'],
                "reasoning": "Using fallback parameters due to JSON parsing error"
            }
            
            result = self._safe_json_parse(response, fallback_data)
            
            state.global_params = {
                "tempo": max(60, min(200, result.get("tempo", 120))),  # Clamp tempo
                "key": result.get("key", state.request.song_key or "C"),
                "timeSignature": result.get("timeSignature", [4, 4]),
                "duration": max(60, min(600, result.get("duration", preferred_duration['seconds']))),  # 1-10 minutes
                "estimated_bars": result.get("estimated_bars", preferred_duration['bars']),
                "reasoning": result.get("reasoning", "")
            }
            
            # Initialize song metadata with better title extraction
            song_title = self._extract_song_title(state.request.song_idea)
            state.song_metadata = {
                "id": f"song-{uuid.uuid4()}",
                "name": song_title,
                "createdAt": datetime.now().isoformat(),
                "updatedAt": datetime.now().isoformat()
            }
            
            logger.info(f"🎼 ComposerAgent: Set {state.global_params['tempo']} BPM, {state.global_params['key']} key, {state.global_params['duration']}s - {state.global_params['reasoning']}")
            
        except Exception as e:
            safe_log_error(f"Composer agent error: {e}")
            state.errors.append(f"Composer: {str(e)}")
            # Use intelligent defaults based on request
            default_tempo = 120
            if any(style in ['ballad', 'slow', 'ambient'] for style in state.request.style_tags):
                default_tempo = 70
            elif any(style in ['edm', 'dance', 'electronic'] for style in state.request.style_tags):
                default_tempo = 128
            
            state.global_params = {
                "tempo": default_tempo,
                "key": state.request.song_key or "C",
                "timeSignature": [4, 4],
                "duration": preferred_duration['seconds'],
                "estimated_bars": preferred_duration['bars'],
                "reasoning": "Using intelligent defaults based on style tags"
            }
        
        return state
    
    async def _arrangement_agent(self, state: SongState) -> SongState:
        """
        ArrangementAgent: Determines song structure and track layout
        - Song sections (intro, verse, chorus, etc.) and timing
        - Track count and types (vocal/instrument/sample)
        - Strategic planning for the entire song arrangement
        """
        state.current_agent = "arrangement"
        logger.info("🎹 ArrangementAgent: Creating song structure and track layout...")
        
        # Send progress update if callback is available
        if self.progress_callback:
            try:
                await self._safe_progress_callback("Arrangement: Designing song sections and tracks...", 25, "arrangement")
            except Exception as e:
                logger.warning(f"Progress callback failed: {e}")
        
        # Calculate timing based on tempo and duration
        tempo = state.global_params.get('tempo', 120)
        duration_seconds = state.global_params.get('duration', 180)
        
        # Safeguard against division by zero
        if duration_seconds <= 0:
            logger.warning(f"Invalid duration {duration_seconds}, defaulting to 180 seconds")
            duration_seconds = 180
        
        bars_per_minute = tempo / 4  # Assuming 4/4 time signature
        total_bars = int((duration_seconds / 60) * bars_per_minute)
        
        # Build QA feedback context if this is a restart
        qa_context = ""
        if state.qa_restart_count > 0 and state.qa_feedback:
            # Filter QA feedback to only include relevant issues for this track type
            # First, ensure all qa_feedback items are strings
            string_feedback_list = self._ensure_string_list(state.qa_feedback)
            relevant_feedback = []
            
            for feedback_str in string_feedback_list:
                feedback_lower = feedback_str.lower()
                # Skip vocal/lyrics feedback for instrumental tracks
                if state.request.is_instrumental:
                    if any(vocal_kw in feedback_lower for vocal_kw in ['vocal', 'voice', 'singing', 'singer', 'lyrics', 'lyric']):
                        # Skip this feedback for instrumental tracks unless it's about missing instrumental equivalent
                        if 'missing vocals track' in feedback_lower:
                            # Convert to instrumental context
                            relevant_feedback.append("structure: Focus on lead instrumental tracks for melody instead of vocal tracks")
                        continue
                    else:
                        relevant_feedback.append(feedback_str)
                else:
                    # Include all feedback for vocal tracks
                    relevant_feedback.append(feedback_str)
            
            if relevant_feedback:
                track_type = "instrumental" if state.request.is_instrumental else "vocal"
                qa_context = f"""
🔄 QA RESTART CONTEXT (Attempt {state.qa_restart_count + 1}) for {track_type.upper()} track:
Previous arrangement had issues that need addressing:
{chr(10).join(f"- {feedback}" for feedback in relevant_feedback)}

Please specifically address these structural and track arrangement issues.
Pay special attention to:
{"- Creating lead instrumental tracks for melody (NO vocal tracks needed)" if state.request.is_instrumental else "- Ensuring vocal tracks are included if lyrics are present"}
- Adding drum/bass tracks for rhythmic foundation
- Creating sufficient track variety for full arrangement
- Proper section structure and timing
"""
        
        prompt = f"""You are a music arranger. Design the song structure and track arrangement for a complete, professional-sounding song.

{qa_context}
Song Parameters:
- Tempo: {tempo} BPM
- Key: {state.global_params.get('key')}
- Total Duration: {duration_seconds} seconds (~{total_bars} bars)
- Time Signature: {state.global_params.get('timeSignature')}
- Style: {self._format_style_tags(state.request.style_tags)} {state.request.custom_style}
- Instrumental: {state.request.is_instrumental}
- Song Idea: {state.request.song_idea}

Available Instruments by Category:
{self.music_tools.format_instruments_for_prompt(state.available_instruments)}

Available User-Uploaded Samples:
{self.music_tools.format_samples_for_prompt(state.available_user_samples) if state.available_user_samples else "No user samples available"}

{f"Sample Library Analysis - Total Available: {state.sample_metadata.get('total_count', 0)} samples ({state.sample_metadata.get('user_count', 0)} user-uploaded)" if state.sample_metadata else ""}

Available Voices: {list(state.available_voices.keys())}

Design a complete song arrangement. Respond ONLY with a JSON object:

EXAMPLE FOR VOCAL TRACK:
{{
    "structure": {{
        "intro": {{"start_time": 0, "duration": 8, "bars": 4, "description": "Gentle piano introduction"}},
        "verse1": {{"start_time": 8, "duration": 16, "bars": 8, "description": "First verse with vocals and light accompaniment"}},
        "chorus1": {{"start_time": 24, "duration": 16, "bars": 8, "description": "Full arrangement chorus with all instruments"}},
        "bridge": {{"start_time": 72, "duration": 12, "bars": 6, "description": "Bridge section with key/mood change"}},
        "outro": {{"start_time": 104, "duration": 12, "bars": 6, "description": "Fade out with main melody"}}
    }},
    "tracks_needed": [
        {{
            "name": "Lead Vocals",
            "instrument": "vocals",
            "category": "vocal",
            "role": "melodic",
            "voice_id": "soprano01",
            "priority": "high",
            "sections": ["verse1", "chorus1", "bridge"],
            "pan": 0.0,
            "volume": 0.8
        }},
        {{
            "name": "Piano",
            "instrument": "piano", 
            "category": "keyboards",
            "role": "harmonic",
            "priority": "high",
            "sections": ["intro", "verse1", "chorus1", "bridge", "outro"],
            "pan": 0.0,
            "volume": 0.7
        }}
    ]
}}

EXAMPLE FOR INSTRUMENTAL TRACK:
{{
    "structure": {{
        "intro": {{"start_time": 0, "duration": 8, "bars": 4, "description": "Piano and strings introduction"}},
        "theme_a": {{"start_time": 8, "duration": 24, "bars": 12, "description": "Main melodic theme with full arrangement"}},
        "theme_b": {{"start_time": 32, "duration": 24, "bars": 12, "description": "Secondary theme with different instrumentation"}},
        "development": {{"start_time": 56, "duration": 32, "bars": 16, "description": "Development section with layered instruments"}},
        "recapitulation": {{"start_time": 88, "duration": 24, "bars": 12, "description": "Return to main theme with full orchestra"}},
        "outro": {{"start_time": 112, "duration": 16, "bars": 8, "description": "Fade out with main melody"}}
    }},
    "tracks_needed": [
        {{
            "name": "Lead Piano",
            "instrument": "piano", 
            "category": "keyboards",
            "role": "melodic",
            "priority": "high",
            "sections": ["intro", "theme_a", "theme_b", "development", "recapitulation", "outro"],
            "pan": 0.0,
            "volume": 0.8
        }},
        {{
            "name": "Strings",
            "instrument": "violin",
            "category": "strings",
            "role": "harmonic",
            "priority": "high",
            "sections": ["theme_a", "theme_b", "development", "recapitulation"],
            "pan": -0.3,
            "volume": 0.7
        }},
        {{
            "name": "Bass",
            "instrument": "bass",
            "category": "strings", 
            "role": "rhythmic",
            "priority": "medium",
            "sections": ["theme_a", "theme_b", "development", "recapitulation"],
            "pan": 0.0,
            "volume": 0.8
        }}
    ],
    "arrangement_philosophy": "Instrumental focus with melodic interplay between piano, strings, and bass",
    "total_tracks": 3,
    "complexity_level": "medium"
}}

Guidelines:
- Create a logical song structure that builds energy and maintains interest
- Plan 3-8 tracks typically, depending on style complexity  
- CRITICAL: Use ONLY instruments from the available_instruments list above - NO other instruments
- PRIORITY: When selecting instruments, prioritize ones that have user-uploaded samples available (check Available User-Uploaded Samples section)
- USER SAMPLE STRATEGY: If user has uploaded samples in relevant categories, incorporate instruments that can utilize those samples
- CRITICAL FOR INSTRUMENTAL TRACKS: DO NOT include any vocal tracks or voice_id assignments
- Include appropriate tracks for the style (rock: drums+bass+guitar, jazz: piano+bass+drums, orchestral: strings+brass+woodwinds, etc.)
- For instrumental tracks: Focus on melodic instruments that can carry the main themes
- Each track should have a clear role: melodic (lead lines), harmonic (chords), rhythmic (beat/groove), textural (atmosphere)
- Consider arrangement dynamics (intro lighter, main sections fuller, bridge different)
- Plan which sections each track will play in (not all tracks play throughout)
- Use appropriate pan positions for stereo field
- Match instruments to style requirements from available options only
- Consider user sample metadata (BPM, key, tags) when planning arrangement to make best use of uploaded samples
- Instrument Selection Rules:
  * For keyboards role: choose from available keyboards instruments
  * For strings role: choose from available strings instruments  
  * For percussion role: choose from available percussion instruments
  * For vocal role: ONLY if NOT instrumental - use "vocals" with voice_id from available voices
- If instrumental, focus on interesting melodic interplay between available instruments
- Ensure total duration matches the target ({duration_seconds} seconds)
- Verify each planned instrument exists in the available_instruments before including it
"""
        
        try:
            logger.info("🎹 ArrangementAgent: Starting arrangement generation...")
            response = await self._call_llm_safely(prompt)
            logger.info("🎹 ArrangementAgent: Received LLM response, parsing JSON...")
            
            # Create fallback data in case of JSON parsing failure
            fallback_data = {
                "structure": self._create_default_structure(duration_seconds, state.request.style_tags),
                "tracks_needed": self._create_default_tracks(state.request.is_instrumental, state.request.style_tags, state.available_instruments),
                "arrangement_philosophy": "Using intelligent default arrangement due to parsing error",
                "total_tracks": 4,
                "complexity_level": "medium"
            }
            
            result = self._safe_json_parse(response, fallback_data)
            
            structure = result.get("structure", {})
            planned_tracks = result.get("tracks_needed", [])
            
            # Validate that planned instruments are available and appropriate
            all_available_instruments = set()
            for category, instruments in state.available_instruments.items():
                all_available_instruments.update(instruments)
            all_available_instruments.add("vocals")  # Vocals are always available
            
            validated_tracks = []
            for track in planned_tracks:
                instrument = track.get('instrument')
                category = track.get('category', '')
                
                # Skip vocal tracks for instrumental songs
                if state.request.is_instrumental and (instrument == "vocals" or track.get('category') == 'vocal'):
                    logger.info(f"🎹 ArrangementAgent: Skipping vocal track '{track.get('name')}' - instrumental song")
                    continue
                
                # Normalize instrument name and fix category if needed
                original_instrument = instrument
                normalized_instrument = self.music_tools.normalize_instrument_name(instrument, category)
                corrected_category = self.music_tools.validate_instrument_category(normalized_instrument, category)
                
                # Update track with normalized values
                if normalized_instrument != original_instrument:
                    logger.info(f"🎹 ArrangementAgent: Normalized instrument '{original_instrument}' -> '{normalized_instrument}'")
                    track['instrument'] = normalized_instrument
                
                if corrected_category != category:
                    logger.info(f"🎹 ArrangementAgent: Corrected category '{category}' -> '{corrected_category}' for {normalized_instrument}")
                    track['category'] = corrected_category
                
                if normalized_instrument in all_available_instruments:
                    validated_tracks.append(track)
                else:
                    logger.warning(f"🎹 ArrangementAgent: Skipping unavailable instrument: {normalized_instrument}")
                    # Try to find a suitable replacement from the corrected category
                    available_in_category = state.available_instruments.get(corrected_category, [])
                    if available_in_category:
                        replacement = available_in_category[0]
                        track['instrument'] = replacement
                        track['category'] = corrected_category
                        track['name'] = track['name'].replace(original_instrument, replacement.replace('_', ' ').title())
                        validated_tracks.append(track)
                        logger.info(f"🎹 ArrangementAgent: Replaced {normalized_instrument} with {replacement}")
                    else:
                        logger.warning(f"🎹 ArrangementAgent: No replacement found for {normalized_instrument} in category {corrected_category}")
            
            planned_tracks = validated_tracks
            
            # Validate and adjust structure timing to fit target duration
            total_structure_time = 0
            for section_name, section_info in structure.items():
                section_duration = section_info.get("duration", 8)
                total_structure_time = max(total_structure_time, 
                                         section_info.get("start_time", 0) + section_duration)
            
            # Scale if necessary to fit target duration
            if abs(total_structure_time - duration_seconds) > 10 and total_structure_time > 0:  # More than 10 seconds off and valid time
                scale_factor = duration_seconds / total_structure_time
                for section_info in structure.values():
                    section_info["start_time"] = int(section_info["start_time"] * scale_factor)
                    section_info["duration"] = int(section_info["duration"] * scale_factor)
            elif total_structure_time <= 0:
                logger.warning(f"Invalid total_structure_time {total_structure_time}, using default structure timing")
            
            state.arrangement = {
                "structure": structure,
                "planned_tracks": planned_tracks,
                "arrangement_philosophy": result.get("arrangement_philosophy", ""),
                "total_tracks": len(planned_tracks),
                "complexity_level": result.get("complexity_level", "medium")
            }
            
            logger.info(f"🎹 ArrangementAgent: Created {len(planned_tracks)} tracks with {len(structure)} sections")
            
        except Exception as e:
            safe_log_error(f"Arrangement agent error: {e}")
            state.errors.append(f"Arrangement: {str(e)}")
            
            # Create intelligent default arrangement based on style and requirements
            default_structure = self._create_default_structure(duration_seconds, state.request.style_tags)
            default_tracks = self._create_default_tracks(state.request.is_instrumental, state.request.style_tags, state.available_instruments)
            
            state.arrangement = {
                "structure": default_structure,
                "planned_tracks": default_tracks,
                "arrangement_philosophy": "Using intelligent default arrangement due to parsing error",
                "total_tracks": len(default_tracks),
                "complexity_level": "medium"
            }
        
        return state
    
    def _create_default_structure(self, duration_seconds: int, style_tags: List[str]) -> Dict[str, Dict[str, Any]]:
        """Create a sensible default song structure based on duration and style."""
        # Simple but effective default structure
        if duration_seconds < 120:  # Short song
            return {
                "intro": {"start_time": 0, "duration": 8, "bars": 4},
                "verse": {"start_time": 8, "duration": 32, "bars": 16},
                "chorus": {"start_time": 40, "duration": 32, "bars": 16},
                "outro": {"start_time": 72, "duration": 16, "bars": 8}
            }
        else:  # Standard length
            return {
                "intro": {"start_time": 0, "duration": 8, "bars": 4},
                "verse1": {"start_time": 8, "duration": 24, "bars": 12},
                "chorus1": {"start_time": 32, "duration": 24, "bars": 12},
                "verse2": {"start_time": 56, "duration": 24, "bars": 12},
                "chorus2": {"start_time": 80, "duration": 24, "bars": 12},
                "bridge": {"start_time": 104, "duration": 16, "bars": 8},
                "final_chorus": {"start_time": 120, "duration": 32, "bars": 16},
                "outro": {"start_time": 152, "duration": 16, "bars": 8}
            }
    
    def _create_default_tracks(self, is_instrumental: bool, style_tags: List[str], available_instruments: Dict[str, List[str]] = None) -> List[Dict[str, Any]]:
        """Create default track layout based on whether instrumental and style."""
        tracks = []
        
        # Use available instruments if provided, otherwise use fallback
        if not available_instruments:
            available_instruments = {
                "keyboards": ["piano", "organ", "electric_piano", "synthesizer"],
                "strings": ["guitar", "bass", "violin", "cello"],
                "percussion": ["drums", "tambourine", "shaker", "bells"],
                "vocal": ["vocals"]
            }
        
        # Always include a keyboard instrument as foundation if available
        keyboard_instruments = available_instruments.get('keyboards', [])
        if keyboard_instruments:
            keyboard_choice = "piano" if "piano" in keyboard_instruments else keyboard_instruments[0]
            tracks.append({
                "name": keyboard_choice.title(),
                "instrument": keyboard_choice,
                "category": "keyboards",
                "role": "harmonic",
                "priority": "high",
                "sections": ["intro", "verse1", "chorus1", "verse2", "chorus2", "bridge", "final_chorus", "outro"],
                "pan": 0.0,
                "volume": 0.7
            })
        
        # Add vocals if not instrumental
        if not is_instrumental:
            tracks.append({
                "name": "Lead Vocals",
                "instrument": "vocals", 
                "category": "vocal",
                "role": "melodic",
                "voice_id": "soprano01",
                "priority": "high",
                "sections": ["verse1", "chorus1", "verse2", "chorus2", "bridge", "final_chorus"],
                "pan": 0.0,
                "volume": 0.8
            })
        
        # Add style-appropriate instruments from available options
        if any(style in ['rock', 'pop', 'alternative'] for style in style_tags):
            # Add bass if available
            string_instruments = available_instruments.get('strings', [])
            if string_instruments:
                bass_choice = "bass" if "bass" in string_instruments else string_instruments[0]
                tracks.append({
                    "name": bass_choice.title(),
                    "instrument": bass_choice,
                    "category": "strings",
                    "role": "rhythmic", 
                    "priority": "medium",
                    "sections": ["verse1", "chorus1", "verse2", "chorus2", "bridge", "final_chorus"],
                    "pan": 0.0,
                    "volume": 0.8
                })
            
            # Add drums if available
            percussion_instruments = available_instruments.get('percussion', [])
            if percussion_instruments:
                drum_choice = "drums" if "drums" in percussion_instruments else percussion_instruments[0]
                tracks.append({
                    "name": drum_choice.title(),
                    "instrument": drum_choice,
                    "category": "percussion",
                    "role": "rhythmic",
                    "priority": "medium", 
                    "sections": ["chorus1", "verse2", "chorus2", "bridge", "final_chorus"],
                    "pan": 0.0,
                    "volume": 0.6
                })
        
        return tracks
    
    async def _lyrics_agent(self, state: SongState) -> SongState:
        """
        LyricsAgent: Creates lyrics aligned with structure and musical parameters
        - Section-specific lyrics matching song structure timing
        - Rhyme schemes and meter appropriate to tempo and style
        - Emotional alignment with request and arrangement
        
        CRITICAL PROTECTION: This agent should NEVER be called for instrumental tracks.
        If called inappropriately, it will bypass all processing and return minimal state.
        """
        state.previous_agent = state.current_agent
        state.current_agent = "lyrics"
        
        # Add workflow routing diagnostics
        logger.info(f"🚦 WORKFLOW ROUTING: Lyrics agent called")
        logger.info(f"🚦 WORKFLOW STATE: is_instrumental={state.request.is_instrumental}")
        logger.info(f"🚦 WORKFLOW STATE: qa_restart_count={state.qa_restart_count}")
        logger.info(f"🚦 WORKFLOW STATE: previous_agent={getattr(state, 'previous_agent', 'unknown')}")
        logger.info(f"🚦 WORKFLOW STATE: current_agent={getattr(state, 'current_agent', 'unknown')}")
        logger.info(f"🚦 WORKFLOW STATE: user_decision={getattr(state, 'user_decision', 'none')}")
        
        # PRIMARY PROTECTION: Immediately exit for instrumental tracks
        if state.request.is_instrumental:
            logger.warning("🚨 CRITICAL PROTECTION: Lyrics agent called for instrumental track - bypassing all processing!")
            logger.error("🚨 WORKFLOW BUG: LangGraph routing failed to prevent lyrics agent execution for instrumental track")
            logger.error(f"🚨 DEBUG INFO: Previous agent: {getattr(state, 'previous_agent', 'unknown')}")
            logger.error(f"🚨 DEBUG INFO: QA restart count: {state.qa_restart_count}")
            logger.error(f"🚨 DEBUG INFO: User decision: {getattr(state, 'user_decision', 'none')}")
            
            # Create minimal lyrics state for instrumental tracks
            state.lyrics = {
                "content": "",
                "sections": {},
                "is_instrumental": True,
                "overall_theme": "Instrumental composition",
                "reasoning": "PROTECTION BYPASS: Instrumental track - no lyrics needed"
            }
            
            # Ensure vocal assignments exist for downstream agents
            if not hasattr(state, 'vocal_assignments') or not state.vocal_assignments:
                state.vocal_assignments = {
                    "tracks": [],
                    "is_instrumental": True,
                    "voice_assignments": {},
                    "reasoning": "PROTECTION BYPASS: Instrumental track - no vocals needed"
                }
            
            logger.warning("📝 LyricsAgent: PROTECTION BYPASS completed - instrumental track")
            return state
        
        # Send progress update if callback is available
        if self.progress_callback:
            try:
                await self._safe_progress_callback("Lyrics: Writing song lyrics...", 35, "lyrics")
            except Exception as e:
                logger.warning(f"Progress callback failed: {e}")
        
        if state.request.is_instrumental:
            state.lyrics = {
                "content": "",
                "sections": {},
                "is_instrumental": True,
                "overall_theme": "Instrumental composition",
                "reasoning": "Instrumental track - no lyrics needed"
            }
            # Initialize vocal assignments for instrumental tracks to ensure downstream agents have this data
            state.vocal_assignments = {
                "tracks": [],
                "is_instrumental": True,
                "voice_assignments": {},
                "reasoning": "Instrumental track - no vocals needed"
            }
            logger.info("📝 LyricsAgent: Completed - instrumental track (vocal assignments initialized)")
            logger.info(f"📝 LyricsAgent: State is_instrumental flag = {state.request.is_instrumental}")
            return state
        
        if state.request.lyrics_option == "custom" and state.request.custom_lyrics:
            # Use provided custom lyrics
            sections = self._parse_custom_lyrics(state.request.custom_lyrics, state.arrangement["structure"])
            state.lyrics = {
                "content": state.request.custom_lyrics,
                "sections": sections,
                "is_custom": True,
                "overall_theme": "User-provided custom lyrics",
                "writing_style": "Custom user content"
            }
            logger.info("📝 LyricsAgent: Using custom user lyrics")
            return state
        
        # Get song structure and timing info
        structure = state.arrangement.get('structure', {})
        tempo = state.global_params.get('tempo', 120)
        key = state.global_params.get('key', 'C major')
        
        # Calculate syllable targets based on tempo and section durations
        syllable_guidance = self._calculate_syllable_targets(structure, tempo)
        
        prompt = f"""You are a professional lyricist. Write complete, emotionally resonant lyrics for this song.

Song Context:
- Core Idea: {state.request.song_idea}
- Musical Style: {self._format_style_tags(state.request.style_tags)} {state.request.custom_style}
- Emotional Mood: {state.request.mood}
- Key: {key}
- Tempo: {tempo} BPM
- Arrangement Philosophy: {state.arrangement.get('arrangement_philosophy', 'Not specified')}

Song Structure & Timing:
{json.dumps(structure, indent=2)}

Syllable Guidance (for singability):
{json.dumps(syllable_guidance, indent=2)}

Write complete lyrics for each section. Respond ONLY with a JSON object:
{{
    "sections": {{
        "intro": ["Optional intro vocals", "Setting the scene"],
        "verse1": ["First verse line telling the story", "Second line developing the theme", "Third line adding detail and depth", "Fourth line leading to the chorus"],
        "chorus1": ["Memorable hook that captures the essence", "Easy to sing and emotionally strong", "Repeatable phrase that stays with listeners", "Powerful message that drives the song"],
        "verse2": ["Second verse building on the story", "Adding new details and perspectives", "Deepening the emotional connection", "Leading naturally to the chorus"],
        "bridge": ["Bridge offers new perspective", "Shifts the emotional tone", "Provides contrast and release", "Builds toward the final section"],
        "final_chorus": ["Final chorus with full power", "May add new layers or variations", "Brings the emotional journey home", "Leaves lasting impression on listener"]
    }},
    "overall_theme": "Central message, story, or emotional journey",
    "writing_style": "Specific approach: conversational, poetic, narrative, impressionistic, etc.",
    "emotional_arc": "How emotions develop and resolve through the song",
    "rhyming_philosophy": "Explanation of rhyme scheme choices",
    "tempo_considerations": "How lyrics are crafted for the {tempo} BPM tempo",
    "mood": "Overall emotional mood of the lyrics"
}}

Critical Guidelines:
- Write complete, singable lyrics for EVERY section that has vocals in the arrangement
- Match syllable counts roughly to timing targets (but prioritize natural flow)
- Create emotional progression: verses tell story, chorus delivers impact, bridge provides contrast
- Use rhyme schemes appropriate to style: pop/rock (ABAB), ballads (AABA), rap (complex)
- Consider tempo: faster songs need fewer syllables per beat, slower songs allow more complex phrasing
- Make chorus instantly memorable and easy to sing along
- Ensure verses advance the narrative or emotional development
- Bridge should offer new perspective, key change preparation, or emotional pivot
- All sections should flow naturally when sung at {tempo} BPM
- Match emotional intensity to arrangement energy levels
- Create coherent story/theme that serves the song idea: "{state.request.song_idea}"
"""
        
        try:
            response = await self._call_llm_safely(prompt)
            
            # Handle empty or whitespace-only responses
            if not response or not response.strip():
                raise ValueError("LLM returned empty response for lyrics generation")
            
            # Clean response and validate JSON
            cleaned_response = response.strip()
            if not cleaned_response.startswith('{') or not cleaned_response.endswith('}'):
                # Try to extract JSON from response if it contains other text
                import re
                json_match = re.search(r'\{.*\}', cleaned_response, re.DOTALL)
                if json_match:
                    cleaned_response = json_match.group(0)
                else:
                    raise ValueError(f"No valid JSON found in lyrics agent response: {cleaned_response[:200]}...")
            
            result = json.loads(cleaned_response)
            
            sections = result.get("sections", {})
            
            # Validate that we have lyrics for sections that need them
            vocal_sections = self._identify_vocal_sections(state.arrangement)
            missing_sections = [section for section in vocal_sections if section not in sections]
            
            if missing_sections:
                logger.warning(f"📝 LyricsAgent: Missing lyrics for vocal sections: {missing_sections}")
                # Add basic lyrics for missing sections
                for section in missing_sections:
                    sections[section] = [
                        "Placeholder lyrics for this section",
                        "Need to be developed further"
                    ]
            
            # Flatten sections into single content string
            all_lyrics = []
            for section, lines in sections.items():
                if lines:
                    all_lyrics.extend(lines)
            
            state.lyrics = {
                "content": "\n".join(all_lyrics),
                "sections": sections,
                "overall_theme": result.get("overall_theme", ""),
                "writing_style": result.get("writing_style", ""),
                "emotional_arc": result.get("emotional_arc", ""),
                "rhyming_philosophy": result.get("rhyming_philosophy", ""),
                "tempo_considerations": result.get("tempo_considerations", ""),
                "mood": result.get("mood", ""),
                "total_sections": len(sections),
                "is_generated": True
            }
            
            logger.info(f"📝 LyricsAgent: Created lyrics for {len(sections)} sections")
            
        except Exception as e:
            safe_log_error(f"Lyrics agent error: {e}")
            state.errors.append(f"Lyrics: {str(e)}")
            
            # Create intelligent default lyrics based on song idea and structure
            default_sections = self._create_default_lyrics(state.request.song_idea, structure, state.request.mood)
            
            # Flatten sections into single content string
            all_lyrics = []
            for section, lines in default_sections.items():
                if lines:
                    all_lyrics.extend(lines)
            
            state.lyrics = {
                "content": "\n".join(all_lyrics),
                "sections": default_sections,
                "overall_theme": f"Song about {state.request.song_idea}",
                "writing_style": "Simple and direct",
                "emotional_arc": "Building emotional intensity",
                "reasoning": "Using default lyrics due to generation error",
                "error": str(e)
            }
        
        return state
    
    def _calculate_syllable_targets(self, structure: Dict[str, Dict], tempo: int) -> Dict[str, int]:
        """Calculate approximate syllable targets for each section based on tempo and duration."""
        syllable_guidance = {}
        
        # Rough guide: ~2-4 syllables per beat depending on style
        syllables_per_second = tempo / 60 * 2.5  # Average 2.5 syllables per beat
        
        for section_name, section_info in structure.items():
            duration = section_info.get('duration', 8)
            target_syllables = int(duration * syllables_per_second)
            syllable_guidance[section_name] = target_syllables
        
        return syllable_guidance
    
    def _identify_vocal_sections(self, arrangement: Dict[str, Any]) -> List[str]:
        """Identify which sections should have vocals based on the arrangement."""
        planned_tracks = arrangement.get('planned_tracks', [])
        vocal_sections = set()
        
        for track in planned_tracks:
            if track.get('category') == 'vocal' or track.get('instrument') == 'vocals':
                sections = track.get('sections', [])
                vocal_sections.update(sections)
        
        return list(vocal_sections)
    
    def _create_default_lyrics(self, song_idea: str, structure: Dict[str, Dict], mood: str) -> Dict[str, List[str]]:
        """Create simple default lyrics based on song context."""
        sections = {}
        
        # Create basic lyrics for main sections
        if 'verse1' in structure or 'verse' in structure:
            sections['verse1'] = [
                f"This song is about {song_idea}",
                "Telling the story as it unfolds",
                f"With {mood} feeling in every line", 
                "Building to something strong"
            ]
        
        if 'chorus1' in structure or 'chorus' in structure:
            sections['chorus1'] = [
                "This is the heart of our song",
                f"Where {mood} emotions ring true",
                "A melody that carries us along",
                "Making the message come through"
            ]
        
        if 'verse2' in structure:
            sections['verse2'] = [
                f"The second part of {song_idea}",
                "Takes us deeper into the theme",
                "With every word we're getting closer",
                "To fulfilling this musical dream"
            ]
        
        if 'bridge' in structure:
            sections['bridge'] = [
                "Here's where we change perspective",
                f"See {song_idea} in new light",
                f"This {mood} feeling so reflective",
                "Guides us through to what feels right"
            ]
        
        return sections
    
    async def _vocal_agent(self, state: SongState) -> SongState:
        """
        VocalAgent: Assigns voices to lyrics and creates vocal clips
        - Maps lyrics to melodic lines with notes and durations  
        - Creates polyphonic vocal clips using available_voices
        - Handles lead vocals, harmonies, and backing vocals
        """
        state.previous_agent = state.current_agent
        state.current_agent = "vocal"
        
        # Add workflow routing diagnostics
        logger.info(f"🚦 WORKFLOW ROUTING: Vocal agent called")
        logger.info(f"🚦 WORKFLOW STATE: is_instrumental={state.request.is_instrumental}")
        logger.info(f"🚦 WORKFLOW STATE: qa_restart_count={state.qa_restart_count}")
        logger.info(f"🚦 WORKFLOW STATE: previous_agent={getattr(state, 'previous_agent', 'unknown')}")
        
        # EMERGENCY SAFEGUARD: Never run vocal agent for instrumental tracks
        if state.request.is_instrumental:
            logger.warning("🚨 EMERGENCY BYPASS: Vocal agent called for instrumental track - this indicates a workflow routing bug!")
            logger.error("🚨 CRITICAL BUG: LangGraph conditional edges failed to prevent vocal agent execution for instrumental track")
            state.vocal_assignments = {
                "tracks": [],
                "is_instrumental": True,
                "voice_assignments": {},
                "reasoning": "EMERGENCY BYPASS: Instrumental track - no vocals needed"
            }
            logger.warning("🎤 VocalAgent: EMERGENCY BYPASS completed - instrumental track")
            return state

        # Send progress update only if we're actually processing vocals
        if self.progress_callback:
            try:
                await self._safe_progress_callback("Vocal: Assigning voices and vocal parts...", 45, "vocal")
            except Exception as e:
                logger.warning(f"Progress callback failed: {e}")
        
        # Get vocal tracks from arrangement and song structure
        planned_vocal_tracks = [t for t in state.arrangement.get('planned_tracks', []) 
                               if t.get('category') == 'vocal' or t.get('instrument') == 'vocals']
        structure = state.arrangement.get('structure', {})
        lyrics_sections = state.lyrics.get('sections', {})
        
        # Musical parameters for melody generation
        key = state.global_params.get('key', 'C major')
        tempo = state.global_params.get('tempo', 120)
        time_signature = state.global_params.get('timeSignature', '4/4')
        
        prompt = f"""You are a professional vocal arranger and melody writer. Create detailed vocal assignments that map lyrics to specific notes and timing.

Song Parameters:
- Key: {key}
- Tempo: {tempo} BPM  
- Time Signature: {time_signature}
- Style: {self._format_style_tags(state.request.style_tags)} {state.request.custom_style}

Available Voices and Ranges:
{self.music_tools.format_voices_for_prompt(state.available_voices)}

Lyrics Sections:
{json.dumps(lyrics_sections, indent=2)}

Song Structure (with timing in seconds):
{json.dumps(structure, indent=2)}

Planned Vocal Tracks from Arrangement:
{json.dumps(planned_vocal_tracks, indent=2)}

Create complete vocal track assignments with melodic content. Respond ONLY with a JSON object:
{{
    "tracks": [
        {{
            "id": "track-lead-vocals",
            "name": "Lead Vocals",
            "instrument": "vocals",
            "category": "vocal",
            "voiceId": "soprano01",
            "volume": 0.8,
            "pan": 0.0,
            "muted": false,
            "solo": false,
            "clips": [
                {{
                    "id": "clip-lead-verse1",
                    "trackId": "track-lead-vocals", 
                    "startTime": 8,
                    "duration": 16,
                    "type": "lyrics",
                    "instrument": "vocals",
                    "voiceId": "soprano01",
                    "volume": 0.8,
                    "pan": 0.0,
                    "effects": {{"reverb": 0.2, "delay": 0.1, "distortion": 0}},
                    "sectionId": "verse1",
                    "sectionSpans": ["verse1"],
                    "voices": [
                        {{
                            "voice_id": "soprano01",
                            "lyrics": [
                                {{
                                    "text": "First line of verse lyrics",
                                    "notes": ["C4", "D4", "E4", "F4", "G4"],
                                    "start": 0.0,
                                    "durations": [1.0, 1.0, 0.5, 0.5, 2.0],
                                    "velocities": [80, 75, 85, 80, 90],
                                    "syllables": [
                                        {{"t": "First", "noteIdx": [0], "dur": 1.0}},
                                        {{"t": "line", "noteIdx": [1], "dur": 1.0}},
                                        {{"t": "of", "noteIdx": [2], "dur": 0.5}},
                                        {{"t": "verse", "noteIdx": [3], "dur": 0.5}},
                                        {{"t": "lyrics", "noteIdx": [4], "dur": 2.0}}
                                    ],
                                    "phonemes": ["f", "ɜr", "s", "t", "l", "aɪ", "n", "ʌ", "v", "v", "ɜr", "s", "l", "ɪ", "r", "ɪ", "k", "s"]
                                }},
                                {{
                                    "text": "Second line continues melody",
                                    "notes": ["F4", "E4", "D4", "C4"],
                                    "start": 5.0,
                                    "durations": [1.5, 1.0, 1.0, 1.5],
                                    "velocities": [75, 80, 85, 80],
                                    "syllables": [
                                        {{"t": "Sec", "noteIdx": [0], "dur": 0.7}},
                                        {{"t": "ond", "noteIdx": [0], "dur": 0.8}},
                                        {{"t": "line", "noteIdx": [1], "dur": 1.0}},
                                        {{"t": "con-tin", "noteIdx": [2], "dur": 1.0}},
                                        {{"t": "ues", "noteIdx": [3], "dur": 0.8}},
                                        {{"t": "mel", "noteIdx": [3], "dur": 0.7}}
                                    ],
                                    "phonemes": ["s", "ɛ", "k", "ə", "n", "d", "l", "aɪ", "n", "k", "ə", "n", "t", "ɪ", "n", "j", "u", "z", "m", "ɛ", "l"]
                                }}
                            ]
                        }}
                    ]
                }}
            ]
        }}
    ],
    "voice_assignments": {{
        "lead": "soprano01",
        "harmony": ["alto01"],
        "backing": ["tenor01", "bass01"]
    }},
    "melody_philosophy": "Explanation of melodic choices and vocal arrangement approach",
    "harmonic_structure": "Description of how harmonies support the lead melody",
    "vocal_production_notes": "Guidance for vocal effects, mixing, and production"
}}

Critical Guidelines:
- Create a clip for EVERY lyrical section that appears in the song structure
- Map every line of lyrics to specific notes in the song key: {key}
- Use appropriate vocal ranges for each voice (soprano: C4-C6, alto: G3-G5, tenor: C3-C5, bass: E2-E4)
- Calculate accurate timing: startTime and duration based on structure timing
- Create singable melodies that match the tempo: {tempo} BPM and style
- Include appropriate effects (reverb, delay) for the style
- For harmony tracks, create supporting notes that complement the lead melody
- Use voice_id values that match available voices: {list(state.available_voices.keys())}
- Ensure total clip duration matches the section duration from structure
- Consider vocal production appropriate to style (pop: compressed, classical: natural, etc.)
- Create emotional arc through melody: verses conversational, chorus soaring
- Include backing vocals/harmonies for choruses and final sections
- Map syllables to note timing carefully - avoid cramming too many syllables per beat
- Use velocities (60-100) to create dynamic expression in the vocal performance
- REQUIRED EXTENDED STRUCTURE FIELDS:
  * "sectionId": Must reference the section name (e.g., "verse1", "chorus", "bridge")  
  * "sectionSpans": Array of sections this clip spans (for cross-boundary clips)
  * "syllables": Array of syllable breakdowns with note mapping for each lyric
  * "phonemes": Array of IPA phoneme strings for TTS/singing engines for each lyric
- SYLLABLES FORMAT: {{"t": "syllable_text", "noteIdx": [note_index], "dur": duration, "melisma": true/false}}
- Generate accurate syllable breakdowns that map to note indices within each lyric
- Include IPA phonemes for proper pronunciation in singing synthesis engines
- Ensure syllables and phonemes arrays are provided for every lyric entry
"""
        
        try:
            response = await self._call_llm_safely(prompt)
            
            # Handle empty or whitespace-only responses
            if not response or not response.strip():
                raise ValueError("LLM returned empty response for vocal arrangement")
            
            # Clean response and validate JSON
            cleaned_response = response.strip()
            if not cleaned_response.startswith('{') or not cleaned_response.endswith('}'):
                # Try to extract JSON from response if it contains other text
                import re
                json_match = re.search(r'\{.*\}', cleaned_response, re.DOTALL)
                if json_match:
                    cleaned_response = json_match.group(0)
                else:
                    raise ValueError(f"No valid JSON found in vocal agent response: {cleaned_response[:200]}...")
            
            result = json.loads(cleaned_response)
            
            tracks = result.get("tracks", [])
            voice_assignments = result.get("voice_assignments", {})
            
            # Validate that all planned vocal tracks have been created
            planned_track_names = [t.get('name', '') for t in planned_vocal_tracks]
            created_track_names = [t.get('name', '') for t in tracks]
            
            missing_tracks = [name for name in planned_track_names if name not in created_track_names]
            if missing_tracks:
                logger.warning(f"🎤 VocalAgent: Missing vocal tracks: {missing_tracks}")
            
            # Validate voice assignments use available voices
            all_assigned_voices = set()
            for track in tracks:
                voice_id = track.get('voiceId')
                if voice_id:
                    all_assigned_voices.add(voice_id)
                for clip in track.get('clips', []):
                    for voice in clip.get('voices', []):
                        all_assigned_voices.add(voice.get('voice_id'))
            
            invalid_voices = all_assigned_voices - set(state.available_voices.keys())
            if invalid_voices:
                logger.warning(f"🎤 VocalAgent: Invalid voice assignments: {invalid_voices}")
            
            # Ensure track and clip IDs are unique
            for i, track in enumerate(tracks):
                if not track.get('id'):
                    track['id'] = f"track-vocal-{i+1}"
                for j, clip in enumerate(track.get('clips', [])):
                    if not clip.get('id'):
                        clip['id'] = f"clip-{track['id']}-{j+1}"
                    clip['trackId'] = track['id']
            
            state.vocal_assignments = {
                "tracks": tracks,
                "voice_assignments": voice_assignments,
                "melody_philosophy": result.get("melody_philosophy", ""),
                "harmonic_structure": result.get("harmonic_structure", ""),
                "vocal_production_notes": result.get("vocal_production_notes", ""),
                "total_tracks": len(tracks),
                "is_generated": True
            }
            
            logger.info(f"🎤 VocalAgent: Created {len(tracks)} vocal tracks with {sum(len(t.get('clips', [])) for t in tracks)} clips")
            
        except Exception as e:
            safe_log_error(f"Vocal agent error: {e}")
            state.errors.append(f"Vocal: {str(e)}")
            
            # Create intelligent default vocal assignments
            default_tracks = self._create_default_vocal_tracks(
                planned_vocal_tracks, lyrics_sections, structure, state.available_voices
            )
            
            state.vocal_assignments = {
                "tracks": default_tracks,
                "voice_assignments": {"lead": "soprano01"},
                "melody_philosophy": "Using default vocal assignments due to generation error", 
                "reasoning": "Fallback vocal arrangement",
                "error": str(e)
            }
        
        return state
    
    def _create_default_vocal_tracks(self, planned_tracks: List[Dict], lyrics_sections: Dict, 
                                   structure: Dict, available_voices: Dict) -> List[Dict]:
        """Create basic default vocal tracks when generation fails."""
        tracks = []
        
        if not planned_tracks:
            # Create a basic lead vocal track
            planned_tracks = [{
                "name": "Lead Vocals",
                "instrument": "vocals",
                "category": "vocal",
                "voice_id": "soprano01",
                "sections": list(lyrics_sections.keys())
            }]
        
        for i, planned_track in enumerate(planned_tracks):
            track_id = f"track-vocal-{i+1}"
            voice_id = planned_track.get('voice_id', 'soprano01')
            
            # Ensure voice_id is available
            if voice_id not in available_voices:
                voice_id = list(available_voices.keys())[0] if available_voices else 'soprano01'
            
            clips = []
            sections_to_sing = planned_track.get('sections', list(lyrics_sections.keys()))
            
            for section_name in sections_to_sing:
                if section_name in lyrics_sections and section_name in structure:
                    section_info = structure[section_name]
                    section_lyrics = lyrics_sections[section_name]
                    
                    clip = {
                        "id": f"clip-{track_id}-{section_name}",
                        "trackId": track_id,
                        "startTime": section_info.get('start_time', 0),
                        "duration": section_info.get('duration', 8),
                        "type": "lyrics",
                        "instrument": "vocals",
                        "voiceId": voice_id,
                        "volume": 0.8,
                        "pan": 0.0,
                        "effects": {"reverb": 0.1, "delay": 0.05, "distortion": 0},
                        "voices": [{
                            "voice_id": voice_id,
                            "lyrics": [{
                                "text": " ".join(str(lyric) for lyric in section_lyrics) if isinstance(section_lyrics, list) else str(section_lyrics),
                                "notes": ["C4", "D4", "E4", "F4"],  # Simple default melody
                                "start": 0.0,
                                "durations": [2.0, 2.0, 2.0, 2.0],
                                "velocities": [80, 80, 80, 80]
                            }]
                        }]
                    }
                    clips.append(clip)
            
            track = {
                "id": track_id,
                "name": planned_track.get('name', f"Vocal Track {i+1}"),
                "instrument": "vocals",
                "category": "vocal", 
                "voiceId": voice_id,
                "volume": 0.8,
                "pan": 0.0,
                "muted": False,
                "solo": False,
                "clips": clips
            }
            tracks.append(track)
        
        return tracks

    async def _instrument_agent(self, state: SongState) -> SongState:
        """
        InstrumentAgent: Creates instrumental tracks and clips
        - Selects instruments/samples from available_instruments
        - Creates melodic/harmonic/percussive clip content with proper timing
        - Handles chord progressions, basslines, drum patterns, and leads
        """
        state.current_agent = "instrument"
        
        # Progress callback for instrument agent
        if self.progress_callback:
            try:
                await self._safe_progress_callback("Agent 5/9: Creating instrumental tracks (drums, bass, leads)", 55, "instrument")
            except Exception as e:
                print(f"Progress callback error: {e}")
        
        # Get instrumental tracks from arrangement plan
        planned_instrument_tracks = [t for t in state.arrangement.get('planned_tracks', []) 
                                   if t.get('category') in ['keyboards', 'strings', 'percussion', 'synth', 'woodwinds', 'brass', 'other']
                                   and t.get('instrument') != 'vocals' 
                                   and t.get('category') != 'vocal']
        
        structure = state.arrangement.get('structure', {})
        key = state.global_params.get('key', 'C major')
        tempo = state.global_params.get('tempo', 120)
        time_signature = state.global_params.get('timeSignature', '4/4')
        
        # Store musical context for fallback generation
        self._current_key = key
        self._current_style_tags = state.request.style_tags
        
        prompt = f"""You are a professional instrumental arranger and composer. Create detailed instrumental tracks with musical content.

Song Parameters:
- Key: {key}
- Tempo: {tempo} BPM
- Time Signature: {time_signature}
- Style: {self._format_style_tags(state.request.style_tags)} {state.request.custom_style}
- Song Idea: {state.request.song_idea}
- Track Type: {'INSTRUMENTAL ONLY - No Vocals' if state.request.is_instrumental else 'Mixed - Includes Vocals'}

Available Instruments by Category:
{self.music_tools.format_instruments_for_prompt(state.available_instruments)}

Available Default Samples:
{self.music_tools.format_samples_for_prompt(state.available_samples)}

🎵 PRIORITY: Available User-Uploaded Samples 🎵
{self.music_tools.format_samples_for_prompt(state.available_user_samples) if state.available_user_samples else "No user samples uploaded yet"}

{f"📊 Sample Library Statistics: {state.sample_metadata.get('total_count', 0)} total samples ({state.sample_metadata.get('user_count', 0)} user-uploaded, {state.sample_metadata.get('combined_count', 0)} default)" if state.sample_metadata else ""}

SAMPLE SELECTION GUIDELINES:
- 🌟 HIGHEST PRIORITY: Use user-uploaded samples whenever possible - these are custom content the user specifically added
- For user-uploaded samples with BPM metadata, prefer samples that match or complement the song tempo ({tempo} BPM)
- For samples with key information, choose samples that fit the song key ({key}) or related keys
- Consider sample tags and categories to match the song style and mood
- User samples should be integrated creatively into the arrangement - they're not just backing tracks
- When using user samples, note their metadata (BPM, key, duration) in your reasoning
- Fall back to default samples only when user samples aren't suitable for the specific instrument role
- Use sample tags to find appropriate sounds for the intended style: {self._format_style_tags(state.request.style_tags)}
- Consider sample duration when creating clips - shorter samples for percussion hits, longer samples for melodic loops
- Mix default instrument samples with user-uploaded samples for variety and personalized sound
{'- INSTRUMENTAL FOCUS: Since this is an instrumental track, create rich, layered arrangements with prominent lead melodies, complex harmonies, and dynamic instrumental sections that compensate for the absence of vocals' if state.request.is_instrumental else '- VOCAL SUPPORT: Create arrangements that support and complement the vocal parts without overwhelming them'}

Song Structure (with timing in seconds):
{json.dumps(structure, indent=2)}

Planned Instrumental Tracks from Arrangement:
{json.dumps(planned_instrument_tracks, indent=2)}

Create complete instrumental tracks with musical content. You MUST use ONLY instruments from the available_instruments list and ONLY samples from the available_samples list.

Respond ONLY with a JSON object following these exact structure guidelines:

FOR MELODIC/HARMONIC INSTRUMENTS (piano, guitar, strings, synths):
{{
    "clips": [
        {{
            "id": "clip-piano-intro",
            "trackId": "track-piano",
            "startTime": 0,
            "duration": 8,
            "type": "synth",
            "instrument": "piano",
            "volume": 0.7,
            "pan": 0.0,
            "effects": {{"reverb": 0.1, "delay": 0, "distortion": 0}},
            "notes": ["C4", "E4", "G4", "C5", "F4", "A4", "C5", "G4"]  // Rich chord progression
        }}
    ]
}}

FOR BASS INSTRUMENTS:
{{
    "clips": [
        {{
            "id": "clip-bass-verse",
            "trackId": "track-bass", 
            "startTime": 8,
            "duration": 16,
            "type": "synth",
            "instrument": "bass",
            "volume": 0.8,
            "pan": 0.0,
            "effects": {{"reverb": 0.05, "delay": 0, "distortion": 0.1}},
            "notes": ["C2", "G2", "F2", "G2", "C2", "E2", "F2", "G2"]  // Low octave bass line
        }}
    ]
}}

FOR PERCUSSION/DRUMS:
{{
    "clips": [
        {{
            "id": "clip-drums-verse",
            "trackId": "track-drums",
            "startTime": 8,
            "duration": 16,
            "type": "synth",  
            "instrument": "drums",
            "volume": 0.6,
            "pan": 0.0,
            "effects": {{"reverb": 0.2, "delay": 0, "distortion": 0}},
            "notes": ["C4", "C4", "E4", "C4", "C4", "E4", "C4", "E4"]  // Kick-Snare pattern
        }}
    ]
}}

FOR BASS INSTRUMENTS:
{{
    "clips": [
        {{
            "id": "clip-bass-verse",
            "trackId": "track-bass",
            "startTime": 8,
            "duration": 16,
            "type": "synth",
            "instrument": "bass",
            "volume": 0.8,
            "pan": 0.0,
            "effects": {{"reverb": 0.05, "delay": 0, "distortion": 0}},
            "notes": ["C2", "A1", "F2", "G2"]
        }}
    ]
}}

Complete JSON Response:
{{
    "tracks": [
        {{
            "id": "track-piano",
            "name": "Piano",
            "instrument": "piano",
            "volume": 0.7,
            "pan": 0.0,
            "muted": false,
            "solo": false,
            "clips": [/* Use appropriate clip structure from examples above */]
        }},
        {{
            "id": "track-bass",
            "name": "Bass",
            "instrument": "bass",
            "volume": 0.8,
            "pan": 0.0,
            "muted": false,
            "solo": false,
            "clips": [/* Use appropriate clip structure from examples above */]
        }}
    ],
    "instrumental_philosophy": "Explanation of instrumental choices and arrangement approach",
    "harmonic_analysis": "Description of chord progressions and harmonic movement",
    "rhythmic_structure": "Explanation of how different instruments create the groove",
    "production_notes": "Guidance for mixing, effects, and overall sound"
}}

Critical Guidelines:
- Create clips for EVERY section where each instrument should play (based on planned tracks)
- Use ONLY instruments from the available_instruments list - NO other instruments allowed
- For percussion: use type="synth" with notes array for rhythmic patterns (NOT samples)
- For melodic instruments: use type="synth" with notes array directly in clip (NO musical_content wrapper)
- Calculate accurate timing: startTime and duration based on structure timing in seconds
- CRITICAL SCHEMA COMPLIANCE: Follow the exact clip schema - put notes array directly in clip object, NOT inside musical_content
- CORRECT clip structure: {{"id": "", "trackId": "", "startTime": 0, "duration": 4, "type": "synth", "instrument": "", "notes": ["C4", "E4", "G4", "C5"], "volume": 1.0, "effects": {{}}}}
- WRONG format (DO NOT USE): {{"musical_content": {{"notes": [...]}}, ...}} - This is invalid and will cause errors

MUSICAL PATTERN GUIDELINES:
- BASS INSTRUMENTS: Use octave 2-3 (C2, D2, E2, F2, G2, A2, B2) for proper low-end foundation
- PIANO/KEYBOARDS: Use chord progressions with octaves 4-5 (C4, E4, G4, C5, F4, A4, etc.)
- DRUMS/PERCUSSION: Use rhythmic patterns with kick (C4) and snare (E4) emphasis
- STRINGS: Use harmonic content in octaves 4-5 for melodic instruments, 2-3 for bass
- WOODWINDS/BRASS: Use melodic lines in octaves 5-6 for bright, prominent melodies
- CREATE VARIETY: Use at least 4-8 different notes per clip, avoid simple 2-note patterns
- INSTRUMENT HARMONY: Different instruments should complement each other, not play identical patterns
- RHYTHM VARIATION: Create interesting rhythmic interplay between instruments

AVOID SIMPLE PATTERNS:
- DO NOT use only ["C4", "G4"] - this is too basic
- DO NOT have all instruments play the same notes
- DO NOT ignore instrument ranges (bass should be low, melody should be higher)

- Match musical content to song style: {self._format_style_tags(state.request.style_tags)}
- Use appropriate effects for each instrument and style
- Ensure all instruments work together harmonically in key: {key}
- Consider instrument ranges and capabilities
- Include both chordal and single-note content as appropriate
- Plan dynamics: verses lighter, choruses fuller
- Ensure track and clip IDs are unique
- Set appropriate volume levels and pan positions for instrument separation
- Match tempo ({tempo} BPM) with appropriate note durations and patterns
"""
        
        try:
            response = await self._call_llm_safely(prompt)
            
            # Handle empty or whitespace-only responses
            if not response or not response.strip():
                raise ValueError("LLM returned empty response for instrumental arrangement")
            
            # Clean response and validate JSON
            cleaned_response = response.strip()
            if not cleaned_response.startswith('{') or not cleaned_response.endswith('}'):
                # Try to extract JSON from response if it contains other text
                import re
                json_match = re.search(r'\{.*\}', cleaned_response, re.DOTALL)
                if json_match:
                    cleaned_response = json_match.group(0)
                else:
                    raise ValueError(f"No valid JSON found in instrument agent response: {cleaned_response[:200]}...")
            
            result = json.loads(cleaned_response)
            
            tracks = result.get("tracks", [])
            
            # Validate instrument assignments use available instruments
            used_instruments = set()
            for track in tracks:
                instrument = track.get('instrument')
                if instrument:
                    used_instruments.add(instrument)
                    
            # Check against available instruments
            all_available = set()
            for category, instruments in state.available_instruments.items():
                all_available.update(instruments)
                
            invalid_instruments = used_instruments - all_available
            if invalid_instruments:
                logger.warning(f"🎹 InstrumentAgent: Invalid instruments used: {invalid_instruments}")
            
            # Ensure all planned instrumental tracks are created
            planned_instruments = [t.get('instrument') for t in planned_instrument_tracks]
            created_instruments = [t.get('instrument') for t in tracks]
            missing_instruments = [inst for inst in planned_instruments if inst not in created_instruments]
            
            if missing_instruments:
                logger.warning(f"🎹 InstrumentAgent: Missing planned instruments: {missing_instruments}")
            
            # Ensure track and clip IDs are unique and fix schema compliance
            for i, track in enumerate(tracks):
                if not track.get('id'):
                    track['id'] = f"track-instrument-{i+1}"
                for j, clip in enumerate(track.get('clips', [])):
                    if not clip.get('id'):
                        clip['id'] = f"clip-{track['id']}-{j+1}"
                    clip['trackId'] = track['id']
                    
                    # Fix schema compliance: move notes from musical_content to clip level
                    if 'musical_content' in clip:
                        musical_content = clip.pop('musical_content')
                        # Move notes to clip level if they exist in musical_content
                        if 'notes' in musical_content and 'notes' not in clip:
                            # Handle both simple notes array and complex note objects
                            if isinstance(musical_content['notes'], list) and musical_content['notes']:
                                # If notes are objects with 'note' property, extract just the note names
                                if isinstance(musical_content['notes'][0], dict) and 'note' in musical_content['notes'][0]:
                                    clip['notes'] = [note_obj['note'] for note_obj in musical_content['notes']]
                                else:
                                    # If notes are already simple strings, use as-is
                                    clip['notes'] = musical_content['notes']
                            else:
                                # Fallback to simple default notes
                                clip['notes'] = generate_intelligent_default_notes(clip.get('instrument', 'piano'), state.song_key or 'C', 'pop')
                        # Remove other musical_content properties as they're not part of the schema
                        logger.info(f"🔧 Fixed clip schema compliance for {clip['id']} - moved notes from musical_content to clip level")
                    
                    # Ensure all clips have required fields for schema compliance
                    if 'notes' not in clip and clip.get('type') == 'synth':
                        clip['notes'] = generate_intelligent_default_notes(clip.get('instrument', 'piano'), state.song_key or 'C', 'pop')  # Intelligent default notes for synth clips
                        logger.debug(f"🔧 Added default notes to synth clip {clip['id']}")
                    
                    # Remove any remaining non-schema fields
                    non_schema_fields = ['category', 'role', 'pattern']
                    for field in non_schema_fields:
                        if field in clip:
                            clip.pop(field)
                            logger.debug(f"🔧 Removed non-schema field '{field}' from clip {clip['id']}")
            
            state.instrumental_content = {
                "tracks": tracks,
                "instrumental_philosophy": result.get("instrumental_philosophy", ""),
                "harmonic_analysis": result.get("harmonic_analysis", ""),
                "rhythmic_structure": result.get("rhythmic_structure", ""),
                "production_notes": result.get("production_notes", ""),
                "total_tracks": len(tracks),
                "is_generated": True
            }
            
            logger.info(f"🎹 InstrumentAgent: Created {len(tracks)} instrumental tracks with {sum(len(t.get('clips', [])) for t in tracks)} clips")
            
        except Exception as e:
            safe_log_error(f"Instrument agent error: {e}")
            state.errors.append(f"Instrument: {str(e)}")
            
            # Create intelligent default instrumental tracks
            default_tracks = self._create_default_instrument_tracks(
                planned_instrument_tracks, structure, state.available_instruments
            )
            
            state.instrumental_content = {
                "tracks": default_tracks,
                "instrumental_philosophy": "Using default instrumental arrangement due to generation error",
                "reasoning": "Fallback instrumental arrangement", 
                "error": str(e)
            }
        
        return state
    
    def _create_default_instrument_tracks(self, planned_tracks: List[Dict], structure: Dict, 
                                        available_instruments: Dict) -> List[Dict]:
        """Create basic default instrumental tracks when generation fails."""
        tracks = []
        
        if not planned_tracks:
            # Create basic default tracks if none planned
            planned_tracks = [
                {"name": "Piano", "instrument": "piano", "category": "keyboards"},
                {"name": "Bass", "instrument": "bass", "category": "strings"}
            ]
        
        # Extract musical context from state
        key = getattr(self, '_current_key', 'C major')
        style_tags = getattr(self, '_current_style_tags', ['default'])
        
        for i, planned_track in enumerate(planned_tracks):
            track_id = f"track-instrument-{i+1}"
            instrument = planned_track.get('instrument', 'piano')
            category = planned_track.get('category', 'keyboards')
            
            # Normalize instrument name and fix category
            normalized_instrument = self.music_tools.normalize_instrument_name(instrument, category)
            corrected_category = self.music_tools.validate_instrument_category(normalized_instrument, category)
            
            # Ensure instrument is available
            if corrected_category in available_instruments and normalized_instrument not in available_instruments[corrected_category]:
                if available_instruments[corrected_category]:
                    normalized_instrument = available_instruments[corrected_category][0]  # Use first available in category
            
            clips = []
            sections_to_play = planned_track.get('sections', list(structure.keys()))
            
            for section_name in sections_to_play:
                if section_name in structure:
                    section_info = structure[section_name]
                    section_duration = section_info.get('duration', 8)
                    
                    # Generate intelligent notes based on instrument and musical context
                    intelligent_notes = self.music_tools.generate_intelligent_notes(
                        instrument_name=normalized_instrument,
                        category=corrected_category,
                        key=key,
                        style_tags=style_tags,
                        duration_beats=max(4, section_duration // 2)  # Convert seconds to approximate beats
                    )
                    
                    clip = {
                        "id": f"clip-{track_id}-{section_name}",
                        "trackId": track_id,
                        "startTime": section_info.get('start_time', 0),
                        "duration": section_duration,
                        "type": "synth",  # Use "synth" for compatibility
                        "instrument": normalized_instrument,  # Use normalized name
                        "volume": 0.7,
                        "pan": 0.0,
                        "effects": {"reverb": 0.1, "delay": 0, "distortion": 0},
                        "notes": intelligent_notes
                    }
                    clips.append(clip)
            
            track = {
                "id": track_id,
                "name": planned_track.get('name', f"{normalized_instrument.replace('_', ' ').title()} Track"),
                "instrument": normalized_instrument,  # Use normalized name
                "category": corrected_category,
                "volume": 0.7,
                "pan": 0.0,
                "muted": False,
                "solo": False,
                "clips": clips
            }
            tracks.append(track)
        
        return tracks

    async def _effects_agent(self, state: SongState) -> SongState:
        """
        EffectsAgent: Adds audio effects to tracks and clips
        - reverb, delay, distortion guided by style
        """
        state.current_agent = "effects"
        
        # Progress callback for effects agent
        if self.progress_callback:
            try:
                await self._safe_progress_callback("Agent 6/9: Applying audio effects (reverb, delay, EQ)", 66, "effects")
            except Exception as e:
                print(f"Progress callback error: {e}")
        
        # Combine all tracks from vocal and instrumental agents
        all_tracks = []
        all_tracks.extend(state.vocal_assignments.get("tracks", []))
        all_tracks.extend(state.instrumental_content.get("tracks", []))
        
        prompt = f"""You are an audio engineer. Add appropriate effects to the tracks based on style and instrument type.

Song Style: {self._format_style_tags(state.request.style_tags)} {state.request.custom_style}
Track Type: {'INSTRUMENTAL ONLY - No Vocals' if state.request.is_instrumental else 'Mixed - Includes Vocals'}
Tempo: {state.global_params.get('tempo')} BPM

Current Tracks:
{json.dumps(all_tracks, indent=2)}

Add effects to enhance the mix. Respond ONLY with a JSON object:
{{
    "track_effects": {{
        "track-id-1": {{
            "reverb": 0.3,
            "delay": 0.1,
            "distortion": 0.0
        }},
        "track-id-2": {{
            "reverb": 0.1,
            "delay": 0.0,
            "distortion": 0.2
        }}
    }},
    "clip_effects": {{
        "clip-id-1": {{
            "reverb": 0.2,
            "delay": 0.0,
            "distortion": 0.0
        }}
    }},
    "mixing_notes": "Brief explanation of effect choices"
}}

Effect Guidelines (values 0.0-1.0):
- Reverb: Vocals (0.2-0.4), Drums (0.1-0.3), Lead instruments (0.1-0.3)
- Delay: Vocals/Leads (0.0-0.2), Rhythmic instruments (0.0-0.1)
- Distortion: Rock guitars (0.2-0.6), Electronic synths (0.1-0.4), Clean instruments (0.0)
- Style-specific: Rock (more distortion), Ambient (more reverb), Electronic (more delay)
"""
        
        try:
            response = await self._call_llm_safely(prompt)
            
            # Handle empty or whitespace-only responses
            if not response or not response.strip():
                raise ValueError("LLM returned empty response for effects configuration")
            
            # Clean response and validate JSON
            cleaned_response = response.strip()
            if not cleaned_response.startswith('{') or not cleaned_response.endswith('}'):
                # Try to extract JSON from response if it contains other text
                import re
                json_match = re.search(r'\{.*\}', cleaned_response, re.DOTALL)
                if json_match:
                    cleaned_response = json_match.group(0)
                else:
                    raise ValueError(f"No valid JSON found in effects agent response: {cleaned_response[:200]}...")
            
            result = json.loads(cleaned_response)
            
            state.effects_config = {
                "track_effects": result.get("track_effects", {}),
                "clip_effects": result.get("clip_effects", {}),
                "mixing_notes": result.get("mixing_notes", ""),
                "is_generated": True
            }
            
        except Exception as e:
            safe_log_error(f"Effects agent error: {e}")
            state.errors.append(f"Effects: {str(e)}")
            state.effects_config = {"track_effects": {}, "clip_effects": {}, "error": str(e)}
        
        return state
    
    async def _review_agent(self, state: SongState) -> SongState:
        """
        ReviewAgent: Evaluates the assembled song_state
        - Schema completeness, musical coherence, sample/voice/instrument validity
        """
        state.current_agent = "review"
        
        # Progress callback for review agent
        if self.progress_callback:
            try:
                await self._safe_progress_callback("Agent 7/9: Reviewing composition and structure", 77, "review")
            except Exception as e:
                print(f"Progress callback error: {e}")
        
        # Assemble current song structure for review
        current_song = self._assemble_song_structure(state)
        
        prompt = f"""You are a music production quality reviewer. Evaluate this generated song structure for completeness and quality.

Generated Song Structure:
{json.dumps(current_song, indent=2)}

Original Request:
- Idea: {state.request.song_idea}
- Style: {self._format_style_tags(state.request.style_tags)} {state.request.custom_style}
- Instrumental: {state.request.is_instrumental}

Evaluate and respond ONLY with a JSON object:
{{
    "is_ready": true,
    "review_notes": [
        "Positive aspects and what works well",
        "Any minor issues (these won't trigger revision)"
    ],
    "schema_issues": [
        "Only list CRITICAL schema problems that prevent song playback"
    ],
    "musical_issues": [
        "Only list CRITICAL musical problems that make the song unlistenable"
    ],
    "recommendation": "continue",
    "revision_priority": "low"
}}

IMPORTANT: Only recommend "revise" for CRITICAL issues that would prevent the song from playing or being completely unusable. Be generous with "continue" to avoid infinite revision loops.

Check for:
1. CRITICAL schema completeness (only flag if required fields are completely missing)
2. CRITICAL musical coherence (only flag if completely unmusical)
3. Track/clip relationships (only flag if IDs are broken)
4. Basic playability

Be constructive but focus on what works rather than minor improvements. Most songs should receive "continue" recommendation.
"""
        
        try:
            response = await self._call_llm_safely(prompt)
            
            # Handle empty or whitespace-only responses
            if not response or not response.strip():
                raise ValueError("LLM returned empty response for review analysis")
            
            # Clean response and validate JSON
            cleaned_response = response.strip()
            if not cleaned_response.startswith('{') or not cleaned_response.endswith('}'):
                # Try to extract JSON from response if it contains other text
                import re
                json_match = re.search(r'\{.*\}', cleaned_response, re.DOTALL)
                if json_match:
                    cleaned_response = json_match.group(0)
                else:
                    raise ValueError(f"No valid JSON found in review agent response: {cleaned_response[:200]}...")
            
            result = json.loads(cleaned_response)
            
            state.review_notes = result.get("review_notes", [])
            state.is_ready_for_export = result.get("is_ready", False)
            
            # Add specific issue tracking
            schema_issues = result.get("schema_issues", [])
            musical_issues = result.get("musical_issues", [])
            
            if schema_issues:
                state.errors.extend([f"Schema: {issue}" for issue in schema_issues])
            if musical_issues:
                state.errors.extend([f"Musical: {issue}" for issue in musical_issues])
            
            # Set recommendation for workflow control
            state.arrangement["review_recommendation"] = result.get("recommendation", "continue")
            
        except Exception as e:
            safe_log_error(f"Review agent error: {e}")
            state.errors.append(f"Review: {str(e)}")
            state.review_notes = [f"Review failed: {str(e)}"]
            state.is_ready_for_export = False
        
        return state
    
    async def _design_agent(self, state: SongState) -> SongState:
        """
        DesignAgent: Creates album art description/concept
        Note: Always uses OpenAI as it's the only provider with image generation capabilities
        """
        state.current_agent = "design"
        
        # Progress callback for design agent
        if self.progress_callback:
            try:
                await self._safe_progress_callback("Agent 8/9: Creating album art and visual concept", 88, "design")
            except Exception as e:
                print(f"Progress callback error: {e}")
        
        prompt = f"""You are a creative visual artist and album cover designer. Create an album art concept for this song.

Song Information:
- Title: {state.song_metadata.get('name', 'Untitled')}
- Style: {self._format_style_tags(state.request.style_tags)} {state.request.custom_style}
- Mood: {state.lyrics.get('mood', 'Unknown')}
- Theme: {state.lyrics.get('theme', 'Unknown')}
- Key: {state.global_params.get('key')} (consider emotional implications)

Create album art concept. Respond ONLY with a JSON object:
{{
    "concept": "Detailed visual description of the album cover",
    "color_palette": ["#FF0000", "#00FF00", "#0000FF"],
    "style": "photographic|illustrated|abstract|minimalist|vintage",
    "mood": "energetic|calm|dark|bright|mysterious",
    "elements": ["element1", "element2", "element3"],
    "typography": "bold|elegant|grunge|modern|classic",
    "composition": "Description of layout and focal points"
}}

Guidelines:
- Match the musical style and mood
- Consider the target audience
- Create something visually striking and memorable
- Think about how it would look as both large and thumbnail sizes
- Include specific visual elements that relate to the lyrics or style
"""
        
        try:
            # ALWAYS force OpenAI for album cover generation - NEVER use Claude or other providers
            logger.info("🎨 Design Agent: Forcing OpenAI model for image generation (ignoring user preference)")
            
            # Ensure we have OpenAI API key
            openai_key = self.openai_api_key or os.getenv('OPENAI_API_KEY')
            if not openai_key:
                logger.warning("❌ No OpenAI API key available for album art generation - skipping")
                state.album_art = {
                    "concept": "Album art generation skipped - OpenAI API key not available",
                    "color_palette": ["#333333", "#666666", "#999999"],
                    "style": "minimalist",
                    "mood": "neutral",
                    "elements": [],
                    "typography": "modern",
                    "composition": "Simple text-based design",
                    "is_generated": False,
                    "provider": "none",
                    "error": "No OpenAI API key"
                }
                return state
            
            # IMPORTANT: Create dedicated OpenAI instance - do NOT use self.llm or any other LLM
            # This ensures we never accidentally use Claude/Anthropic for image generation
            logger.info("🔧 Creating dedicated OpenAI ChatGPT instance for design agent")
            
            design_llm = ChatOpenAI(
                model="gpt-4o",  # Use a reliable text model for concept generation
                api_key=openai_key,
                temperature=0.7,
                max_tokens=1500
            )
            
            # Verify it's actually OpenAI
            llm_class_name = design_llm.__class__.__name__
            llm_module = design_llm.__class__.__module__
            logger.info(f"✅ Design Agent LLM: {llm_class_name} from {llm_module}")
            
            # Double-check we're not using Anthropic
            if 'anthropic' in llm_module.lower() or 'claude' in llm_class_name.lower():
                logger.error("❌ CRITICAL: Design agent incorrectly configured with Anthropic - forcing fallback")
                state.album_art = {
                    "concept": "Album art generation failed - incorrect model configuration",
                    "color_palette": ["#333333", "#666666", "#999999"],
                    "style": "minimalist",
                    "mood": "neutral",
                    "elements": [],
                    "typography": "modern",
                    "composition": "Simple text-based design",
                    "is_generated": False,
                    "provider": "error",
                    "error": "Anthropic model incorrectly used for design agent"
                }
                return state
            
            logger.info("🔍 Design Agent: Using OpenAI ChatGPT-4o for album cover concept generation")
            
            messages = [SystemMessage(content=prompt)]
            
            # Call the LLM directly (not through _call_llm_safely to avoid user preference override)
            if hasattr(design_llm, 'ainvoke'):
                response = await design_llm.ainvoke(messages)
            else:
                response = await asyncio.get_event_loop().run_in_executor(
                    None, design_llm.invoke, messages
                )
            
            result = self._safe_json_parse(response.content.strip(), {
                "concept": "Default album art concept",
                "color_palette": ["#333333", "#666666", "#999999"],
                "style": "minimalist",
                "mood": "neutral",
                "elements": [],
                "typography": "modern",
                "composition": "Simple design"
            })
            
            # Generate actual album cover image using the concept
            image_url = None
            image_generation_error = None
            
            try:
                logger.info("Generating album cover image using DALL-E-3...")
                # Create a detailed prompt for image generation based on the concept
                image_prompt = self._create_image_prompt_from_concept(result, state)
                
                # Generate the image using OpenAI DALL-E-3
                image_url = await self._generate_album_cover_image(image_prompt)
                logger.info(f"Album cover image generated successfully: {image_url}")
                
            except Exception as img_error:
                logger.error(f"Album cover image generation failed: {img_error}")
                image_generation_error = str(img_error)
            
            state.album_art = {
                "concept": result.get("concept", ""),
                "color_palette": result.get("color_palette", []),
                "style": result.get("style", ""),
                "mood": result.get("mood", ""),
                "elements": result.get("elements", []),
                "typography": result.get("typography", ""),
                "composition": result.get("composition", ""),
                "image_url": image_url,  # Add the generated image URL
                "image_generation_error": image_generation_error,
                "is_generated": True,
                "provider": "openai"  # Always use OpenAI for album covers
            }
            
            if image_url:
                logger.info(f"Album art with image generated successfully: {result.get('concept', '')[:50]}...")
            else:
                logger.warning(f"Album art concept generated but image failed: {result.get('concept', '')[:50]}...")
            
        except Exception as e:
            logger.error(f"Design agent error: {e}")
            safe_log_error(f"Design agent error: {e}")
            state.errors.append(f"Design: {str(e)}")
            state.album_art = {
                "concept": "Album art generation failed", 
                "error": str(e),
                "is_generated": False,
                "provider": "error"
            }
        
        return state
    
    def _create_image_prompt_from_concept(self, concept_data: Dict[str, Any], state: SongState) -> str:
        """Create a detailed DALL-E prompt from the album art concept"""
        song_name = state.song_metadata.get('name', 'Untitled')
        style_tags = self._format_style_tags(state.request.style_tags)
        
        # Base prompt with the concept
        base_concept = concept_data.get('concept', 'Modern album cover design')
        
        # Add style and mood information
        style = concept_data.get('style', 'modern')
        mood = concept_data.get('mood', 'neutral')
        elements = ', '.join([str(el) if not isinstance(el, str) else el for el in concept_data.get('elements', [])])
        
        # Create a comprehensive prompt for DALL-E-3
        prompt = f"""Professional album cover for "{song_name}". {base_concept}. 
        
Style: {style} {style_tags} music album cover. 
Mood: {mood}. 
Visual elements: {elements}.
        
High quality, professional music album artwork, suitable for digital music platforms like Spotify, Apple Music. 
No text or typography overlays - just the visual artwork. 
Artistic, eye-catching, and representative of the music genre. 
Perfect for both large display and thumbnail sizes."""
        
        # Clean up the prompt
        return ' '.join(prompt.split())
    
    async def _generate_album_cover_image(self, prompt: str) -> str:
        """Generate album cover image using OpenAI DALL-E-3"""
        try:
            # Import here to avoid circular imports
            from .ai_service import AIService
            
            # Initialize AI service with forced OpenAI configuration
            ai_service = AIService()
            
            if not ai_service.openai_client:
                raise Exception("OpenAI client not available for image generation")
            
            logger.info(f"🖼️ DALL-E-3: Generating album cover with prompt: {prompt[:100]}...")
            
            # Generate image using DALL-E-3 (always uses OpenAI)
            response = ai_service.openai_client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size="1024x1024",
                quality="standard",
                style="vivid",
                n=1
            )
            
            image_url = response.data[0].url
            logger.info(f"✅ Album cover image generated successfully: {image_url}")
            
            return image_url
            
        except Exception as e:
            logger.error(f"❌ Image generation failed: {e}")
            raise Exception(f"Album cover image generation failed: {str(e)}")
    
    async def _qa_agent(self, state: SongState) -> SongState:
        """
        QAAgent: Final validation and structure assembly
        - Fixes missing fields, applies corrections, validates against schema
        """
        state.current_agent = "qa"
        
        # Progress callback for QA agent
        if self.progress_callback:
            try:
                base_progress = 99
                adjusted_progress = self._calculate_restart_adjusted_progress(base_progress, state)
                restart_message = f" (restart {state.qa_restart_count})" if state.qa_restart_count > 0 else ""
                await self._safe_progress_callback(f"Agent 9/9: Final quality assurance and validation{restart_message}", adjusted_progress, "qa")
            except Exception as e:
                print(f"Progress callback error: {e}")
        
        # Assemble the final song structure
        final_song = self._assemble_song_structure(state)
        
        prompt = f"""You are a final quality assurance agent. Review and finalize this song structure.

Current Song Structure:
{json.dumps(final_song, indent=2)}

Fix any remaining issues and ensure schema compliance. Respond ONLY with a JSON object:
{{
    "corrections_made": [
        "Description of any fixes applied"
    ],
    "final_validation": "pass|fail",
    "remaining_issues": [
        "Specific issues that couldn't be automatically fixed - be precise about the problem area"
    ]
}}

When describing remaining_issues, use these keywords to help identify the responsible agent:
- For tempo/key/timing issues: include words like "tempo", "bpm", "key", "time signature", "duration"
- For song structure issues: include words like "structure", "arrangement", "sections", "track count"
- For lyrical content: include words like "lyrics", "lyric", "verse", "chorus", "words"
- For vocal issues: include words like "vocal", "voice", "singing", "harmony"
- For instrumental content: include words like "instrument", "piano", "guitar", "drum", "bass", "notes", "pattern", "melody", "chord"
- For audio effects: include words like "effect", "reverb", "delay", "distortion", "volume", "pan"
- For visual/design: include words like "album", "cover", "art", "image", "visual", "design"

Required Schema Fields:
- id, name, tempo, timeSignature, key, tracks, duration, createdAt, updatedAt
- Each track: id, name, instrument, volume, pan, muted, solo, clips, effects
- Each clip: id, trackId, startTime, duration, type, instrument, volume, effects
- Lyrics clips: additional voices array with voice_id, lyrics array

Validation Checks:
1. All required fields present
2. Valid data types and ranges
3. Unique IDs across tracks and clips
4. Logical timing (no overlapping issues)
5. Valid instrument/voice references
6. Effects values in 0.0-1.0 range
"""
        
        try:
            logger.info("🔍 QA Agent: Calling LLM for validation...")
            response = await self._call_llm_safely(prompt)
            logger.info(f"🔍 QA Agent: LLM response received (length: {len(response)})")
            
            # Handle empty or whitespace-only responses
            if not response or not response.strip():
                raise ValueError("LLM returned empty response for QA validation")
            
            # Clean response and validate JSON
            cleaned_response = response.strip()
            if not cleaned_response.startswith('{') or not cleaned_response.endswith('}'):
                # Try to extract JSON from response if it contains other text
                import re
                json_match = re.search(r'\{.*\}', cleaned_response, re.DOTALL)
                if json_match:
                    cleaned_response = json_match.group(0)
                else:
                    raise ValueError(f"No valid JSON found in QA agent response: {cleaned_response[:200]}...")
            
            # Log the first 500 chars of response for debugging
            logger.info(f"🔍 QA Agent: Response preview: {cleaned_response[:500]}...")
            
            result = json.loads(cleaned_response)
            logger.info(f"🔍 QA Agent: JSON parsed successfully: {result}")
            
            state.qa_corrections = result.get("corrections_made", [])
            
            # Apply any automatic fixes and finalize
            final_song = self._apply_qa_fixes(final_song, state)
            state.final_song_json = final_song
            
            # Final validation
            if result.get("final_validation") == "pass" and not result.get("remaining_issues"):
                state.is_ready_for_export = True
                state.qa_feedback = []  # Clear any previous feedback
                logger.info("✓ QA Agent: Song passed final validation")
            else:
                # Store feedback for restart decision and explicitly mark as NOT ready
                state.is_ready_for_export = False  # Explicitly set to False to trigger restart
                raw_issues = result.get("remaining_issues", [])
                state.qa_feedback = self._ensure_string_list(raw_issues)
                state.errors.extend(state.qa_feedback)
                logger.warning(f"⚠ QA Agent: Song failed validation - {state.qa_feedback}")
                
                # Don't call completion callback yet - let the decision function handle restart
                return state
            
        except Exception as e:
            safe_log_error(f"QA agent error: {e}")
            state.errors.append(f"QA: {str(e)}")
            
            # Try to assemble the current structure for analysis
            state.final_song_json = final_song
            
            # Don't auto-approve if we already have QA feedback indicating issues
            if state.qa_feedback:
                logger.warning(f"QA agent error occurred, but previous QA feedback exists: {state.qa_feedback}")
                # Keep existing feedback and let decision function handle restart
                state.is_ready_for_export = False  # Ensure not ready for export
                return state
            
            # Only auto-approve if we have a valid song structure AND no existing issues
            if (final_song and 
                final_song.get('tracks') and 
                len(final_song.get('tracks', [])) > 0 and 
                not state.errors):  # Check for no accumulated errors
                
                state.is_ready_for_export = True
                state.qa_corrections.append("Auto-approved despite QA LLM error - song structure appears valid")
                logger.info("✓ QA Agent: Auto-approved song despite LLM error (structure valid, no previous issues)")
            else:
                # If we have structural issues or errors, don't auto-approve
                logger.warning("QA agent error occurred with invalid structure or existing errors - not auto-approving")
                # Set generic feedback to trigger restart
                state.is_ready_for_export = False  # Explicitly set to False
                state.qa_feedback = ["structure: QA validation failed due to technical error, needs review"]
                return state
        
        # Only call completion callback if we're actually ready for export
        # Otherwise, the decision function will handle restart
        if state.is_ready_for_export and self.progress_callback:
            try:
                await self._safe_progress_callback("✓ Song generation complete! All agents finished.", 100, "complete")
            except Exception as e:
                print(f"Progress callback error: {e}")
        
        return state

    async def _user_approval_agent(self, state: SongState) -> SongState:
        """
        User Approval Agent: Presents QA feedback to user within progress dialog
        - Shows QA evaluation and current song quality
        - Waits for user decision through progress dialog interface
        """
        state.current_agent = "user_approval"
        
        # Prepare user feedback summary
        final_song = self._assemble_song_structure(state)
        
        # Create comprehensive feedback for user decision within progress dialog
        qa_summary = {
            "qa_feedback": state.qa_feedback,
            "qa_corrections": getattr(state, 'qa_corrections', []),
            "current_quality": "needs_improvement" if state.qa_feedback else "good",
            "restart_count": state.qa_restart_count,
            "max_restarts": state.max_qa_restarts,
            "song_structure": {
                "tracks": len(final_song.get('tracks', [])),
                "duration": final_song.get('duration', 0),
                "tempo": final_song.get('tempo', 0),
                "key": final_song.get('key', 'Unknown')
            },
            "improvement_areas": [],
            "user_decision_required": True
        }
        
        # Analyze potential improvement areas from QA feedback
        if state.qa_feedback:
            feedback_text = " ".join(self._ensure_string_list(state.qa_feedback)).lower()
            improvement_suggestions = []
            
            if any(word in feedback_text for word in ['tempo', 'bpm', 'key', 'timing']):
                improvement_suggestions.append("Musical parameters (tempo, key, timing)")
            if any(word in feedback_text for word in ['structure', 'arrangement', 'sections']):
                improvement_suggestions.append("Song structure and arrangement")
            if any(word in feedback_text for word in ['lyrics', 'lyric', 'words']):
                improvement_suggestions.append("Lyrics and lyrical content")
            if any(word in feedback_text for word in ['vocal', 'voice', 'singing']):
                improvement_suggestions.append("Vocal assignments and melodies")
            if any(word in feedback_text for word in ['instrument', 'notes', 'melody', 'harmony']):
                improvement_suggestions.append("Instrumental content and arrangements")
            if any(word in feedback_text for word in ['effect', 'reverb', 'delay', 'volume']):
                improvement_suggestions.append("Audio effects and mixing")
            if any(word in feedback_text for word in ['album', 'cover', 'art', 'design']):
                improvement_suggestions.append("Album art and visual design")
                
            qa_summary["improvement_areas"] = improvement_suggestions
        
        # Store the feedback for the user interface
        state.user_approval_data = qa_summary
        
        # Send progress update with user decision request integrated in progress dialog
        if self.progress_callback:
            try:
                # Create user-friendly progress message
                if state.qa_feedback:
                    feedback_summary = f"{len(state.qa_feedback)} quality issues detected"
                    quality_level = "needs improvement"
                else:
                    feedback_summary = "Good quality achieved"
                    quality_level = "good"
                
                # Prepare decision message for progress dialog
                decision_message = {
                    "type": "user_decision_required",
                    "title": "Quality Assessment Complete",
                    "summary": f"Song generated with {qa_summary['song_structure']['tracks']} tracks ({feedback_summary})",
                    "quality_status": quality_level,
                    "qa_feedback": state.qa_feedback,
                    "qa_corrections": state.qa_corrections,
                    "improvement_areas": qa_summary["improvement_areas"],
                    "song_info": {
                        "tracks": qa_summary["song_structure"]["tracks"],
                        "duration": f"{qa_summary['song_structure']['duration']} seconds",
                        "tempo": f"{qa_summary['song_structure']['tempo']} BPM",
                        "key": qa_summary["song_structure"]["key"]
                    },
                    "restart_info": {
                        "current_attempt": state.qa_restart_count + 1,
                        "max_attempts": state.max_qa_restarts + 1
                    },
                    "options": [
                        {
                            "id": "accept",
                            "label": "Accept Current Version",
                            "description": "Use the song as-is (fast completion)",
                            "action": "complete"
                        },
                        {
                            "id": "improve", 
                            "label": "Request Improvements",
                            "description": "AI will address the identified quality issues (takes more time)",
                            "action": "restart",
                            "disabled": state.qa_restart_count >= state.max_qa_restarts
                        }
                    ]
                }
                
                await self._safe_progress_callback(
                    message="⏸️ Quality assessment complete - Your decision needed",
                    progress=95,
                    agent="user_approval",
                    decision_data=decision_message,
                    user_interaction_required=True,
                    qa_feedback_summary=qa_summary
                )
            except Exception as e:
                logger.warning(f"Progress callback failed: {e}")
        
        # Log the user approval state
        logger.info(f"🤖 User Approval: Presenting quality feedback in progress dialog")
        logger.info(f"🤖 Quality status: {qa_summary['current_quality']}")
        logger.info(f"🤖 QA feedback items: {len(state.qa_feedback)}")
        if state.qa_feedback:
            logger.info(f"🤖 Issues to address: {state.qa_feedback}")
        
        return state

    def _user_approval_decision(self, state: SongState) -> str:
        """
        User decision point: Check what action the user wants to take
        This function handles the routing based on user choice received through progress dialog
        """
        # Check if user has made a decision (this will be set by external interface via progress system)
        user_decision = getattr(state, 'user_decision', None)
        
        logger.info(f"🤖 User Approval Decision: Starting decision check")
        logger.info(f"🤖 User Approval Decision: user_decision = {user_decision}")
        logger.info(f"🤖 User Approval Decision: qa_feedback count = {len(state.qa_feedback) if state.qa_feedback else 0}")
        logger.info(f"🤖 User Approval Decision: qa_feedback = {state.qa_feedback}")
        logger.info(f"🤖 User Approval Decision: user_approval_data exists = {hasattr(state, 'user_approval_data') and state.user_approval_data is not None}")
        
        if user_decision == 'accept':
            logger.info("🤖 User Decision: User accepted current version")
            logger.info("🤖 User Decision: ROUTING TO: accept")
            state.is_ready_for_export = True
            # Send completion update through progress callback
            if self.progress_callback:
                try:
                    asyncio.create_task(self._safe_progress_callback(
                        "✓ Song accepted by user - Generation complete!", 
                        100, 
                        "complete",
                        user_choice="accept"
                    ))
                except Exception as e:
                    logger.warning(f"Progress callback failed: {e}")
            return "accept"
            
        elif user_decision == 'improve':
            # User wants improvements - use automatic QA decision logic
            logger.info("🤖 User Decision: User requested improvements")
            state.qa_restart_count += 1
            
            # Use existing QA analysis logic to determine best restart point
            feedback_text = " ".join(self._ensure_string_list(state.qa_feedback)).lower() if state.qa_feedback else ""
            
            # Determine which agent to restart based on feedback content
            restart_target = "restart_arrangement"  # Default
            restart_reason = "General improvements requested"
            
            if any(word in feedback_text for word in ['tempo', 'bpm', 'key', 'timing']):
                restart_target = "restart_composer"
                restart_reason = "Musical parameters need adjustment"
            elif any(word in feedback_text for word in ['structure', 'arrangement', 'sections']):
                restart_target = "restart_arrangement"
                restart_reason = "Song structure needs improvement"
            elif any(word in feedback_text for word in ['lyrics', 'words']) and not state.request.is_instrumental:
                restart_target = "restart_lyrics"
                restart_reason = "Lyrics need refinement"
                logger.info(f"🤖 User Decision: QA Analysis suggests lyrics restart for vocal track")
            elif any(word in feedback_text for word in ['lyrics', 'words']) and state.request.is_instrumental:
                # PROTECTION: Never restart lyrics for instrumental tracks
                logger.warning(f"🚨 PROTECTION: QA mentioned lyrics feedback for INSTRUMENTAL track - redirecting to arrangement")
                restart_target = "restart_arrangement"
                restart_reason = "Arrangement needs refinement (lyrics feedback ignored for instrumental track)"
            elif any(word in feedback_text for word in ['vocal', 'voice']) and not state.request.is_instrumental:
                restart_target = "restart_vocal"
                restart_reason = "Vocal arrangements need improvement"
                logger.info(f"🤖 User Decision: QA Analysis suggests vocal restart for vocal track")
            elif any(word in feedback_text for word in ['vocal', 'voice']) and state.request.is_instrumental:
                # PROTECTION: Never restart vocal for instrumental tracks
                logger.warning(f"🚨 PROTECTION: QA mentioned vocal feedback for INSTRUMENTAL track - redirecting to instrument")
                restart_target = "restart_instrument"
                restart_reason = "Instrumental content needs enhancement (vocal feedback ignored for instrumental track)"
            elif any(word in feedback_text for word in ['instrument', 'notes', 'melody']):
                restart_target = "restart_instrument"
                restart_reason = "Instrumental content needs enhancement"
            elif any(word in feedback_text for word in ['effect', 'reverb', 'volume']):
                restart_target = "restart_effects"
                restart_reason = "Audio effects need adjustment"
            elif any(word in feedback_text for word in ['album', 'cover', 'art']):
                restart_target = "restart_design"
                restart_reason = "Album art needs improvement"
            
            # Send restart update through progress callback
            if self.progress_callback:
                try:
                    agent_name = restart_target.replace("restart_", "").title()
                    asyncio.create_task(self._safe_progress_callback(
                        f"🔄 Restarting from {agent_name} agent - {restart_reason}",
                        20 + (state.qa_restart_count * 10),  # Progressive restart indicator
                        restart_target.replace("restart_", ""),
                        user_choice="improve",
                        restart_reason=restart_reason,
                        restart_attempt=state.qa_restart_count
                    ))
                except Exception as e:
                    logger.warning(f"Progress callback failed: {e}")
            
            logger.info(f"🤖 User Decision: Restarting from {restart_target} - {restart_reason}")
            return restart_target
            
        else:
            # No user decision yet - this is expected when first reaching user approval
            logger.info("🤖 User Decision: No user decision provided yet - user approval UI should be displayed")
            logger.info(f"🤖 User Decision: This is the FIRST TIME reaching user approval decision")
            
            # Check if there are issues that need addressing
            if state.qa_feedback and len(state.qa_feedback) > 0:
                logger.info(f"🤖 User Decision: QA feedback exists ({len(state.qa_feedback)} items) - should wait for user choice")
                logger.info(f"🤖 User Decision: QA feedback items: {state.qa_feedback}")
                # Don't auto-accept - instead, this should signal that user input is required
                # The main generation function should detect user_approval_data and pause for user input
                state.user_approval_pending = True
                logger.info("🤖 User Decision: Setting user_approval_pending flag to pause workflow")
                logger.info("🤖 User Decision: ROUTING TO: accept (but with user_approval_pending=True)")
                return "accept"  # This will end the workflow, but main function will detect user_approval_data
            else:
                # No feedback means it's good to go
                logger.info("🤖 User Decision: No issues detected - auto-accepting")
                logger.info("🤖 User Decision: ROUTING TO: accept (auto-accept)")
                state.is_ready_for_export = True
                return "accept"

    def set_user_decision(self, session_id: str, decision: str) -> bool:
        """
        Method to receive user decisions from the frontend through the progress dialog
        This would be called by the API when user makes a choice
        
        Args:
            session_id: The workflow session identifier
            decision: 'accept' or 'improve'
            
        Returns:
            bool: True if decision was set successfully
        """
        # In a complete implementation, this would:
        # 1. Retrieve the workflow state from session storage
        # 2. Set the user_decision field
        # 3. Signal the workflow to continue from user_approval_decision
        
        logger.info(f"🤖 User Decision Received: session={session_id}, decision={decision}")
        
        if decision not in ['accept', 'improve']:
            logger.error(f"🤖 Invalid user decision: {decision}")
            return False
        
        # This is a placeholder - real implementation would update the stored workflow state
        # and resume the LangGraph execution
        logger.info(f"🤖 User Decision Set: {decision} (implementation pending)")
        return True
    
    # ============================================================================
    # WORKFLOW CONTROL AND UTILITY METHODS
    # ============================================================================
    
    def _review_decision(self, state: SongState) -> str:
        """Decide whether to continue or revise based on review results"""
        # Always force continue after max revisions to prevent infinite loops
        if state.revision_count >= state.max_revisions:
            logger.info(f"Forcing continue after {state.revision_count} revisions")
            return "continue"
        
        # Get review recommendation from the review agent result
        review_recommendation = state.arrangement.get("review_recommendation", "continue")
        
        # Be very conservative with revisions to prevent infinite loops
        if review_recommendation == "revise":
            # Only allow revisions if we haven't revised much and have serious issues
            critical_errors = [error for error in state.errors 
                             if any(word in error.lower() for word in ['critical', 'missing required', 'invalid schema'])]
            
            if critical_errors and state.revision_count < 1:  # Max 1 revision
                state.revision_count += 1
                logger.info(f"Allowing revision {state.revision_count} due to critical issues: {critical_errors[:2]}")
                return "revise"
            else:
                logger.info(f"Ignoring revision request - either no critical errors or already revised {state.revision_count} times")
                return "continue"
        
        logger.info("Review decision: continue to design phase")
        return "continue"
    
    async def _qa_decision(self, state: SongState) -> str:
        """
        Analyze QA feedback and decide whether to restart from a specific agent or complete
        Uses priority-based analysis to handle multiple issues effectively
        """
        logger.info(f"🔍 QA Decision: Starting analysis (restart count: {state.qa_restart_count}/{state.max_qa_restarts})")
        logger.info(f"🔍 QA Decision: Ready for export: {state.is_ready_for_export}")
        logger.info(f"🔍 QA Decision: QA feedback count: {len(state.qa_feedback) if state.qa_feedback else 0}")
        logger.info(f"🔍 QA Decision: QA feedback: {state.qa_feedback}")
        
        # Always complete after max QA restarts to prevent infinite loops
        if state.qa_restart_count >= state.max_qa_restarts:
            logger.info(f"🔄 QA Decision: Forcing completion after {state.qa_restart_count} QA restarts (limit: {state.max_qa_restarts})")
            return "complete"
        
        # If there's QA feedback indicating issues, route to user approval
        if state.qa_feedback and len(state.qa_feedback) > 0:
            logger.info(f"🔄 QA Decision: QA feedback detected ({len(state.qa_feedback)} items) - routing to user approval")
            logger.info(f"🔄 QA Decision: Feedback items: {state.qa_feedback}")
            logger.info(f"🔄 QA Decision: ROUTING TO: user_review")
            return "user_review"
        elif state.is_ready_for_export:
            logger.info("🔄 QA Decision: Song validation passed - completing workflow")
            logger.info(f"🔄 QA Decision: ROUTING TO: complete")
            return "complete"
        else:
            # No feedback but not ready for export - something went wrong, complete anyway
            logger.warning("🔄 QA Decision: No QA feedback but not ready for export - completing anyway")
            logger.warning(f"🔄 QA Decision: ROUTING TO: complete (fallback)")
            return "complete"
    
    def _assemble_song_structure(self, state: SongState) -> Dict[str, Any]:
        """Assemble the current song structure from all agent outputs"""
        # Start with basic structure
        song = {
            "id": state.song_metadata.get("id", f"song-{uuid.uuid4()}"),
            "name": state.song_metadata.get("name", "Generated Song"),
            "tempo": state.global_params.get("tempo", 120),
            "timeSignature": state.global_params.get("timeSignature", [4, 4]),
            "key": state.global_params.get("key", "C"),
            "duration": state.global_params.get("duration", 32),
            "createdAt": state.song_metadata.get("createdAt", datetime.now().isoformat()),
            "updatedAt": datetime.now().isoformat(),
            "tracks": []
        }
        
        # Add lyrics if available
        if state.lyrics.get("content"):
            song["lyrics"] = state.lyrics["content"]
        
        # Add album cover if available from design agent
        if state.album_art and state.album_art.get("image_url"):
            song["albumCover"] = state.album_art["image_url"]
            logger.info(f"Added album cover to song structure: {state.album_art['image_url']}")
        elif state.album_art and state.album_art.get("concept"):
            # If no image URL but we have a concept, add that for reference
            song["albumCoverConcept"] = state.album_art.get("concept", "")
            logger.info("Added album cover concept to song structure (no image generated)")
        
        # Combine all tracks
        all_tracks = []
        
        # Add vocal tracks
        vocal_tracks = state.vocal_assignments.get("tracks", [])
        all_tracks.extend(vocal_tracks)
        
        # Add instrumental tracks
        instrumental_tracks = state.instrumental_content.get("tracks", [])
        all_tracks.extend(instrumental_tracks)
        
        # Apply effects to tracks
        track_effects = state.effects_config.get("track_effects", {})
        clip_effects = state.effects_config.get("clip_effects", {})
        
        for track in all_tracks:
            track_id = track.get("id")
            
            # Apply track-level effects
            if track_id in track_effects:
                track["effects"] = track_effects[track_id]
            elif "effects" not in track:
                track["effects"] = {"reverb": 0, "delay": 0, "distortion": 0}
            
            # Apply clip-level effects and ensure schema compliance
            for clip in track.get("clips", []):
                clip_id = clip.get("id")
                if clip_id in clip_effects:
                    clip["effects"] = clip_effects[clip_id]
                elif "effects" not in clip:
                    clip["effects"] = {"reverb": 0, "delay": 0, "distortion": 0}
                
                # FINAL SCHEMA COMPLIANCE CHECK: Remove any remaining musical_content structures
                if 'musical_content' in clip:
                    musical_content = clip.pop('musical_content')
                    # Move notes to clip level if they exist in musical_content
                    if 'notes' in musical_content and 'notes' not in clip:
                        # Handle both simple notes array and complex note objects
                        if isinstance(musical_content['notes'], list) and musical_content['notes']:
                            # If notes are objects with 'note' property, extract just the note names
                            if isinstance(musical_content['notes'][0], dict) and 'note' in musical_content['notes'][0]:
                                clip['notes'] = [note_obj['note'] for note_obj in musical_content['notes']]
                            else:
                                # If notes are already simple strings, use as-is
                                clip['notes'] = musical_content['notes']
                        else:
                            # Fallback to simple default notes
                            clip['notes'] = generate_intelligent_default_notes(clip.get('instrument', 'piano'), 'C', 'pop')
                    logger.info(f"🔧 FINAL FIX: Removed musical_content from clip {clip_id} in final assembly")
                
                # Ensure synth clips have notes
                if clip.get('type') == 'synth' and 'notes' not in clip:
                    clip['notes'] = generate_intelligent_default_notes(clip.get('instrument', 'piano'), 'C', 'pop')
                
                # Remove any other non-schema fields
                non_schema_fields = ['category', 'role', 'pattern']
                for field in non_schema_fields:
                    if field in clip:
                        clip.pop(field)
        
        song["tracks"] = all_tracks
        return song
    
    def _apply_qa_fixes(self, song: Dict[str, Any], state: SongState) -> Dict[str, Any]:
        """Apply automatic fixes to ensure schema compliance"""
        # Ensure all required fields are present
        defaults = {
            "id": f"song-{uuid.uuid4()}",
            "name": "Generated Song",
            "tempo": 120,
            "timeSignature": [4, 4],
            "key": "C",
            "duration": 32,
            "tracks": [],
            "createdAt": datetime.now().isoformat(),
            "updatedAt": datetime.now().isoformat()
        }
        
        for key, default_value in defaults.items():
            if key not in song:
                song[key] = default_value
        
        # Fix track issues
        for track in song.get("tracks", []):
            # Ensure required track fields
            track_defaults = {
                "volume": 0.8,
                "pan": 0.0,
                "muted": False,
                "solo": False,
                "clips": [],
                "effects": {"reverb": 0, "delay": 0, "distortion": 0}
            }
            
            for key, default_value in track_defaults.items():
                if key not in track:
                    track[key] = default_value
            
            # Ensure unique track ID
            if "id" not in track:
                track["id"] = f"track-{uuid.uuid4()}"
            
            # Fix clip issues
            for clip in track.get("clips", []):
                # Ensure required clip fields
                clip_defaults = {
                    "volume": 0.8,
                    "effects": {"reverb": 0, "delay": 0, "distortion": 0}
                }
                
                for key, default_value in clip_defaults.items():
                    if key not in clip:
                        clip[key] = default_value
                
                # Ensure unique clip ID and trackId reference
                if "id" not in clip:
                    clip["id"] = f"clip-{uuid.uuid4()}"
                if "trackId" not in clip:
                    clip["trackId"] = track["id"]
        
        return song
    
    def _extract_song_title(self, song_idea: str) -> str:
        """Extract a song title from the song idea"""
        if not song_idea:
            return "Generated Song"
        
        # Simple extraction - take first few words or find title-like phrases
        words = song_idea.split()
        if len(words) <= 4:
            return song_idea.title()
        
        # Look for quoted titles
        if '"' in song_idea:
            parts = song_idea.split('"')
            if len(parts) >= 3:
                return parts[1].title()
        
        # Take first 3-4 words
        return " ".join(words[:4]).title()
    
    def _parse_custom_lyrics(self, lyrics: str, structure: Dict[str, Any]) -> Dict[str, List[str]]:
        """Parse custom lyrics into sections based on song structure"""
        lines = [line.strip() for line in lyrics.split('\n') if line.strip()]
        sections = {}
        
        # Simple distribution across sections
        section_names = list(structure.keys())
        if section_names and lines:
            lines_per_section = max(1, len(lines) // len(section_names))
            
            for i, section in enumerate(section_names):
                start_idx = i * lines_per_section
                end_idx = start_idx + lines_per_section if i < len(section_names) - 1 else len(lines)
                sections[section] = lines[start_idx:end_idx]
        
        return sections


# ============================================================================
# API INTEGRATION
# ============================================================================

async def generate_song_with_langgraph(request_data: Dict[str, Any], openai_api_key: str) -> Dict[str, Any]:
    """
    Main API function to generate a song using the LangGraph multi-agent system
    
    Args:
        request_data: Dictionary containing song generation parameters from frontend
        openai_api_key: OpenAI API key for the language models
    
    Returns:
        Dictionary with success status and generated song structure
    """
    try:
        # Parse request data into SongGenerationRequest
        # Derive mood from style tags and song idea
        style_tags = request_data.get("style_tags", [])
        song_idea = request_data.get("song_idea", "")
        mood = ""
        if style_tags:
            # Ensure style_tags are strings before joining
            safe_tags = [str(tag) if isinstance(tag, dict) else tag for tag in style_tags]
            mood = ", ".join(safe_tags)
        if song_idea and mood:
            mood = f"{mood} (inspired by: {song_idea})"
        elif song_idea:
            mood = song_idea
        
        request = SongGenerationRequest(
            song_idea=song_idea,
            style_tags=style_tags,
            custom_style=request_data.get("custom_style", ""),
            lyrics_option=request_data.get("lyrics_option", "automatically"),
            custom_lyrics=request_data.get("custom_lyrics", ""),
            is_instrumental=request_data.get("is_instrumental", False),
            duration=request_data.get("duration", ""),
            song_key=request_data.get("song_key", ""),
            selected_provider=request_data.get("selected_provider", "openai"),
            selected_model=request_data.get("selected_model", "gpt-4"),
            mood=mood
        )
        
        # Get Anthropic API key from environment for provider support
        import os
        anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')
        
        # Initialize and run the generator with provider/model selection
        print(f"Initializing LangGraph generator with provider: {request.selected_provider}, model: {request.selected_model}")
        generator = LangGraphSongGenerator(
            openai_api_key=openai_api_key,
            anthropic_api_key=anthropic_api_key,
            provider=request.selected_provider,
            model=request.selected_model
        )
        print(f"Generator initialized - LLM: {'Yes' if generator.llm else 'No'}, Graph: {'Yes' if generator.graph else 'No'}")
        result = await generator.generate_song(request)
        
        return result
        
    except Exception as e:
        safe_log_error(f"Error in LangGraph song generation: {e}")
        return {
            "success": False,
            "error": str(e),
            "errors": [str(e)]
        }


# ============================================================================
# TESTING AND DEVELOPMENT
# ============================================================================

async def test_langgraph_generation():
    """Test function for development purposes"""
    test_request = {
        "song_idea": "A happy summer pop song about friendship",
        "style_tags": ["pop", "upbeat", "summer"],
        "custom_style": "",
        "lyrics_option": "automatically",
        "custom_lyrics": "",
        "is_instrumental": False,
        "duration": "3 minutes",
        "song_key": "C",
        "selected_provider": "openai",
        "selected_model": "gpt-4"
    }
    
    # Note: You'd need to provide a real API key for testing
    # result = await generate_song_with_langgraph(test_request, "your-openai-api-key")
    # print(json.dumps(result, indent=2))
    
    print("Test function ready - provide API key to run actual test")


if __name__ == "__main__":
    # Run test if executed directly
    asyncio.run(test_langgraph_generation())

