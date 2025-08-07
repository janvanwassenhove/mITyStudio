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
8. DesignAgent - Creates album cover concept
9. QAAgent - Final validation, fixes missing fields, validates against schema

The system respects the existing mITyStudio JSON schema and integrates with
available voices, instruments, and samples.
"""

import json
import uuid
import asyncio
import logging
import os
import re
import traceback
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
try:
    from .langchain.music_tools import MusicCompositionTools
    print("Successfully imported full MusicCompositionTools")
except Exception as e:
    print(f"Warning: Full music tools not available, using fallbacks: {e}")

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
    
    # Initialize OpenAI LLM with minimal parameters to avoid 'proxies' error
    if ChatOpenAI and openai_key:
        try:
            print("🚀 Creating global OpenAI LLM...")
            # Use minimal parameters to avoid compatibility issues
            _global_openai_llm = ChatOpenAI(
                api_key=openai_key,
                model="gpt-4",  # Use model instead of model_name
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
                    openai_api_key=openai_key,  # Try alternative parameter name
                    model_name="gpt-4",
                    temperature=0.7,
                    timeout=120  # Increased timeout for fallback as well
                )
                print("✅ Global OpenAI LLM initialized with alternative parameters")
                logger.info("✓ Global OpenAI LLM initialized with alternative parameters")
            except Exception as e2:
                print(f"❌ Alternative OpenAI LLM initialization also failed: {e2}")
                logger.error(f"✗ Alternative OpenAI LLM initialization failed: {e2}")
    else:
        print(f"⚠️ OpenAI LLM not available - ChatOpenAI: {ChatOpenAI is not None}, Key: {bool(openai_key)}")
    
    # Initialize Anthropic LLM with minimal parameters
    if ChatAnthropic and anthropic_key:
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
                    anthropic_api_key=anthropic_key,  # Try alternative parameter name
                    model_name="claude-3-5-sonnet-20241022",
                    temperature=0.7,
                    timeout=120  # Increased timeout for fallback as well
                )
                print("✅ Global Anthropic LLM initialized with alternative parameters")
                logger.info("✓ Global Anthropic LLM initialized with alternative parameters")
            except Exception as e2:
                print(f"❌ Alternative Anthropic LLM initialization also failed: {e2}")
                logger.error(f"✗ Alternative Anthropic LLM initialization failed: {e2}")
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
    is_ready_for_export: bool = False
    
    # Final output
    final_song_json: Dict[str, Any] = field(default_factory=dict)
    
    # Workflow control
    current_agent: str = ""
    revision_count: int = 0
    max_revisions: int = 3
    
    # Error tracking
    errors: List[str] = field(default_factory=list)


class LangGraphSongGenerator:
    """Main class for the multi-agent song generation system"""
    
    def __init__(self, openai_api_key: str = None, anthropic_api_key: str = None, 
                 provider: str = "openai", model: str = "gpt-4"):
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
            if ChatAnthropic and anthropic_key:
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
                logger.error(f"❌ Cannot create Anthropic LLM - ChatAnthropic: {ChatAnthropic is not None}, Key: {bool(anthropic_key)}")
                if _global_anthropic_llm:
                    self.llm = _global_anthropic_llm
                    logger.info("🔄 Using global Anthropic LLM")
                else:
                    logger.error("❌ No Anthropic options available")
        elif self.provider.lower() == "openai":
            logger.info(f"🎯 User selected OPENAI provider")
            if ChatOpenAI and openai_key:
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
        
        # Log final result
        if self.llm:
            llm_type = type(self.llm).__name__
            logger.info(f"🎉 FINAL LLM: {llm_type} (user wanted: {self.provider})")
        else:
            logger.error(f"💥 FINAL LLM: None (user wanted: {self.provider})")
        
        # Always use OpenAI for album cover generation (design phase) if available
        if ChatOpenAI and openai_key:
            try:
                # For design phase, always use OpenAI with a good model for image generation
                self.openai_llm = ChatOpenAI(
                    api_key=openai_key,
                    model="gpt-4o",  # Best model for image generation prompts
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
                logger.warning("✗ No OpenAI LLM available - album cover generation may fail")
    
    async def _safe_progress_callback(self, message: str, progress: int, agent: str = None):
        """Safely call progress callback whether it's async or sync"""
        if self.progress_callback:
            try:
                if asyncio.iscoroutinefunction(self.progress_callback):
                    await self._safe_progress_callback(message, progress, agent)
                else:
                    self.progress_callback(message, progress, agent)
            except Exception as e:
                logger.warning(f"Progress callback failed: {e}")

    async def _call_llm_safely(self, prompt: str) -> str:
        """
        Call LLM with proper message format for both OpenAI and Anthropic
        Anthropic requires at least one HumanMessage, OpenAI accepts SystemMessage only
        """
        try:
            # Check if LLM is available
            if self.llm is None:
                print(f"ERROR: LLM is None in _call_llm_safely!")
                print(f"Global LLMs status - OpenAI: {bool(_global_openai_llm)}, Anthropic: {bool(_global_anthropic_llm)}")
                raise ValueError("LLM is not initialized - cannot make API call")
            
            # Add comprehensive logging to track LLM usage
            llm_type = type(self.llm).__name__
            llm_model = getattr(self.llm, 'model', getattr(self.llm, 'model_name', 'unknown'))
            print(f"🔍 CALLING LLM: {llm_type} | Model: {llm_model} | User wanted: {self.provider}")
            print(f"DEBUG: About to call LLM {llm_type} with prompt length {len(prompt)}")
            print(f"DEBUG: LLM instance: {self.llm}")
            print(f"DEBUG: LLM has ainvoke: {hasattr(self.llm, 'ainvoke')}")
            print(f"DEBUG: LLM has invoke: {hasattr(self.llm, 'invoke')}")
            
            # Verify the LLM matches user's selection
            if self.provider.lower() == "anthropic" and llm_type != "ChatAnthropic":
                print(f"🚨 WARNING: User selected ANTHROPIC but using {llm_type}!")
                logger.warning(f"LLM mismatch: User wanted {self.provider} but using {llm_type}")
            elif self.provider.lower() == "openai" and llm_type != "ChatOpenAI":
                print(f"🚨 WARNING: User selected OPENAI but using {llm_type}!")
                logger.warning(f"LLM mismatch: User wanted {self.provider} but using {llm_type}")
            
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
            
            print(f"DEBUG: About to call LLM with {len(messages)} messages")
            
            # Try async first, fallback to sync if needed
            if hasattr(self.llm, 'ainvoke'):
                print("DEBUG: Trying async ainvoke...")
                try:
                    # Check what ainvoke returns before awaiting
                    ainvoke_result = self.llm.ainvoke(messages)
                    print(f"DEBUG: ainvoke returned: {type(ainvoke_result)} - {ainvoke_result}")
                    
                    if ainvoke_result is None:
                        print("ERROR: ainvoke returned None, trying sync invoke...")
                        raise ValueError("ainvoke returned None")
                    
                    response = await ainvoke_result
                    print(f"DEBUG: Async LLM call successful, response type: {type(response)}")
                except Exception as async_error:
                    print(f"DEBUG: Async call failed: {async_error}, trying sync...")
                    # Fallback to sync call
                    if hasattr(self.llm, 'invoke'):
                        response = await asyncio.get_event_loop().run_in_executor(
                            None, self.llm.invoke, messages
                        )
                        print(f"DEBUG: Sync LLM call successful, response type: {type(response)}")
                    else:
                        raise async_error
            elif hasattr(self.llm, 'invoke'):
                print("DEBUG: No ainvoke available, using sync invoke...")
                response = await asyncio.get_event_loop().run_in_executor(
                    None, self.llm.invoke, messages
                )
                print(f"DEBUG: Sync LLM call successful, response type: {type(response)}")
            else:
                raise ValueError("LLM has neither ainvoke nor invoke methods")
            
            print(f"DEBUG: Response content length: {len(response.content) if response and hasattr(response, 'content') and response.content else 'None'}")
            
            if not response or not hasattr(response, 'content') or not response.content:
                print("ERROR: Response is empty or has no content!")
                raise ValueError("LLM returned empty response")
                
            return response.content.strip()
        except Exception as e:
            print(f"ERROR in _call_llm_safely: {e}")
            print(f"ERROR type: {type(e)}")
            print(f"ERROR traceback: {traceback.format_exc()}")
            
            # Provide more specific error messages for timeouts
            if "timeout" in str(e).lower() or "timed out" in str(e).lower():
                logger.error(f"LLM request timed out after 120 seconds: {e}")
                raise TimeoutError("LLM request timed out. The AI model took too long to respond. Please try again or use a simpler prompt.")
            elif "rate limit" in str(e).lower():
                logger.error(f"LLM rate limit exceeded: {e}")
                raise Exception("API rate limit exceeded. Please wait a moment and try again.")
            else:
                logger.error(f"LLM call failed: {e}")
                raise
    
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
            'gpt-4o': 'gpt-4o',
            'gpt-4o-mini': 'gpt-4o-mini',
            'gpt-4-turbo': 'gpt-4-turbo',
            'gpt-4-turbo-preview': 'gpt-4-turbo-preview',
            'gpt-4': 'gpt-4',
            'gpt-3.5-turbo': 'gpt-3.5-turbo'
        }
        return model_mapping.get(model_id, 'gpt-4')
    
    def _build_graph(self) -> None:
        """Build the LangGraph workflow"""
        if not StateGraph:
            raise ImportError("LangGraph not available")
        
        # Create the state graph
        workflow = StateGraph(SongState)
        
        # Add all agent nodes
        workflow.add_node("composer", self._composer_agent)
        workflow.add_node("arrangement", self._arrangement_agent)
        workflow.add_node("lyrics", self._lyrics_agent)
        workflow.add_node("vocal", self._vocal_agent)
        workflow.add_node("instrument", self._instrument_agent)
        workflow.add_node("effects", self._effects_agent)
        workflow.add_node("review", self._review_agent)
        workflow.add_node("design", self._design_agent)
        workflow.add_node("qa", self._qa_agent)
        
        # Define the workflow edges
        workflow.set_entry_point("composer")
        
        # Linear progression with conditional review feedback
        workflow.add_edge("composer", "arrangement")
        workflow.add_edge("arrangement", "lyrics")
        workflow.add_edge("lyrics", "vocal")
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
        workflow.add_edge("qa", END)
        
        # Compile the graph
        self.graph = workflow.compile()
    
    async def generate_song(self, request: SongGenerationRequest, progress_callback=None) -> Dict[str, Any]:
        """Generate a complete song structure using the multi-agent system"""
        if not self.graph:
            raise RuntimeError("Graph not initialized. Check dependencies and API key.")
        
        # Store progress callback for agents to use
        self.progress_callback = progress_callback
        
        # Add progress tracking
        await self._safe_progress_callback("Initializing song generation...", 0)
        
        # Initialize state
        initial_state = SongState(
            request=request,
            available_instruments=self.music_tools.available_instruments,
            available_samples=self.music_tools.available_samples,
            available_voices=self.music_tools.available_voices
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
            else:
                is_ready = final_state.is_ready_for_export
                final_song_json = final_state.final_song_json
                album_art = final_state.album_art
                review_notes = final_state.review_notes
                qa_corrections = final_state.qa_corrections
                errors = final_state.errors
            
            await self._safe_progress_callback("Song generation completed!", 100)
            
            if is_ready and final_song_json:
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
                    "error": f"Song generation failed validation: {'; '.join(detailed_errors[:3])}",
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
                await self._safe_progress_callback("Composer: Setting tempo, key, and structure...", 15, "composer")
            except Exception as e:
                logger.warning(f"Progress callback failed: {e}")
        
        # Map user duration preference to actual seconds/bars
        duration_mapping = {
            'short': {'seconds': 120, 'bars': 32},    # 2 minutes
            'medium': {'seconds': 180, 'bars': 48},   # 3 minutes  
            'long': {'seconds': 300, 'bars': 80}      # 5 minutes
        }
        
        preferred_duration = duration_mapping.get(state.request.duration, {'seconds': 180, 'bars': 48})
        
        prompt = f"""You are a professional music composer. Based on the song request, define the global musical parameters.

Song Request:
- Idea: {state.request.song_idea}
- Style Tags: {', '.join(state.request.style_tags)}
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
        bars_per_minute = tempo / 4  # Assuming 4/4 time signature
        total_bars = int((duration_seconds / 60) * bars_per_minute)
        
        prompt = f"""You are a music arranger. Design the song structure and track arrangement for a complete, professional-sounding song.

Song Parameters:
- Tempo: {tempo} BPM
- Key: {state.global_params.get('key')}
- Total Duration: {duration_seconds} seconds (~{total_bars} bars)
- Time Signature: {state.global_params.get('timeSignature')}
- Style: {', '.join(state.request.style_tags)} {state.request.custom_style}
- Instrumental: {state.request.is_instrumental}
- Song Idea: {state.request.song_idea}

Available Instruments by Category:
{self.music_tools.format_instruments_for_prompt(state.available_instruments)}

Available Voices: {list(state.available_voices.keys())}

Design a complete song arrangement. Respond ONLY with a JSON object:
{{
    "structure": {{
        "intro": {{"start_time": 0, "duration": 8, "bars": 4, "description": "Gentle piano introduction"}},
        "verse1": {{"start_time": 8, "duration": 16, "bars": 8, "description": "First verse with vocals and light accompaniment"}},
        "chorus1": {{"start_time": 24, "duration": 16, "bars": 8, "description": "Full arrangement chorus with all instruments"}},
        "verse2": {{"start_time": 40, "duration": 16, "bars": 8, "description": "Second verse with additional elements"}},
        "chorus2": {{"start_time": 56, "duration": 16, "bars": 8, "description": "Second chorus with harmonies"}},
        "bridge": {{"start_time": 72, "duration": 12, "bars": 6, "description": "Bridge section with key/mood change"}},
        "final_chorus": {{"start_time": 84, "duration": 20, "bars": 10, "description": "Extended final chorus"}},
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
            "sections": ["verse1", "chorus1", "verse2", "chorus2", "bridge", "final_chorus"],
            "pan": 0.0,
            "volume": 0.8
        }},
        {{
            "name": "Piano",
            "instrument": "piano", 
            "category": "keyboards",
            "role": "harmonic",
            "priority": "high",
            "sections": ["intro", "verse1", "chorus1", "verse2", "chorus2", "bridge", "final_chorus", "outro"],
            "pan": 0.0,
            "volume": 0.7
        }},
        {{
            "name": "Bass",
            "instrument": "bass",
            "category": "strings", 
            "role": "rhythmic",
            "priority": "medium",
            "sections": ["verse1", "chorus1", "verse2", "chorus2", "bridge", "final_chorus"],
            "pan": 0.0,
            "volume": 0.8
        }},
        {{
            "name": "Drums",
            "instrument": "drums",
            "category": "percussion",
            "role": "rhythmic", 
            "priority": "medium",
            "sections": ["chorus1", "verse2", "chorus2", "bridge", "final_chorus"],
            "pan": 0.0,
            "volume": 0.6
        }}
    ],
    "arrangement_philosophy": "Explanation of arrangement choices and how they serve the song",
    "total_tracks": 4,
    "complexity_level": "medium"
}}

Guidelines:
- Create a logical song structure that builds energy and maintains interest
- Plan 3-8 tracks typically, depending on style complexity  
- Include appropriate tracks for the style (rock: drums+bass+guitar+vocals, jazz: piano+bass+drums+vocals, etc.)
- For vocals: specify voice_id from available voices (soprano01, alto01, tenor01, bass01)
- Each track should have a clear role: melodic (lead lines), harmonic (chords), rhythmic (beat/groove), textural (atmosphere)
- Consider arrangement dynamics (intro lighter, chorus fuller, bridge different)
- Plan which sections each track will play in (not all tracks play throughout)
- Use appropriate pan positions for stereo field
- Match instruments to style requirements
- If instrumental, focus on interesting melodic interplay between instruments
- Ensure total duration matches the target ({duration_seconds} seconds)
"""
        
        try:
            logger.info("🎹 ArrangementAgent: Starting arrangement generation...")
            response = await self._call_llm_safely(prompt)
            logger.info("🎹 ArrangementAgent: Received LLM response, parsing JSON...")
            
            # Create fallback data in case of JSON parsing failure
            fallback_data = {
                "structure": self._create_default_structure(duration_seconds, state.request.style_tags),
                "tracks_needed": self._create_default_tracks(state.request.is_instrumental, state.request.style_tags),
                "arrangement_philosophy": "Using intelligent default arrangement due to parsing error",
                "total_tracks": 4,
                "complexity_level": "medium"
            }
            
            result = self._safe_json_parse(response, fallback_data)
            
            structure = result.get("structure", {})
            planned_tracks = result.get("tracks_needed", [])
            
            # Validate and adjust structure timing to fit target duration
            total_structure_time = 0
            for section_name, section_info in structure.items():
                section_duration = section_info.get("duration", 8)
                total_structure_time = max(total_structure_time, 
                                         section_info.get("start_time", 0) + section_duration)
            
            # Scale if necessary to fit target duration
            if abs(total_structure_time - duration_seconds) > 10:  # More than 10 seconds off
                scale_factor = duration_seconds / total_structure_time
                for section_info in structure.values():
                    section_info["start_time"] = int(section_info["start_time"] * scale_factor)
                    section_info["duration"] = int(section_info["duration"] * scale_factor)
            
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
            default_tracks = self._create_default_tracks(state.request.is_instrumental, state.request.style_tags)
            
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
    
    def _create_default_tracks(self, is_instrumental: bool, style_tags: List[str]) -> List[Dict[str, Any]]:
        """Create default track layout based on whether instrumental and style."""
        tracks = []
        
        # Always include piano as foundation
        tracks.append({
            "name": "Piano",
            "instrument": "piano",
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
        
        # Add style-appropriate instruments
        if any(style in ['rock', 'pop', 'alternative'] for style in style_tags):
            tracks.extend([
                {
                    "name": "Bass",
                    "instrument": "bass",
                    "category": "strings",
                    "role": "rhythmic", 
                    "priority": "medium",
                    "sections": ["verse1", "chorus1", "verse2", "chorus2", "bridge", "final_chorus"],
                    "pan": 0.0,
                    "volume": 0.8
                },
                {
                    "name": "Drums",
                    "instrument": "drums",
                    "category": "percussion",
                    "role": "rhythmic",
                    "priority": "medium", 
                    "sections": ["chorus1", "verse2", "chorus2", "bridge", "final_chorus"],
                    "pan": 0.0,
                    "volume": 0.6
                }
            ])
        
        return tracks
    
    async def _lyrics_agent(self, state: SongState) -> SongState:
        """
        LyricsAgent: Creates lyrics aligned with structure and musical parameters
        - Section-specific lyrics matching song structure timing
        - Rhyme schemes and meter appropriate to tempo and style
        - Emotional alignment with request and arrangement
        """
        state.current_agent = "lyrics"
        
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
            logger.info("📝 LyricsAgent: Skipping - instrumental track")
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
- Musical Style: {', '.join(state.request.style_tags)} {state.request.custom_style}
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
            result = json.loads(response)
            
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
        state.current_agent = "vocal"
        
        # Send progress update if callback is available
        if self.progress_callback:
            try:
                await self._safe_progress_callback("Vocal: Assigning voices and vocal parts...", 45, "vocal")
            except Exception as e:
                logger.warning(f"Progress callback failed: {e}")
        
        if state.request.is_instrumental or not state.lyrics.get("content"):
            state.vocal_assignments = {
                "tracks": [],
                "is_instrumental": True,
                "voice_assignments": {},
                "reasoning": "Instrumental track - no vocals needed"
            }
            logger.info("🎤 VocalAgent: Skipping - instrumental track")
            return state
        
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
- Style: {', '.join(state.request.style_tags)} {state.request.custom_style}

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
            "mute": false,
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
                    "voices": [
                        {{
                            "voice_id": "soprano01",
                            "lyrics": [
                                {{
                                    "text": "First line of verse lyrics",
                                    "notes": ["C4", "D4", "E4", "F4", "G4"],
                                    "start": 0.0,
                                    "durations": [1.0, 1.0, 0.5, 0.5, 2.0],
                                    "velocities": [80, 75, 85, 80, 90]
                                }},
                                {{
                                    "text": "Second line continues melody",
                                    "notes": ["F4", "E4", "D4", "C4"],
                                    "start": 5.0,
                                    "durations": [1.5, 1.0, 1.0, 1.5],
                                    "velocities": [75, 80, 85, 80]
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
- Map every line of lyrics to specific notes in the song's key ({key})
- Use appropriate vocal ranges for each voice (soprano: C4-C6, alto: G3-G5, tenor: C3-C5, bass: E2-E4)
- Calculate accurate timing: startTime and duration based on structure timing
- Create singable melodies that match the tempo ({tempo} BPM) and style
- Include appropriate effects (reverb, delay) for the style
- For harmony tracks, create supporting notes that complement the lead melody
- Use voice_id values that match available voices: {list(state.available_voices.keys())}
- Ensure total clip duration matches the section duration from structure
- Consider vocal production appropriate to style (pop: compressed, classical: natural, etc.)
- Create emotional arc through melody: verses conversational, chorus soaring
- Include backing vocals/harmonies for choruses and final sections
- Map syllables to note timing carefully - avoid cramming too many syllables per beat
- Use velocities (60-100) to create dynamic expression in the vocal performance
"""
        
        try:
            response = await self._call_llm_safely(prompt)
            result = json.loads(response)
            
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
                                "text": " ".join(section_lyrics) if isinstance(section_lyrics, list) else section_lyrics,
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
                "mute": False,
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
                                   and t.get('instrument') != 'vocals']
        
        structure = state.arrangement.get('structure', {})
        key = state.global_params.get('key', 'C major')
        tempo = state.global_params.get('tempo', 120)
        time_signature = state.global_params.get('timeSignature', '4/4')
        
        prompt = f"""You are a professional instrumental arranger and composer. Create detailed instrumental tracks with musical content.

Song Parameters:
- Key: {key}
- Tempo: {tempo} BPM
- Time Signature: {time_signature}
- Style: {', '.join(state.request.style_tags)} {state.request.custom_style}
- Song Idea: {state.request.song_idea}

Available Instruments by Category:
{self.music_tools.format_instruments_for_prompt(state.available_instruments)}

Song Structure (with timing in seconds):
{json.dumps(structure, indent=2)}

Planned Instrumental Tracks from Arrangement:
{json.dumps(planned_instrument_tracks, indent=2)}

Create complete instrumental tracks with musical content. Respond ONLY with a JSON object:
{{
    "tracks": [
        {{
            "id": "track-piano",
            "name": "Piano",
            "instrument": "piano",
            "category": "keyboards", 
            "volume": 0.7,
            "pan": 0.0,
            "mute": false,
            "solo": false,
            "clips": [
                {{
                    "id": "clip-piano-intro",
                    "trackId": "track-piano",
                    "startTime": 0,
                    "duration": 8,
                    "type": "audio",
                    "instrument": "piano",
                    "category": "keyboards",
                    "volume": 0.7,
                    "pan": 0.0,
                    "effects": {{"reverb": 0.1, "delay": 0, "distortion": 0}},
                    "musical_content": {{
                        "chord_progression": ["Cmaj", "Am", "F", "G"],
                        "pattern": "arpeggiated_chords",
                        "notes": [
                            {{"note": "C4", "start": 0.0, "duration": 1.0, "velocity": 75}},
                            {{"note": "E4", "start": 0.5, "duration": 1.0, "velocity": 70}},
                            {{"note": "G4", "start": 1.0, "duration": 1.0, "velocity": 72}}
                        ],
                        "rhythm_pattern": "steady_eighth_notes",
                        "role": "harmonic_foundation"
                    }}
                }}
            ]
        }},
        {{
            "id": "track-bass",
            "name": "Bass",
            "instrument": "bass",
            "category": "strings",
            "volume": 0.8,
            "pan": 0.0,
            "mute": false,
            "solo": false,
            "clips": [
                {{
                    "id": "clip-bass-verse1",
                    "trackId": "track-bass",
                    "startTime": 8,
                    "duration": 16,
                    "type": "audio",
                    "instrument": "bass",
                    "category": "strings",
                    "volume": 0.8,
                    "pan": 0.0,
                    "effects": {{"reverb": 0.05, "delay": 0, "distortion": 0}},
                    "musical_content": {{
                        "bass_line": ["C2", "A1", "F2", "G2"],
                        "pattern": "root_note_emphasis",
                        "notes": [
                            {{"note": "C2", "start": 0.0, "duration": 2.0, "velocity": 85}},
                            {{"note": "A1", "start": 4.0, "duration": 2.0, "velocity": 82}},
                            {{"note": "F2", "start": 8.0, "duration": 2.0, "velocity": 83}},
                            {{"note": "G2", "start": 12.0, "duration": 2.0, "velocity": 85}}
                        ],
                        "rhythm_pattern": "quarter_note_foundation",
                        "role": "rhythmic_foundation"
                    }}
                }}
            ]
        }}
    ],
    "instrumental_philosophy": "Explanation of instrumental choices and arrangement approach",
    "harmonic_analysis": "Description of chord progressions and harmonic movement",
    "rhythmic_structure": "Explanation of how different instruments create the groove",
    "production_notes": "Guidance for mixing, effects, and overall sound"
}}

Critical Guidelines:
- Create clips for EVERY section where each instrument should play (based on planned tracks)
- Use ONLY instruments from the available_instruments list
- Calculate accurate timing: startTime and duration based on structure timing in seconds
- Create appropriate musical content for each instrument's role:
  * Keyboards: chord progressions, arpeggios, melodic lines
  * Strings: bass lines, melodic lines, harmonic support
  * Percussion: drum patterns, rhythmic emphasis
  * Woodwinds/Brass: melodic lines, harmonic fills
- Match musical content to song style: {', '.join(state.request.style_tags)}
- Use appropriate effects for each instrument and style
- Ensure all instruments work together harmonically in key: {key}
- Create interesting rhythmic interplay between instruments
- Consider instrument ranges and capabilities
- Include both chordal and single-note content as appropriate
- Plan dynamics: verses lighter, choruses fuller
- Ensure track and clip IDs are unique
- Set appropriate volume levels and pan positions for instrument separation
- Match tempo ({tempo} BPM) with appropriate note durations and patterns
"""
        
        try:
            response = await self._call_llm_safely(prompt)
            result = json.loads(response)
            
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
            
            # Ensure track and clip IDs are unique
            for i, track in enumerate(tracks):
                if not track.get('id'):
                    track['id'] = f"track-instrument-{i+1}"
                for j, clip in enumerate(track.get('clips', [])):
                    if not clip.get('id'):
                        clip['id'] = f"clip-{track['id']}-{j+1}"
                    clip['trackId'] = track['id']
            
            state.instrument_assignments = {
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
            
            state.instrument_assignments = {
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
        
        for i, planned_track in enumerate(planned_tracks):
            track_id = f"track-instrument-{i+1}"
            instrument = planned_track.get('instrument', 'piano')
            category = planned_track.get('category', 'keyboards')
            
            # Ensure instrument is available
            if category in available_instruments and instrument not in available_instruments[category]:
                if available_instruments[category]:
                    instrument = available_instruments[category][0]  # Use first available in category
            
            clips = []
            sections_to_play = planned_track.get('sections', list(structure.keys()))
            
            for section_name in sections_to_play:
                if section_name in structure:
                    section_info = structure[section_name]
                    
                    clip = {
                        "id": f"clip-{track_id}-{section_name}",
                        "trackId": track_id,
                        "startTime": section_info.get('start_time', 0),
                        "duration": section_info.get('duration', 8),
                        "type": "audio",
                        "instrument": instrument,
                        "category": category,
                        "volume": 0.7,
                        "pan": 0.0,
                        "effects": {"reverb": 0.1, "delay": 0, "distortion": 0},
                        "musical_content": {
                            "notes": [
                                {"note": "C4", "start": 0.0, "duration": 2.0, "velocity": 75},
                                {"note": "G4", "start": 2.0, "duration": 2.0, "velocity": 75}
                            ],
                            "pattern": "simple_default",
                            "role": "harmonic"
                        }
                    }
                    clips.append(clip)
            
            track = {
                "id": track_id,
                "name": planned_track.get('name', f"{instrument.title()} Track"),
                "instrument": instrument,
                "category": category,
                "volume": 0.7,
                "pan": 0.0,
                "mute": False,
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

Song Style: {', '.join(state.request.style_tags)} {state.request.custom_style}
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
            result = json.loads(response)
            
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
- Style: {', '.join(state.request.style_tags)} {state.request.custom_style}
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
            result = json.loads(response)
            
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
- Style: {', '.join(state.request.style_tags)} {state.request.custom_style}
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
            # Always use OpenAI specifically for album cover generation (best for image generation prompts)
            llm_to_use = self.openai_llm if self.openai_llm else None
            
            if not llm_to_use:
                # If no OpenAI available, log that we're skipping album art
                logger.warning("No OpenAI LLM available for album art generation - skipping")
                state.album_art = {
                    "concept": "Album art generation skipped - OpenAI not available",
                    "color_palette": ["#333333", "#666666", "#999999"],
                    "style": "minimalist",
                    "mood": "neutral",
                    "elements": [],
                    "typography": "modern",
                    "composition": "Simple text-based design",
                    "is_generated": False,
                    "provider": "none"
                }
                return state
                
            # Use OpenAI for album cover generation
            logger.info("Using OpenAI LLM for album cover generation")
            
            # Check if it's an Anthropic LLM (shouldn't be for design, but safety check)
            is_anthropic = hasattr(llm_to_use, '__class__') and 'anthropic' in llm_to_use.__class__.__module__.lower()
            
            if is_anthropic:
                messages = [HumanMessage(content=prompt)]
            else:
                messages = [SystemMessage(content=prompt)]
            
            if hasattr(llm_to_use, 'ainvoke'):
                response = await llm_to_use.ainvoke(messages)
            else:
                response = await asyncio.get_event_loop().run_in_executor(
                    None, llm_to_use.invoke, messages
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
            
            state.album_art = {
                "concept": result.get("concept", ""),
                "color_palette": result.get("color_palette", []),
                "style": result.get("style", ""),
                "mood": result.get("mood", ""),
                "elements": result.get("elements", []),
                "typography": result.get("typography", ""),
                "composition": result.get("composition", ""),
                "is_generated": True,
                "provider": "openai"  # Always use OpenAI for album covers
            }
            
            logger.info(f"Album art generated successfully with OpenAI: {result.get('concept', '')[:50]}...")
            
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
    
    async def _qa_agent(self, state: SongState) -> SongState:
        """
        QAAgent: Final validation and structure assembly
        - Fixes missing fields, applies corrections, validates against schema
        """
        state.current_agent = "qa"
        
        # Progress callback for QA agent
        if self.progress_callback:
            try:
                await self._safe_progress_callback("Agent 9/9: Final quality assurance and validation", 99, "qa")
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
        "Any issues that couldn't be automatically fixed"
    ]
}}

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
            response = await self._call_llm_safely(prompt)
            result = json.loads(response)
            
            state.qa_corrections = result.get("corrections_made", [])
            
            # Apply any automatic fixes and finalize
            final_song = self._apply_qa_fixes(final_song, state)
            state.final_song_json = final_song
            
            # Final validation
            if result.get("final_validation") == "pass" and not result.get("remaining_issues"):
                state.is_ready_for_export = True
                logger.info("✓ QA Agent: Song passed final validation")
            else:
                state.errors.extend(result.get("remaining_issues", []))
                logger.warning(f"⚠ QA Agent: Song failed validation - {result.get('remaining_issues', [])}")
            
        except Exception as e:
            safe_log_error(f"QA agent error: {e}")
            state.errors.append(f"QA: {str(e)}")
            # Still try to finalize with current structure
            state.final_song_json = final_song
            # If we have a valid song structure, mark as ready despite LLM errors
            if final_song and final_song.get('tracks') and len(final_song.get('tracks', [])) > 0:
                state.is_ready_for_export = True
                state.qa_corrections.append("Auto-approved despite QA LLM error - song structure appears valid")
                logger.info("✓ QA Agent: Auto-approved song despite LLM error (structure valid)")
        
        # Final completion callback
        if self.progress_callback:
            try:
                await self._safe_progress_callback("✓ Song generation complete! All agents finished.", 100, "complete")
            except Exception as e:
                print(f"Progress callback error: {e}")
        
        return state
    
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
            
            # Apply clip-level effects
            for clip in track.get("clips", []):
                clip_id = clip.get("id")
                if clip_id in clip_effects:
                    clip["effects"] = clip_effects[clip_id]
                elif "effects" not in clip:
                    clip["effects"] = {"reverb": 0, "delay": 0, "distortion": 0}
        
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
            mood = ", ".join(style_tags)
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

