"""
Utility functions and constants for the LangChain service.
"""

import logging
from flask import current_app


def safe_log_error(message: str):
    """Safe error logging that works both inside and outside Flask context"""
    try:
        current_app.logger.error(message)
    except (RuntimeError, NameError):
        # Working outside application context or current_app not available
        print(f"ERROR: {message}")


# Music theory constants
CHORD_PROGRESSIONS = {
    'C': ['C_major', 'Am_minor', 'F_major', 'G_major'],
    'G': ['G_major', 'Em_minor', 'C_major', 'D_major'],
    'F': ['F_major', 'Dm_minor', 'Bb_major', 'C_major'],
    'D': ['D_major', 'Bm_minor', 'G_major', 'A_major'],
    'A': ['A_major', 'F#m_minor', 'D_major', 'E_major'],
    'E': ['E_major', 'C#m_minor', 'A_major', 'B_major'],
    'Am': ['Am_minor', 'F_major', 'C_major', 'G_major'],
    'Em': ['Em_minor', 'C_major', 'G_major', 'D_major'],
    'Dm': ['Dm_minor', 'Bb_major', 'F_major', 'C_major']
}

INTRO_PROGRESSIONS = {
    'C': ['C_major', 'F_major', 'Am_minor', 'G_major'],
    'G': ['G_major', 'C_major', 'Em_minor', 'D_major'],
    'F': ['F_major', 'Bb_major', 'Dm_minor', 'C_major'],
    'D': ['D_major', 'G_major', 'Bm_minor', 'A_major'],
    'A': ['A_major', 'D_major', 'F#m_minor', 'E_major'],
    'E': ['E_major', 'A_major', 'C#m_minor', 'B_major'],
    'Am': ['Am_minor', 'Dm_minor', 'G_major', 'C_major'],
    'Em': ['Em_minor', 'Am_minor', 'D_major', 'G_major'],
    'Dm': ['Dm_minor', 'Gm_minor', 'C_major', 'F_major']
}

BASS_NOTES = {
    'C': ['C2', 'A2', 'F2', 'G2'],
    'G': ['G2', 'E2', 'C2', 'D2'],
    'F': ['F2', 'D2', 'Bb2', 'C2'],
    'D': ['D2', 'B2', 'G2', 'A2'],
    'A': ['A2', 'F#2', 'D2', 'E2'],
    'E': ['E2', 'C#2', 'A2', 'B2'],
    'Am': ['A2', 'F2', 'C2', 'G2'],
    'Em': ['E2', 'C2', 'G2', 'D2'],
    'Dm': ['D2', 'Bb2', 'F2', 'C2']
}

TEMPO_RANGES = {
    'ballad': (60, 90),
    'pop': (110, 130),
    'rock': (120, 140),
    'dance': (128, 140),
    'jazz': (80, 120),
    'blues': (90, 120),
    'country': (120, 140),
    'folk': (90, 120)
}


def get_chord_progression_for_key(key: str) -> list[str]:
    """Get a standard chord progression for a given key"""
    return CHORD_PROGRESSIONS.get(key, CHORD_PROGRESSIONS['C'])


def get_intro_chords_for_key(key: str) -> list[str]:
    """Get appropriate intro chord progression for a given key"""
    return INTRO_PROGRESSIONS.get(key, INTRO_PROGRESSIONS['C'])


def get_bass_notes_for_key(key: str) -> list[str]:
    """Get appropriate bass notes for a given key"""
    return BASS_NOTES.get(key, BASS_NOTES['C'])


def get_suggested_tempo(style: str) -> int:
    """Get suggested tempo for a given musical style"""
    tempo_ranges = {
        'ballad': 70, 'slow': 80, 'pop': 120, 'rock': 130,
        'dance': 128, 'edm': 128, 'jazz': 100, 'blues': 100,
        'country': 130, 'folk': 100, 'classical': 90
    }
    return tempo_ranges.get(style.lower(), 120)


def get_roman_numerals(key: str, chords: list[str]) -> list[str]:
    """Convert chord names to Roman numeral analysis"""
    # Simplified Roman numeral mapping
    roman_map = {
        'major': ['I', 'ii', 'iii', 'IV', 'V', 'vi', 'vii°'],
        'minor': ['i', 'ii°', 'III', 'iv', 'V', 'VI', 'VII']
    }
    
    # This is a simplified implementation
    # In a real application, you'd need proper chord analysis
    if key.endswith('m'):
        return roman_map['minor'][:len(chords)]
    else:
        return roman_map['major'][:len(chords)]
