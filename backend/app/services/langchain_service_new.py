"""
LangChain Service
Handles advanced AI interactions using LangChain framework with React Agent for music composition

This module has been refactored into smaller, focused components.
Import from the langchain package instead for better modularity.
"""

# Import everything from the new modular structure
from .langchain import *

# Backward compatibility - re-export the main classes and functions
from .langchain.langchain_service import LangChainService
from .langchain.music_tools import MusicCompositionTools
from .langchain.utils import safe_log_error as _safe_log_error

# Make sure all tools are available at the module level for backward compatibility
__all__ = [
    'LangChainService',
    'MusicCompositionTools', 
    '_safe_log_error',
    'analyze_song_structure',
    'get_available_instruments',
    'get_available_samples', 
    'search_user_samples',
    'create_track',
    'add_clip_to_track',
    'generate_chord_progression',
    'create_song_section',
    'modify_song_structure',
    'add_lyrics_to_track',
    'create_multi_voice_lyrics',
    'get_available_voices'
]
