"""
AI Service API Routes
Handles chat, music generation, and AI-powered composition features
"""

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.services.ai_service import AIService
from app.services.langchain_service import LangChainService
from app.utils.decorators import handle_errors
import json
import os
import os
from pathlib import Path

ai_bp = Blueprint('ai', __name__)


@ai_bp.route('/chat', methods=['POST'])
@handle_errors
def chat():
    """
    Handle AI chat interactions
    """
    data = request.get_json()
    message = data.get('message', '')
    provider = data.get('provider', 'anthropic')
    model = data.get('model', 'claude-sonnet-4')
    context = data.get('context', {})
    
    if not message:
        return jsonify({'error': 'Message is required'}), 400
    
    ai_service = AIService()
    
    try:
        response = ai_service.chat_completion(
            message=message,
            provider=provider,
            model=model,
            context=context
        )
        
        return jsonify({
            'response': response['content'],
            'provider': provider,
            'model': model,
            'actions': response.get('actions', []),
            'timestamp': response.get('timestamp')
        })
        
    except Exception as e:
        current_app.logger.error(f"AI Chat error: {str(e)}")
        return jsonify({'error': 'AI service temporarily unavailable'}), 503


@ai_bp.route('/generate/chord-progression', methods=['POST'])
@handle_errors
def generate_chord_progression():
    """
    Generate chord progressions using AI
    """
    data = request.get_json()
    genre = data.get('genre', 'pop')
    key = data.get('key', 'C')
    mood = data.get('mood', 'happy')
    complexity = data.get('complexity', 'simple')
    
    ai_service = AIService()
    
    try:
        progression = ai_service.generate_chord_progression(
            genre=genre,
            key=key,
            mood=mood,
            complexity=complexity
        )
        
        return jsonify({
            'progression': progression,
            'metadata': {
                'genre': genre,
                'key': key,
                'mood': mood,
                'complexity': complexity
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Chord generation error: {str(e)}")
        return jsonify({'error': 'Failed to generate chord progression'}), 500


@ai_bp.route('/generate/melody', methods=['POST'])
@handle_errors
def generate_melody():
    """
    Generate melodies using AI
    """
    data = request.get_json()
    scale = data.get('scale', 'major')
    key = data.get('key', 'C')
    tempo = data.get('tempo', 120)
    style = data.get('style', 'pop')
    chord_progression = data.get('chord_progression', [])
    
    ai_service = AIService()
    
    try:
        melody = ai_service.generate_melody(
            scale=scale,
            key=key,
            tempo=tempo,
            style=style,
            chord_progression=chord_progression
        )
        
        return jsonify({
            'melody': melody,
            'metadata': {
                'scale': scale,
                'key': key,
                'tempo': tempo,
                'style': style
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Melody generation error: {str(e)}")
        return jsonify({'error': 'Failed to generate melody'}), 500


@ai_bp.route('/analyze/song', methods=['POST'])
@handle_errors
def analyze_song():
    """
    Analyze song structure and provide suggestions
    """
    data = request.get_json()
    tracks = data.get('tracks', [])
    structure = data.get('structure', {})
    
    ai_service = AIService()
    
    try:
        analysis = ai_service.analyze_song_structure(
            tracks=tracks,
            structure=structure
        )
        
        return jsonify({
            'analysis': analysis,
            'suggestions': analysis.get('suggestions', []),
            'score': analysis.get('score', 0)
        })
        
    except Exception as e:
        current_app.logger.error(f"Song analysis error: {str(e)}")
        return jsonify({'error': 'Failed to analyze song'}), 500


@ai_bp.route('/suggest/instruments', methods=['POST'])
@handle_errors
def suggest_instruments():
    """
    Suggest instruments based on current composition and available sample library
    """
    data = request.get_json()
    genre = data.get('genre', 'pop')
    existing_instruments = data.get('existing_instruments', [])
    mood = data.get('mood', 'neutral')
    tempo = data.get('tempo', 120)
    
    # Get available instruments from sample library
    available_instruments = get_available_sample_instruments()
    
    ai_service = AIService()
    
    try:
        # Get AI suggestions
        suggestions = ai_service.suggest_instruments(
            genre=genre,
            existing_instruments=existing_instruments,
            mood=mood,
            tempo=tempo
        )
        
        # Filter suggestions to only include instruments we have samples for
        available_suggestions = []
        for instrument in suggestions.get('suggestions', []):
            if instrument in available_instruments:
                available_suggestions.append({
                    'name': instrument,
                    'display_name': instrument.replace('_', ' ').title(),
                    'available': True,
                    'sample_count': len(get_instrument_chords(instrument))
                })
            else:
                # Still suggest but mark as unavailable
                available_suggestions.append({
                    'name': instrument,
                    'display_name': instrument.replace('_', ' ').title(),
                    'available': False,
                    'sample_count': 0
                })
        
        # Also suggest other available instruments not already suggested
        for instrument in available_instruments:
            if instrument not in [s['name'] for s in available_suggestions] and instrument not in existing_instruments:
                available_suggestions.append({
                    'name': instrument,
                    'display_name': instrument.replace('_', ' ').title(),
                    'available': True,
                    'sample_count': len(get_instrument_chords(instrument))
                })
        
        return jsonify({
            'suggestions': available_suggestions[:5],  # Limit to top 5
            'reasoning': suggestions.get('reasoning', ''),
            'available_instruments': available_instruments,
            'total_available': len(available_instruments)
        })
        
    except Exception as e:
        current_app.logger.error(f"Instrument suggestion error: {str(e)}")
        return jsonify({'error': 'Failed to suggest instruments'}), 500


def get_available_sample_instruments():
    """
    Scan the public/samples directory to find available instruments
    """
    try:
        # Get the frontend public samples directory
        # Go up from backend/app/api/ to get to the root, then to frontend/public/samples
        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent.parent.parent
        samples_dir = project_root / 'frontend' / 'public' / 'samples'
        
        current_app.logger.info(f"Looking for samples in: {samples_dir}")
        
        if not samples_dir.exists():
            current_app.logger.warning(f"Samples directory not found: {samples_dir}")
            return []
        
        instruments = []
        for item in samples_dir.iterdir():
            if item.is_dir():
                instruments.append(item.name)
        
        current_app.logger.info(f"Found instruments: {instruments}")
        return instruments
        
    except Exception as e:
        current_app.logger.error(f"Error scanning sample instruments: {str(e)}")
        return []


def get_instrument_chords(instrument):
    """
    Get available chords/samples for a specific instrument
    """
    try:
        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent.parent.parent
        samples_dir = project_root / 'frontend' / 'public' / 'samples' / instrument
        
        current_app.logger.info(f"Looking for {instrument} chords in: {samples_dir}")
        
        if not samples_dir.exists():
            current_app.logger.warning(f"Instrument directory not found: {samples_dir}")
            return []
        
        chords = []
        
        # Look for duration subdirectories (like 1_0s)
        for duration_dir in samples_dir.iterdir():
            if duration_dir.is_dir():
                # Look for format subdirectories (wav, mp3, midi)
                wav_dir = duration_dir / 'wav'
                if wav_dir.exists():
                    for wav_file in wav_dir.iterdir():
                        if wav_file.is_file() and wav_file.suffix.lower() == '.wav':
                            # Extract chord name from filename (e.g., "C_major.wav" -> "C_major")
                            chord_name = wav_file.stem
                            if chord_name not in chords:
                                chords.append(chord_name)
        
        current_app.logger.info(f"Found {len(chords)} chords for {instrument}")
        return chords
        
    except Exception as e:
        current_app.logger.error(f"Error getting chords for {instrument}: {str(e)}")
        return []


@ai_bp.route('/samples/instruments', methods=['GET'])
@handle_errors
def get_sample_instruments():
    """
    Get list of available instruments from the sample library
    """
    instruments = get_available_sample_instruments()
    
    instruments_with_details = []
    for instrument in instruments:
        chords = get_instrument_chords(instrument)
        instruments_with_details.append({
            'name': instrument,
            'display_name': instrument.replace('_', ' ').title(),
            'chord_count': len(chords),
            'available_chords': chords[:10] if len(chords) > 10 else chords,  # Sample of chords
            'total_chords': len(chords)
        })
    
    return jsonify({
        'instruments': instruments_with_details,
        'total_instruments': len(instruments)
    })


@ai_bp.route('/samples/instruments/<instrument>/chords', methods=['GET'])
@handle_errors
def get_instrument_chord_list(instrument):
    """
    Get all available chords for a specific instrument
    """
    chords = get_instrument_chords(instrument)
    
    if not chords:
        return jsonify({'error': f'No chords found for instrument: {instrument}'}), 404
    
    # Organize chords by type
    chord_types = {
        'major': [],
        'minor': [],
        'dominant': [],
        'augmented': [],
        'diminished': [],
        'suspended': [],
        'other': []
    }
    
    for chord in chords:
        chord_lower = chord.lower()
        if '_major' in chord_lower:
            chord_types['major'].append(chord)
        elif '_minor' in chord_lower or '_min7' in chord_lower:
            chord_types['minor'].append(chord)
        elif '_dom7' in chord_lower:
            chord_types['dominant'].append(chord)
        elif '_augmented' in chord_lower:
            chord_types['augmented'].append(chord)
        elif '_diminished' in chord_lower:
            chord_types['diminished'].append(chord)
        elif '_sus' in chord_lower:
            chord_types['suspended'].append(chord)
        else:
            chord_types['other'].append(chord)
    
    return jsonify({
        'instrument': instrument,
        'chord_types': chord_types,
        'total_chords': len(chords),
        'all_chords': sorted(chords)
    })


@ai_bp.route('/samples/suggest-progression', methods=['POST'])
@handle_errors
def suggest_chord_progression_from_samples():
    """
    Suggest chord progressions using available samples for a specific instrument
    """
    data = request.get_json()
    instrument = data.get('instrument', 'guitar')
    genre = data.get('genre', 'pop')
    key = data.get('key', 'C')
    mood = data.get('mood', 'happy')
    
    # Get available chords for the instrument
    available_chords = get_instrument_chords(instrument)
    
    if not available_chords:
        return jsonify({'error': f'No samples found for instrument: {instrument}'}), 404
    
    # Filter chords by key if possible
    key_chords = [chord for chord in available_chords if chord.startswith(key + '_')]
    
    if not key_chords:
        # If no chords in the specified key, use all available chords
        key_chords = available_chords
    
    # Simple progression suggestions based on common patterns
    progressions = {
        'pop': ['major', 'minor', 'major', 'major'],
        'rock': ['major', 'major', 'minor', 'major'],
        'ballad': ['major', 'minor', 'minor', 'major'],
        'jazz': ['maj7', 'min7', 'dom7', 'maj7']
    }
    
    pattern = progressions.get(genre, progressions['pop'])
    suggested_chords = []
    
    for chord_type in pattern:
        # Find a chord that matches the type
        matching_chords = [c for c in key_chords if chord_type in c.lower()]
        if matching_chords:
            suggested_chords.append(matching_chords[0])
        elif key_chords:
            # Fallback to any available chord
            suggested_chords.append(key_chords[0])
    
    return jsonify({
        'instrument': instrument,
        'key': key,
        'genre': genre,
        'progression': suggested_chords,
        'available_chords': key_chords,
        'total_available': len(available_chords)
    })


@ai_bp.route('/models', methods=['GET'])
def get_available_models():
    """
    Get list of available AI models
    """
    return jsonify({
        'providers': {
            'anthropic': ['claude-sonnet-4', 'claude-3-opus', 'claude-3-haiku'],
            'openai': ['gpt-4o', 'gpt-4-turbo', 'gpt-3.5-turbo'],
            'google': ['gemini-1.5-pro', 'gemini-1.0-pro']
        },
        'default': {
            'provider': 'anthropic',
            'model': 'claude-sonnet-4'
        }
    })


@ai_bp.route('/status', methods=['GET'])
def ai_status():
    """
    Check AI service status and available providers
    """
    ai_service = AIService()
    status = ai_service.check_service_status()
    
    return jsonify({
        'status': 'online' if any(status.values()) else 'offline',
        'providers': status,
        'features': {
            'chat': True,
            'generation': True,
            'analysis': True
        }
    })


@ai_bp.route('/api-key-status', methods=['GET'])
@handle_errors
def get_api_key_status():
    """
    Check API key status for different AI providers
    """
    provider = request.args.get('provider', 'anthropic').lower()
    
    # Map providers to their environment variable names
    provider_env_vars = {
        'anthropic': 'ANTHROPIC_API_KEY',
        'openai': 'OPENAI_API_KEY',
        'google': 'GOOGLE_API_KEY'
    }
    
    if provider not in provider_env_vars:
        return jsonify({'error': 'Unsupported provider'}), 400
    
    env_var = provider_env_vars[provider]
    api_key = current_app.config.get(env_var) or os.getenv(env_var)
    
    # Check if API key exists and is not empty
    is_set = bool(api_key and api_key.strip())
    
    return jsonify({
        'provider': provider,
        'api_key_set': is_set,
        'env_var': env_var
    })


@ai_bp.route('/api-key-status/all', methods=['GET'])
@handle_errors
def get_all_api_key_status():
    """
    Check API key status for all AI providers
    """
    providers = ['anthropic', 'openai', 'google']
    status = {}
    
    for provider in providers:
        provider_env_vars = {
            'anthropic': 'ANTHROPIC_API_KEY',
            'openai': 'OPENAI_API_KEY',
            'google': 'GOOGLE_API_KEY'
        }
        
        env_var = provider_env_vars[provider]
        api_key = current_app.config.get(env_var) or os.getenv(env_var)
        is_set = bool(api_key and api_key.strip())
        
        status[provider] = {
            'api_key_set': is_set,
            'env_var': env_var
        }
    
    return jsonify(status)


@ai_bp.route('/samples/test', methods=['GET'])
@handle_errors
def test_sample_scanning():
    """
    Test endpoint to verify sample directory scanning works
    """
    try:
        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent.parent.parent
        samples_dir = project_root / 'frontend' / 'public' / 'samples'
        
        result = {
            'current_file': str(current_file),
            'project_root': str(project_root),
            'samples_dir': str(samples_dir),
            'samples_dir_exists': samples_dir.exists(),
            'instruments': [],
            'guitar_chords': []
        }
        
        if samples_dir.exists():
            result['instruments'] = [item.name for item in samples_dir.iterdir() if item.is_dir()]
            
            # Test guitar specifically
            guitar_dir = samples_dir / 'guitar' / '1_0s' / 'wav'
            if guitar_dir.exists():
                guitar_files = [f.stem for f in guitar_dir.iterdir() if f.suffix.lower() == '.wav']
                result['guitar_chords'] = guitar_files[:10]  # First 10 for testing
                result['total_guitar_chords'] = len(guitar_files)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e), 'traceback': str(e.__traceback__)})


@ai_bp.route('/generate/smart-progression', methods=['POST'])
@handle_errors
def generate_smart_chord_progression():
    """
    Generate chord progressions using both AI and available sample library
    """
    data = request.get_json()
    instrument = data.get('instrument', 'guitar')
    genre = data.get('genre', 'pop')
    key = data.get('key', 'C')
    mood = data.get('mood', 'happy')
    complexity = data.get('complexity', 'simple')
    num_chords = data.get('num_chords', 4)
    
    # Get available chords for the instrument
    available_chords = get_instrument_chords(instrument)
    
    if not available_chords:
        # Fallback to traditional AI generation if no samples available
        ai_service = AIService()
        try:
            progression = ai_service.generate_chord_progression(
                genre=genre,
                key=key,
                mood=mood,
                complexity=complexity
            )
            return jsonify({
                'progression': progression,
                'source': 'ai_generated',
                'available_samples': False,
                'metadata': {
                    'genre': genre,
                    'key': key,
                    'mood': mood,
                    'complexity': complexity,
                    'instrument': instrument
                }
            })
        except Exception as e:
            current_app.logger.error(f"Smart chord generation error: {str(e)}")
            return jsonify({'error': 'Failed to generate chord progression'}), 500
    
    # Filter chords by key
    key_chords = [chord for chord in available_chords if chord.startswith(key + '_')]
    
    if not key_chords:
        # Try finding chords in related keys or use all chords
        related_keys = get_related_keys(key)
        for related_key in related_keys:
            related_chords = [chord for chord in available_chords if chord.startswith(related_key + '_')]
            if related_chords:
                key_chords.extend(related_chords)
                break
        
        if not key_chords:
            key_chords = available_chords
    
    # Generate progression based on music theory and mood
    progression_patterns = get_progression_patterns(genre, mood, complexity)
    selected_pattern = progression_patterns[0] if progression_patterns else ['major', 'minor', 'major', 'major']
    
    suggested_progression = []
    used_chords = []
    
    for i in range(min(num_chords, len(selected_pattern))):
        chord_type = selected_pattern[i]
        
        # Find chords matching the type
        matching_chords = [c for c in key_chords if chord_type in c.lower() and c not in used_chords]
        
        if matching_chords:
            chord = matching_chords[0]
            suggested_progression.append({
                'chord': chord,
                'type': chord_type,
                'sample_path': f'/samples/{instrument}/1_0s/wav/{chord}.wav',
                'midi_path': f'/samples/{instrument}/1_0s/midi/{chord}.mid'
            })
            used_chords.append(chord)
        elif key_chords:
            # Fallback to any available chord
            fallback_chord = [c for c in key_chords if c not in used_chords]
            if fallback_chord:
                chord = fallback_chord[0]
                suggested_progression.append({
                    'chord': chord,
                    'type': 'fallback',
                    'sample_path': f'/samples/{instrument}/1_0s/wav/{chord}.wav',
                    'midi_path': f'/samples/{instrument}/1_0s/midi/{chord}.mid'
                })
                used_chords.append(chord)
    
    return jsonify({
        'progression': suggested_progression,
        'source': 'sample_based',
        'available_samples': True,
        'pattern_used': selected_pattern,
        'total_available_chords': len(available_chords),
        'key_specific_chords': len([c for c in available_chords if c.startswith(key + '_')]),
        'metadata': {
            'genre': genre,
            'key': key,
            'mood': mood,
            'complexity': complexity,
            'instrument': instrument,
            'num_chords': num_chords
        }
    })


def get_related_keys(key):
    """Get musically related keys for chord suggestions"""
    key_relationships = {
        'C': ['Am', 'F', 'G'],
        'G': ['Em', 'C', 'D'],
        'D': ['Bm', 'G', 'A'],
        'A': ['F#m', 'D', 'E'],
        'E': ['C#m', 'A', 'B'],
        'B': ['G#m', 'E', 'F#'],
        'F#': ['D#m', 'B', 'C#'],
        'F': ['Dm', 'Bb', 'C'],
        'Bb': ['Gm', 'Eb', 'F'],
        'Eb': ['Cm', 'Ab', 'Bb'],
        'Ab': ['Fm', 'Db', 'Eb'],
        'Db': ['Bbm', 'Gb', 'Ab']
    }
    
    return key_relationships.get(key, ['C', 'F', 'G'])


def get_progression_patterns(genre, mood, complexity):
    """Get chord progression patterns based on musical context"""
    patterns = {
        'pop': {
            'happy': {
                'simple': ['major', 'major', 'minor', 'major'],
                'complex': ['maj7', 'minor', 'dom7', 'major']
            },
            'sad': {
                'simple': ['minor', 'major', 'minor', 'minor'],
                'complex': ['min7', 'maj7', 'min7', 'dim']
            }
        },
        'rock': {
            'energetic': {
                'simple': ['major', 'major', 'major', 'minor'],
                'complex': ['major', 'dom7', 'minor', 'major']
            },
            'aggressive': {
                'simple': ['minor', 'minor', 'major', 'minor'],
                'complex': ['minor', 'dim', 'major', 'minor']
            }
        },
        'jazz': {
            'complex': ['maj7', 'min7', 'dom7', 'maj7'],
            'simple': ['major', 'minor', 'dom7', 'major']
        },
        'blues': {
            'simple': ['dom7', 'dom7', 'dom7', 'dom7'],
            'complex': ['dom7', 'min7', 'dom7', 'dim']
        }
    }
    
    genre_patterns = patterns.get(genre.lower(), patterns['pop'])
    
    if isinstance(genre_patterns, dict):
        mood_patterns = genre_patterns.get(mood.lower(), list(genre_patterns.values())[0])
        if isinstance(mood_patterns, dict):
            return [mood_patterns.get(complexity.lower(), mood_patterns.get('simple', ['major', 'minor', 'major', 'major']))]
        else:
            return [mood_patterns]
    else:
        return [genre_patterns]
