"""
LangChain service package for music composition AI assistance.
"""

from .langchain_service import LangChainService
from .music_tools import MusicCompositionTools
from .song_tools import *
from .lyrics_tools import *

__all__ = [
    'LangChainService',
    'MusicCompositionTools',
    'analyze_song_structure',
    'get_available_instruments',
    'get_available_samples',
    'create_track',
    'add_clip_to_track',
    'generate_chord_progression',
    'create_song_section',
    'modify_song_structure',
    'add_lyrics_to_track',
    'create_multi_voice_lyrics',
    'get_available_voices'
]
