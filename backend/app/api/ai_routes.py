"""
AI Service API Routes
Handles chat, music generation, and AI-powered composition features
"""

from flask import Blueprint, request, jsonify, current_app, Response
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.services.ai_service import AIService
# Temporarily disable LangChain service due to pydantic compatibility issues
# from app.services.langchain_service import LangChainService
from app.models.song_structure import SongStructure
from app.utils.decorators import handle_errors
import json
import os
import time
import asyncio
import logging
from pathlib import Path
from datetime import datetime

ai_bp = Blueprint('ai', __name__)


@ai_bp.route('/chat', methods=['POST'])
@handle_errors
def chat():
    """
    Handle AI chat interactions with enhanced music assistance
    """
    data = request.get_json()
    message = data.get('message', '')
    provider = data.get('provider', 'anthropic')
    model = data.get('model', 'claude-sonnet-4')
    context = data.get('context', {})
    
    if not message:
        return jsonify({'error': 'Message is required'}), 400
    
    # Enhance context with available instruments
    try:
        available_instruments = get_all_available_instruments()
        context['available_instruments'] = available_instruments
        current_app.logger.info(f"Added {len(available_instruments)} available instruments to AI context")
    except Exception as e:
        current_app.logger.warning(f"Could not load available instruments for AI context: {str(e)}")
        context['available_instruments'] = []

    ai_service = AIService()

    try:
        response = ai_service.chat_completion(
            message=message,
            provider=provider,
            model=model,
            context=context
        )

        # Build enhanced response with LangChain fields if available
        result = {
            'response': response['content'],
            'provider': provider,
            'model': model,
            'actions': response.get('actions', []),
            'timestamp': response.get('timestamp'),
            'success': response.get('success', True)
        }

        # Include LangChain-specific fields if present
        if 'updated_song_structure' in response:
            result['updated_song_structure'] = response['updated_song_structure']
        
        if 'tools_used' in response:
            result['tools_used'] = response['tools_used']
        
        return jsonify(result)
        
    except Exception as e:
        current_app.logger.error(f"AI Chat error: {str(e)}")
        return jsonify({
            'error': 'AI service temporarily unavailable',
            'success': False,
            'fallback_response': 'I apologize, but I\'m having trouble connecting to the AI service right now. Please try again in a moment.'
        }), 503


@ai_bp.route('/chat-with-scores', methods=['POST'])
@handle_errors
def chat_with_scores():
    """
    Handle AI chat interactions with musical score sheet attachments
    """
    data = request.get_json()
    message = data.get('message', '')
    provider = data.get('provider', 'anthropic')
    model = data.get('model', 'claude-sonnet-4')
    context = data.get('context', {})
    score_file_ids = data.get('score_file_ids', [])  # List of uploaded score file IDs
    
    if not message:
        return jsonify({'error': 'Message is required'}), 400
    
    # Enhance context with available instruments
    try:
        available_instruments = get_all_available_instruments()
        context['available_instruments'] = available_instruments
        current_app.logger.info(f"Added {len(available_instruments)} available instruments to AI context")
    except Exception as e:
        current_app.logger.warning(f"Could not load available instruments for AI context: {str(e)}")
        context['available_instruments'] = []
    
    # Add score sheet analysis to context if provided
    if score_file_ids:
        try:
            from app.services.score_service import ScoreService
            score_service = ScoreService()
            
            score_analyses = []
            for file_id in score_file_ids:
                analysis = score_service.get_score_analysis(file_id)
                if analysis:
                    score_analyses.append({
                        'file_id': file_id,
                        'filename': analysis.get('original_filename', 'Unknown'),
                        'category': analysis.get('category', 'unknown'),
                        'analysis': analysis.get('analysis', {})
                    })
            
            if score_analyses:
                context['uploaded_scores'] = score_analyses
                current_app.logger.info(f"Added {len(score_analyses)} score analyses to AI context")
        
        except Exception as e:
            current_app.logger.warning(f"Could not load score analyses for AI context: {str(e)}")
    
    ai_service = AIService()
    
    try:
        response = ai_service.chat_completion(
            message=message,
            provider=provider,
            model=model,
            context=context
        )
        
        # Build enhanced response
        result = {
            'response': response['content'],
            'provider': provider,
            'model': model,
            'actions': response.get('actions', []),
            'timestamp': response.get('timestamp'),
            'success': response.get('success', True),
            'score_files_processed': len(score_file_ids)
        }
        
        # Include additional fields if present
        if 'updated_song_structure' in response:
            result['updated_song_structure'] = response['updated_song_structure']
        
        if 'tools_used' in response:
            result['tools_used'] = response['tools_used']
        
        return jsonify(result)
        
    except Exception as e:
        current_app.logger.error(f"AI Chat with scores error: {str(e)}")
        return jsonify({
            'error': 'AI service temporarily unavailable',
            'success': False,
            'fallback_response': 'I apologize, but I\'m having trouble processing your request with the score sheets right now. Please try again in a moment.'
        }), 503


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
    available_instruments = get_all_available_instruments()
    
    ai_service = AIService()
    
    try:
        # Get AI suggestions
        suggestions = ai_service.suggest_instruments(
            genre=genre,
            existing_instruments=existing_instruments,
            mood=mood,
            tempo=tempo,
            available_instruments=available_instruments
        )
        
        # Filter suggestions to only include instruments we have samples for
        available_suggestions = []
        available_instrument_names = [inst['name'] for inst in available_instruments]
        
        for instrument in suggestions.get('suggestions', []):
            # Check if this instrument is available in any category
            matching_instruments = [inst for inst in available_instruments if inst['name'] == instrument]
            
            if matching_instruments:
                # Use the first matching instrument
                match = matching_instruments[0]
                chords = get_instrument_chords(match['category'], match['name'])
                available_suggestions.append({
                    'name': match['name'],
                    'category': match['category'],
                    'display_name': match['display_name'],
                    'available': True,
                    'sample_count': len(chords)
                })
            else:
                # Still suggest but mark as unavailable
                available_suggestions.append({
                    'name': instrument,
                    'category': 'unknown',
                    'display_name': instrument.replace('_', ' ').title(),
                    'available': False,
                    'sample_count': 0
                })
        
        # Also suggest other available instruments not already suggested
        for instrument in available_instruments:
            if instrument['name'] not in [s['name'] for s in available_suggestions] and instrument['name'] not in existing_instruments:
                chords = get_instrument_chords(instrument['category'], instrument['name'])
                available_suggestions.append({
                    'name': instrument['name'],
                    'category': instrument['category'],
                    'display_name': instrument['display_name'],
                    'available': True,
                    'sample_count': len(chords)
                })
        
        return jsonify({
            'suggestions': available_suggestions[:5],  # Limit to top 5
            'reasoning': suggestions.get('reasoning', ''),
            'available_instruments': available_instrument_names,
            'total_available': len(available_instruments)
        })
        
    except Exception as e:
        current_app.logger.error(f"Instrument suggestion error: {str(e)}")
        return jsonify({'error': 'Failed to suggest instruments'}), 500


def get_available_sample_instruments(category):
    """
    Scan the public/instruments/[category] directory to find available instruments
    """
    try:
        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent.parent.parent
        instruments_dir = project_root / 'frontend' / 'public' / 'instruments' / category
        current_app.logger.info(f"Looking for instruments in: {instruments_dir}")
        if not instruments_dir.exists():
            current_app.logger.warning(f"Samples directory not found: {instruments_dir}")
            return []
        instruments = []
        for item in instruments_dir.iterdir():
            if item.is_dir():
                instruments.append(item.name)
        current_app.logger.info(f"Found instruments: {instruments}")
        return instruments
    except Exception as e:
        current_app.logger.error(f"Error scanning sample instruments: {str(e)}")
        return []


def get_instrument_chords(category, instrument):
    """
    Get available chords/samples for a specific instrument in a category
    """
    try:
        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent.parent.parent
        instruments_dir = project_root / 'frontend' / 'public' / 'instruments' / category / instrument
        current_app.logger.info(f"Looking for {instrument} chords in: {instruments_dir}")
        
        if not instruments_dir.exists():
            current_app.logger.warning(f"Instrument directory not found: {instruments_dir}")
            return []
        
        chords = []

        # Check for format directories directly in the instrument folder (newer structure)
        format_dirs = ['mp3', 'wav', 'midi']
        for format_name in format_dirs:
            format_dir = instruments_dir / format_name
            if format_dir.exists():
                for audio_file in format_dir.iterdir():
                    if audio_file.is_file() and audio_file.suffix.lower() in ['.mp3', '.wav']:
                        # Extract chord name from filename (e.g., "C_major.mp3" -> "C_major")
                        chord_name = audio_file.stem
                        if chord_name not in chords:
                            chords.append(chord_name)

        # Also check for duration subdirectories (older structure)
        for duration_dir in instruments_dir.iterdir():
            if duration_dir.is_dir() and duration_dir.name not in format_dirs:
                # Check multiple format directories in order of preference
                for format_name in format_dirs:
                    format_dir = duration_dir / format_name
                    if format_dir.exists():
                        for audio_file in format_dir.iterdir():
                            if audio_file.is_file() and audio_file.suffix.lower() in ['.mp3', '.wav']:
                                # Extract chord name from filename (e.g., "C_major.mp3" -> "C_major")
                                chord_name = audio_file.stem
                                if chord_name not in chords:
                                    chords.append(chord_name)

        current_app.logger.info(f"Found {len(chords)} chords for {instrument}")
        return chords

    except Exception as e:
        current_app.logger.error(f"Error getting chords for {instrument} in {category}: {str(e)}")
        return []


@ai_bp.route('/samples/instruments', methods=['GET'])
@handle_errors
def get_sample_instruments():
    """
    Get list of available instruments from the sample library
    """
    instruments = get_all_available_instruments()
    
    instruments_with_details = []
    for instrument in instruments:
        chords = get_instrument_chords(instrument['category'], instrument['name'])
        instruments_with_details.append({
            'name': instrument['name'],
            'category': instrument['category'],
            'display_name': instrument['display_name'],
            'chord_count': len(chords),
            'available_chords': chords[:10] if len(chords) > 10 else chords,  # Sample of chords
            'total_chords': len(chords)
        })
    
    return jsonify({
        'instruments': instruments_with_details,
        'total_instruments': len(instruments)
    })


@ai_bp.route('/samples/instruments/<category>', methods=['GET'])
@handle_errors
def get_sample_instruments_by_category(category):
    """
    Get list of available instruments from the sample library for a given category
    """
    instruments = get_available_sample_instruments(category)
    
    instruments_with_details = []
    for instrument in instruments:
        chords = get_instrument_chords(category, instrument)
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


@ai_bp.route('/samples/instruments/<category>/<instrument>/chords', methods=['GET'])
@handle_errors
def get_instrument_chord_list(category, instrument):
    """
    Get all available chords for a specific instrument in a category
    """
    chords = get_instrument_chords(category, instrument)
    
    if not chords:
        return jsonify({'error': f'No chords found for instrument: {instrument} in category: {category}'}), 404
    
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
    category = data.get('category')
    instrument = data.get('instrument', 'guitar')
    genre = data.get('genre', 'pop')
    key = data.get('key', 'C')
    mood = data.get('mood', 'happy')

    if not category:
        return jsonify({'error': 'Missing required parameter: category'}), 400

    # Get available chords for the instrument in the category
    available_chords = get_instrument_chords(category, instrument)

    if not available_chords:
        return jsonify({'error': f'No samples found for instrument: {instrument} in category: {category}'}), 404

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
            chord = matching_chords[0]
            suggested_chords.append({
                'chord': chord,
                'type': chord_type,
                'sample_path': f'/samples/instruments/{category}/{instrument}/1_0s/wav/{chord}.wav',
                'midi_path': f'/samples/instruments/{category}/{instrument}/1_0s/midi/{chord}.mid'
            })
        elif key_chords:
            # Fallback to any available chord
            chord = key_chords[0]
            suggested_chords.append({
                'chord': chord,
                'type': 'fallback',
                'sample_path': f'/samples/instruments/{category}/{instrument}/1_0s/wav/{chord}.wav',
                'midi_path': f'/samples/instruments/{category}/{instrument}/1_0s/midi/{chord}.mid'
            })
    return jsonify({
        'instrument': instrument,
        'category': category,
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
            'anthropic': [
                'claude-4-sonnet',
                'claude-3-7-sonnet',
                'claude-3-5-sonnet-20241022',
                'claude-3-5-sonnet-20240620',
                'claude-3-5-haiku-20241022',
                'claude-3-opus-20240229',
                'claude-3-sonnet-20240229',
                'claude-3-haiku-20240307',
                'claude-2.1',
                'claude-2.0',
                'claude-instant-1.2'
            ],
            'openai': [
                'gpt-4o',
                'gpt-4o-mini',
                'gpt-4-turbo',
                'gpt-4-turbo-preview',
                'gpt-4-0125-preview',
                'gpt-4-1106-preview',
                'gpt-4',
                'gpt-4-0613',
                'gpt-3.5-turbo',
                'gpt-3.5-turbo-0125',
                'gpt-3.5-turbo-1106',
                'gpt-3.5-turbo-16k',
                'gpt-3.5-turbo-instruct'
            ],
            'google': [
                'gemini-1.5-pro',
                'gemini-1.5-pro-latest',
                'gemini-1.5-flash',
                'gemini-1.5-flash-latest',
                'gemini-1.0-pro',
                'gemini-1.0-pro-latest',
                'gemini-1.0-pro-vision',
                'gemini-pro',
                'gemini-pro-vision'
            ],
            'mistral': [
                'mistral-large-latest',
                'mistral-large-2407',
                'mistral-large-2402',
                'mistral-medium-latest',
                'mistral-medium-2312',
                'mistral-small-latest',
                'mistral-small-2402',
                'mistral-small-2312',
                'mistral-tiny',
                'mistral-7b-instruct',
                'mixtral-8x7b-instruct',
                'mixtral-8x22b-instruct',
                'open-mistral-7b',
                'open-mistral-8x7b',
                'open-mistral-8x22b',
                'open-mixtral-8x7b',
                'open-mixtral-8x22b'
            ],
            'xai': [
                'grok-beta',
                'grok-2-1212',
                'grok-2-latest',
                'grok-2-public',
                'grok-2-mini',
                'grok-vision-beta',
                'grok-1',
                'grok-1.5'
            ]
        },
        'default': {
            'provider': 'anthropic',
            'model': 'claude-4-sonnet'
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
        'google': 'GOOGLE_API_KEY',
        'mistral': 'MISTRAL_API_KEY',
        'xai': 'XAI_API_KEY'
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
    category = data.get('category')
    instrument = data.get('instrument', 'guitar')
    genre = data.get('genre', 'pop')
    key = data.get('key', 'C')
    mood = data.get('mood', 'happy')
    complexity = data.get('complexity', 'simple')
    num_chords = data.get('num_chords', 4)

    if not category:
        return jsonify({'error': 'Missing required parameter: category'}), 400

    # Get available chords for the instrument in the category
    available_chords = get_instrument_chords(category, instrument)

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
                    'instrument': instrument,
                    'category': category
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
                'sample_path': f'/samples/instruments/{category}/{instrument}/1_0s/wav/{chord}.wav',
                'midi_path': f'/samples/instruments/{category}/{instrument}/1_0s/midi/{chord}.mid'
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
                    'sample_path': f'/samples/instruments/{category}/{instrument}/1_0s/wav/{chord}.wav',
                    'midi_path': f'/samples/instruments/{category}/{instrument}/1_0s/midi/{chord}.mid'
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
            'category': category,
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


@ai_bp.route('/samples/instruments/all', methods=['GET'])
@handle_errors
def get_all_sample_instruments():
    """
    Get all instruments grouped by category for the instrument selection dialog
    """
    try:
        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent.parent.parent
        # FIX: Use correct path
        instruments_root = project_root / 'frontend' / 'public' / 'instruments'
        result = {}
        if instruments_root.exists():
            for category_dir in instruments_root.iterdir():
                if category_dir.is_dir():
                    category = category_dir.name
                    instruments = []
                    for item in category_dir.iterdir():
                        if item.is_dir():
                            chords = get_instrument_chords(category, item.name)
                            instruments.append({
                                'name': item.name,
                                'display_name': item.name.replace('_', ' ').title(),
                                'category': category,
                                'chord_count': len(chords),
                                'available_chords': chords[:10] if len(chords) > 10 else chords,
                                'total_chords': len(chords)
                            })
                    result[category] = instruments
        return jsonify({'categories': result})
    except Exception as e:
        current_app.logger.error(f"Error getting all sample instruments: {str(e)}")
        return jsonify({'error': 'Failed to get all sample instruments'}), 500


@ai_bp.route('/music-assistant', methods=['POST'])
@handle_errors
def music_assistant():
    """
    Advanced AI Music Assistant using LangChain React Agent
    Provides intelligent assistance for music composition and song structure modification
    """
    data = request.get_json()
    message = data.get('message', '')
    provider = data.get('provider', 'anthropic')
    model = data.get('model', 'claude-sonnet-4')
    song_structure_data = data.get('song_structure', {})
    
    if not message:
        return jsonify({'error': 'Message is required'}), 400
    
    # Validate and parse song structure if provided
    song_structure = None
    validation_errors = []
    
    if song_structure_data:
        try:
            # Try to create SongStructure object for validation
            song_structure = SongStructure.from_dict(song_structure_data)
            validation_errors = song_structure.validate()
            
            if validation_errors:
                current_app.logger.warning(f"Song structure validation warnings: {validation_errors}")
            
        except Exception as e:
            current_app.logger.warning(f"Song structure parsing failed, using raw data: {e}")
            # Use raw data if parsing fails
            song_structure = song_structure_data
    
    # Initialize LangChain service with React Agent
    langchain_service = LangChainService()
    
    try:
        # Use the React Agent to process the request
        response = langchain_service.chat_with_music_assistant(
            message=message,
            song_structure=song_structure.to_dict() if hasattr(song_structure, 'to_dict') else song_structure_data,
            provider=provider
        )
        
        # Validate updated song structure if returned
        updated_structure = response.get('updated_song_structure')
        if updated_structure:
            try:
                validated_structure = SongStructure.from_dict(updated_structure)
                structure_validation_errors = validated_structure.validate()
                if structure_validation_errors:
                    current_app.logger.warning(f"Updated structure validation warnings: {structure_validation_errors}")
                response['updated_song_structure'] = validated_structure.to_dict()
            except Exception as e:
                current_app.logger.warning(f"Updated structure validation failed: {e}")
        
        result = {
            'response': response['response'],
            'updated_song_structure': response.get('updated_song_structure'),
            'provider': provider,
            'model': model,
            'success': response['success'],
            'tools_used': response.get('tools_used', []),
            'timestamp': datetime.now().isoformat()
        }
        
        # Include validation warnings if any
        if validation_errors:
            result['validation_warnings'] = validation_errors
            
        return jsonify(result)
        
    except Exception as e:
        current_app.logger.error(f"Music Assistant error: {str(e)}")
        return jsonify({
            'error': 'Music assistant temporarily unavailable',
            'fallback_response': 'I can help you with music composition. Please try again or use the basic chat function.',
            'success': False
        }), 503


@ai_bp.route('/analyze-song', methods=['POST'])
@handle_errors
def analyze_song_advanced():
    """
    Advanced song analysis using LangChain React Agent with new song structure validation
    """
    data = request.get_json()
    song_structure_data = data.get('song_structure', {})
    
    if not song_structure_data:
        return jsonify({'error': 'Song structure is required'}), 400
    
    # Validate and parse song structure
    try:
        song_structure = SongStructure.from_dict(song_structure_data)
        validation_errors = song_structure.validate()
        
        if validation_errors:
            current_app.logger.warning(f"Song structure validation issues: {validation_errors}")
            
        # Specific validation for lyrics & vocals
        lyrics_track = song_structure.get_lyrics_track()
        lyrics_validation_errors = []
        
        if lyrics_track:
            for clip in lyrics_track.clips:
                if clip.is_lyrics_clip():
                    if not clip.validate_lyrics_structure():
                        lyrics_validation_errors.append(f"Clip {clip.id} has invalid lyrics structure")
                    elif clip.has_multi_voice():
                        # Validate multi-voice structure
                        for voice in clip.voices:
                            if not voice.lyrics:
                                lyrics_validation_errors.append(f"Voice {voice.voice_id} in clip {clip.id} has no lyrics fragments")
                            for fragment in voice.lyrics:
                                if not fragment.text or not fragment.notes:
                                    lyrics_validation_errors.append(f"Invalid lyrics fragment in voice {voice.voice_id}")
        
    except Exception as e:
        current_app.logger.error(f"Song structure parsing failed: {e}")
        return jsonify({'error': 'Invalid song structure format'}), 400
    
    langchain_service = LangChainService()
    
    try:
        # Use React Agent for analysis with validated structure
        analysis_message = "Please analyze this song structure and provide detailed feedback with suggestions for improvement."
        
        response = langchain_service.chat_with_music_assistant(
            message=analysis_message,
            song_structure=song_structure.to_dict(),
            provider=data.get('provider', 'anthropic')
        )
        
        result = {
            'analysis': response['response'],
            'suggestions': response.get('updated_song_structure', {}),
            'success': response['success'],
            'tools_used': response.get('tools_used', [])
        }
        
        # Include validation results
        if validation_errors or lyrics_validation_errors:
            result['validation_issues'] = {
                'general': validation_errors,
                'lyrics_vocals': lyrics_validation_errors
            }
        
        return jsonify(result)
        
    except Exception as e:
        current_app.logger.error(f"Advanced song analysis error: {str(e)}")
        return jsonify({'error': 'Failed to analyze song with advanced AI'}), 500


@ai_bp.route('/generate-section', methods=['POST'])
@handle_errors
def generate_song_section():
    """
    Generate a complete song section using React Agent
    """
    data = request.get_json()
    song_structure = data.get('song_structure', {})
    section_name = data.get('section_name', 'verse')
    section_requirements = data.get('requirements', {})
    
    langchain_service = LangChainService()
    
    try:
        # Create message for section generation
        requirements_text = ", ".join([f"{k}: {v}" for k, v in section_requirements.items()])
        message = f"Please add a {section_name} section to this song with the following requirements: {requirements_text}"
        
        response = langchain_service.chat_with_music_assistant(
            message=message,
            song_structure=song_structure
        )
        
        return jsonify({
            'response': response['response'],
            'updated_song_structure': response.get('updated_song_structure'),
            'section_name': section_name,
            'success': response['success']
        })
        
    except Exception as e:
        current_app.logger.error(f"Section generation error: {str(e)}")
        return jsonify({'error': 'Failed to generate song section'}), 500


@ai_bp.route('/suggest-modifications', methods=['POST'])
@handle_errors
def suggest_modifications():
    """
    Get AI suggestions for song modifications using React Agent
    """
    data = request.get_json()
    song_structure = data.get('song_structure', {})
    user_goal = data.get('goal', 'improve the song')
    
    langchain_service = LangChainService()
    
    try:
        message = f"Please analyze this song and suggest modifications to {user_goal}. Provide specific actionable suggestions."
        
        response = langchain_service.chat_with_music_assistant(
            message=message,
            song_structure=song_structure
        )
        
        return jsonify({
            'suggestions': response['response'],
            'suggested_structure': response.get('updated_song_structure'),
            'success': response['success']
        })
        
    except Exception as e:
        current_app.logger.error(f"Modification suggestion error: {str(e)}")
        return jsonify({'error': 'Failed to generate modification suggestions'}), 500


@ai_bp.route('/available-tools', methods=['GET'])
@handle_errors
def get_available_tools():
    """
    Get list of available tools that the AI assistant can use
    """
    try:
        tools_info = [
            {
                'name': 'analyze_song_structure',
                'description': 'Analyze current song structure and provide insights',
                'parameters': ['song_json']
            },
            {
                'name': 'get_available_instruments', 
                'description': 'Get list of available instruments from sample library',
                'parameters': []
            },
            {
                'name': 'get_available_samples',
                'description': 'Get available samples for instruments', 
                'parameters': ['category', 'instrument']
            },
            {
                'name': 'create_track',
                'description': 'Add a new track to the song',
                'parameters': ['song_json', 'track_name', 'instrument', 'category']
            },
            {
                'name': 'add_clip_to_track',
                'description': 'Add a clip to a specific track',
                'parameters': ['song_json', 'track_id', 'start_time', 'duration', 'clip_type', 'notes', 'sample_url']
            },
            {
                'name': 'generate_chord_progression',
                'description': 'Generate chord progressions for given key and style',
                'parameters': ['key', 'style', 'num_bars']
            },
            {
                'name': 'create_song_section',
                'description': 'Create complete song sections with multiple tracks',
                'parameters': ['song_json', 'section_name', 'start_time', 'duration', 'chord_progression', 'instruments']
            },
            {
                'name': 'modify_song_structure',
                'description': 'Apply structural modifications based on natural language',
                'parameters': ['song_json', 'modifications']
            }
        ]
        
        return jsonify({
            'tools': tools_info,
            'total_tools': len(tools_info),
            'agent_type': 'React Agent',
            'description': 'LangChain React Agent with music composition tools'
        })
        
    except Exception as e:
        current_app.logger.error(f"Error getting available tools: {str(e)}")
        return jsonify({'error': 'Failed to get available tools'}), 500


def get_sample_path(category, instrument, chord, format_type='wav'):
    """
    Get the correct sample path for an instrument chord, handling both directory structures
    """
    try:
        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent.parent.parent
        instruments_dir = project_root / 'frontend' / 'public' / 'instruments' / category / instrument
        
        # Check if format directory exists directly under instrument
        format_dir = instruments_dir / format_type
        if format_dir.exists():
            chord_file = format_dir / f"{chord}.{format_type}"
            if chord_file.exists():
                return f'/instruments/{category}/{instrument}/{format_type}/{chord}.{format_type}'
        
        # Check for duration subdirectories
        for duration_dir in instruments_dir.iterdir():
            if duration_dir.is_dir() and duration_dir.name not in ['mp3', 'wav', 'midi']:
                format_dir = duration_dir / format_type
                if format_dir.exists():
                    chord_file = format_dir / f"{chord}.{format_type}"
                    if chord_file.exists():
                        return f'/instruments/{category}/{instrument}/{duration_dir.name}/{format_type}/{chord}.{format_type}'
        
        # Fallback to the old structure assumption
        return f'/instruments/{category}/{instrument}/1_0s/{format_type}/{chord}.{format_type}'
    
    except Exception as e:
        current_app.logger.error(f"Error getting sample path for {instrument} {chord}: {str(e)}")
        return f'/instruments/{category}/{instrument}/1_0s/{format_type}/{chord}.{format_type}'


def get_all_available_instruments():
    """
    Get all available instruments from all categories in the sample library
    """
    try:
        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent.parent.parent
        instruments_root = project_root / 'frontend' / 'public' / 'instruments'
        
        if not instruments_root.exists():
            current_app.logger.warning(f"Instruments directory not found: {instruments_root}")
            return []
        
        all_instruments = []
        for category_dir in instruments_root.iterdir():
            if category_dir.is_dir():
                category = category_dir.name
                instruments = get_available_sample_instruments(category)
                for instrument in instruments:
                    all_instruments.append({
                        'name': instrument,
                        'category': category,
                        'full_name': f"{category}/{instrument}",
                        'display_name': instrument.replace('_', ' ').title()
                    })
        
        current_app.logger.info(f"Found {len(all_instruments)} instruments across all categories")
        return all_instruments
    
    except Exception as e:
        current_app.logger.error(f"Error getting all available instruments: {str(e)}")
        return []


@ai_bp.route('/generate/image', methods=['POST'])
@handle_errors
def generate_image():
    """
    Generate AI album cover images
    """
    try:
        data = request.get_json()
        prompt = data.get('prompt', '')
        provider = data.get('provider', 'openai')
        size = data.get('size', '1024x1024')
        quality = data.get('quality', 'standard')
        style = data.get('style', 'vivid')
        
        if not prompt:
            return jsonify({'error': 'Prompt is required'}), 400
        
        # Initialize AI service
        ai_service = AIService()
        
        # Check if OpenAI is available for image generation
        if provider == 'openai' and not ai_service.openai_client:
            return jsonify({'error': 'OpenAI API not configured'}), 400
        
        # Generate image using simplified approach
        if provider == 'openai' and ai_service.openai_client:
            try:
                # Enhance prompt for album cover context
                enhanced_prompt = f"Album cover art: {prompt}. Professional music album cover design, high quality, artistic, suitable for music streaming platforms."
                
                response = ai_service.openai_client.images.generate(
                    model="dall-e-3",
                    prompt=enhanced_prompt,
                    size=size,
                    quality=quality,
                    style=style,
                    n=1
                )
                
                image_url = response.data[0].url
                revised_prompt = getattr(response.data[0], 'revised_prompt', enhanced_prompt)
                
                return jsonify({
                    'success': True,
                    'image_url': image_url,
                    'revised_prompt': revised_prompt,
                    'original_prompt': prompt,
                    'provider': provider,
                    'model': 'dall-e-3',
                    'size': size,
                    'quality': quality,
                    'style': style,
                    'timestamp': datetime.utcnow().isoformat()
                })
                
            except Exception as e:
                current_app.logger.error(f"OpenAI image generation error: {str(e)}")
                return jsonify({'error': f'Image generation failed: {str(e)}'}), 500
        
        return jsonify({'error': 'Image generation provider not available'}), 400
        
    except Exception as e:
        current_app.logger.error(f"Image generation error: {str(e)}")
        return jsonify({'error': 'Failed to generate image'}), 500


@ai_bp.route('/generate/song-langgraph-stream', methods=['POST'])
@handle_errors
def generate_song_langgraph_stream():
    """
    Generate a complete song structure using LangGraph multi-agent system with SSE streaming
    """
    from concurrent.futures import ThreadPoolExecutor
    
    data = request.get_json()
    current_app.logger.info("Received LangGraph streaming song generation request")
    
    def generate():
        try:
            # Build request data from frontend payload
            request_data = {
                'song_idea': data.get('songIdea', ''),
                'style_tags': data.get('selectedStyles', []),
                'custom_style': data.get('customStyle', ''),
                'lyrics_option': data.get('lyricsOption', 'automatically'),
                'custom_lyrics': data.get('customLyrics', ''),
                'is_instrumental': data.get('isInstrumental', False),
                'duration': data.get('duration', ''),
                'song_key': data.get('songKey', ''),
                'selected_provider': data.get('selected_provider', 'anthropic'),
                'selected_model': data.get('selected_model', 'claude-4-sonnet')
            }
            
            # Debug: Log the provider selection from frontend
            print(f"🔍 FRONTEND PROVIDER DATA:")
            print(f"   - Raw data.get('selected_provider'): {data.get('selected_provider')}")
            print(f"   - Raw data.get('selected_model'): {data.get('selected_model')}")
            print(f"   - Final request_data selected_provider: {request_data['selected_provider']}")
            print(f"   - Final request_data selected_model: {request_data['selected_model']}")
            
            # Send initial status
            yield f"data: {json.dumps({'type': 'status', 'message': 'Initializing song generation...', 'progress': 0})}\n\n"
            time.sleep(0.1)
            
            try:
                # Import and setup LangGraph generator
                from app.services.langgraph_song_generator import LangGraphSongGenerator, ensure_global_llms_initialized, SongGenerationRequest
                
                # Ensure global LLMs are initialized
                yield f"data: {json.dumps({'type': 'status', 'message': 'Setting up AI models...', 'progress': 5})}\n\n"
                ensure_global_llms_initialized()
                
                # Get API keys
                openai_api_key = os.getenv('OPENAI_API_KEY')
                anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')
                
                if not openai_api_key:
                    yield f"data: {json.dumps({'type': 'error', 'error': 'OpenAI API key not configured'})}\n\n"
                    return
                
                # Create generator
                generator = LangGraphSongGenerator(
                    openai_api_key=openai_api_key,
                    anthropic_api_key=anthropic_api_key,
                    provider=request_data['selected_provider'],
                    model=request_data['selected_model']
                )
                
                # Build request object
                style_tags = request_data.get("style_tags", [])
                song_idea = request_data.get("song_idea", "")
                mood = ""
                if style_tags:
                    mood = ", ".join(style_tags)
                if song_idea and mood:
                    mood = f"{mood} (inspired by: {song_idea})"
                elif song_idea:
                    mood = song_idea
                
                request_obj = SongGenerationRequest(
                    song_idea=song_idea,
                    style_tags=style_tags,
                    custom_style=request_data.get("custom_style", ""),
                    lyrics_option=request_data.get("lyrics_option", "automatically"),
                    custom_lyrics=request_data.get("custom_lyrics", ""),
                    is_instrumental=request_data.get("is_instrumental", False),
                    duration=request_data.get("duration", ""),
                    song_key=request_data.get("song_key", ""),
                    selected_provider=request_data.get("selected_provider", "anthropic"),  # Default to anthropic to match frontend
                    selected_model=request_data.get("selected_model", "claude-4-sonnet"),  # Default to claude-4-sonnet to match frontend
                    mood=mood
                )
                
                # Initialize progress queue for cross-thread communication
                progress_queue = []
                
                # Progress callback that adds to queue
                def progress_callback(message, progress, agent=None, restart_reason=None, restart_attempt=None, **kwargs):
                    try:
                        progress_data = {
                            'type': 'progress',
                            'message': message,
                            'progress': progress,
                            'agent': agent
                        }
                        
                        # Add restart information if provided
                        if restart_reason:
                            progress_data['restart_reason'] = restart_reason
                        if restart_attempt:
                            progress_data['restart_attempt'] = restart_attempt
                        
                        # Handle user approval workflow data
                        if 'decision_data' in kwargs:
                            progress_data['type'] = 'user_decision_required'
                            progress_data['decision_data'] = kwargs['decision_data']
                            progress_data['user_interaction_required'] = kwargs.get('user_interaction_required', False)
                            progress_data['qa_feedback_summary'] = kwargs.get('qa_feedback_summary', {})
                        
                        # Add any other kwargs that might be useful
                        for key, value in kwargs.items():
                            if key not in ['decision_data', 'user_interaction_required', 'qa_feedback_summary']:
                                progress_data[key] = value
                            
                        progress_queue.append(f"data: {json.dumps(progress_data)}\n\n")
                    except Exception as e:
                        # Use print instead of current_app.logger to avoid application context issues
                        print(f"Progress callback error: {e}")
                
                # Start the generation with streaming progress
                yield f"data: {json.dumps({'type': 'status', 'message': 'Starting multi-agent workflow...', 'progress': 10})}\n\n"
                
                def run_generation():
                    """Run the async generation in a separate thread"""
                    try:
                        # Run without Flask context to avoid "Working outside of application context" errors
                        # Create new event loop for this thread
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        
                        print(f"DEBUG: Thread starting song generation...")
                        print(f"DEBUG: Generator type: {type(generator)}")
                        print(f"DEBUG: Generator has generate_song: {hasattr(generator, 'generate_song')}")
                        print(f"DEBUG: Request object: {request_obj}")
                        
                        # Run the generator
                        result = loop.run_until_complete(generator.generate_song(request_obj, progress_callback))
                        print(f"DEBUG: Generation completed successfully")
                        return result
                    except Exception as e:
                        # Use print instead of current_app.logger to avoid application context issues
                        print(f"Generation thread error: {e}")
                        print(f"Error type: {type(e)}")
                        import traceback
                        print(f"Full traceback:")
                        traceback.print_exc()
                        return {'success': False, 'error': str(e)}
                    finally:
                        if 'loop' in locals():
                            loop.close()
                
                # Start generation in background thread
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(run_generation)
                    
                    # Stream progress while generation runs
                    while not future.done():
                        # Yield any queued progress updates
                        while progress_queue:
                            yield progress_queue.pop(0)
                        
                        # Small delay to prevent busy waiting
                        time.sleep(0.5)
                    
                    # Get final result
                    try:
                        result = future.result(timeout=30)  # 30 second timeout for final result
                    except Exception as e:
                        result = {'success': False, 'error': f'Generation failed: {str(e)}'}
                
                # Yield any remaining progress updates
                while progress_queue:
                    yield progress_queue.pop(0)
                
                # Send completion
                if result.get('success'):
                    # Check if user approval is required
                    if result.get('user_approval_required'):
                        # User approval required - send as special event type
                        user_approval_data = {
                            'type': 'result',
                            'success': True,
                            'user_approval_required': True,
                            'user_approval_data': result.get('user_approval_data'),
                            'qa_feedback': result.get('qa_feedback', []),
                            'qa_corrections': result.get('qa_corrections', []),
                            'song_structure': result.get('song_structure', {}),
                            'review_notes': result.get('review_notes', []),
                            'album_art': result.get('album_art', {}),
                            'provider': request_data['selected_provider'],
                            'model': request_data['selected_model'],
                            'timestamp': datetime.utcnow().isoformat()
                        }
                        yield f"data: {json.dumps(user_approval_data)}\n\n"
                    else:
                        # Normal successful completion
                        # Get song structure
                        song_structure = result['song_structure']
                        
                        # Check if we should save to a project
                        save_to_project = request_data.get('save_to_project', True)  # Default to True
                        project_id = request_data.get('project_id')  # Optional existing project ID
                        user_id = request_data.get('user_id', 'default')
                        
                        created_project = None
                        if save_to_project:
                            try:
                                from app.services.project_service import ProjectService
                                project_service = ProjectService()
                                
                                if project_id:
                                    # Update existing project
                                    created_project = project_service.update_project_from_song_structure(
                                        project_id=project_id,
                                        song_structure=song_structure
                                    )
                                    print(f"DEBUG: Updated existing project {project_id}")
                                else:
                                    # Create new project
                                    created_project = project_service.create_project_from_song_structure(
                                        song_structure=song_structure,
                                        user_id=user_id
                                    )
                                    print(f"DEBUG: Created new project {created_project['id']}")
                                    
                            except Exception as e:
                                print(f"DEBUG: Failed to save to project: {e}")
                                # Don't fail the whole generation, just log the error
                        
                        completion_data = {
                            'type': 'result',
                            'success': True,
                            'song_structure': song_structure,
                            'album_art': result.get('album_art', {}),
                            'review_notes': result.get('review_notes', []),
                            'qa_corrections': result.get('qa_corrections', []),
                            'provider': request_data['selected_provider'],
                            'model': request_data['selected_model'],
                            'timestamp': datetime.utcnow().isoformat(),
                            'project': created_project  # Include project info if created
                        }
                        yield f"data: {json.dumps(completion_data)}\n\n"
                else:
                    error_data = {
                        'type': 'error',
                        'success': False,
                        'error': result.get('error', 'Song generation failed'),
                        'errors': result.get('errors', []),
                        'review_notes': result.get('review_notes', [])
                    }
                    yield f"data: {json.dumps(error_data)}\n\n"
                    
            except ImportError as e:
                error_data = {
                    'type': 'error',
                    'success': False,
                    'error': 'LangGraph song generation not available. Please install required dependencies.',
                    'importError': True
                }
                yield f"data: {json.dumps(error_data)}\n\n"
            
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"LangGraph streaming generation error: {str(e)}")
            error_data = {
                'type': 'error',
                'success': False,
                'error': f'Song generation failed: {str(e)}'
            }
            yield f"data: {json.dumps(error_data)}\n\n"
    
    return Response(generate(), mimetype='text/plain', headers={
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Content-Type': 'text/event-stream',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Cache-Control'
    })


# ============================================================================
# USER APPROVAL WORKFLOW API ENDPOINTS (Placeholder for Future Implementation)
# ============================================================================

@ai_bp.route('/song-generation/approval/<session_id>', methods=['GET'])
@handle_errors
def get_user_approval_summary(session_id):
    """
    Get QA feedback summary for user approval decision
    
    Future Implementation:
    - Retrieve workflow state from session storage
    - Return QA feedback and improvement suggestions
    - Include current song structure summary
    """
    return jsonify({
        'success': False,
        'message': 'User approval workflow not yet fully implemented',
        'session_id': session_id,
        'requires_implementation': [
            'Session state management system',
            'Workflow state storage and retrieval',
            'Frontend user approval interface',
            'Workflow continuation mechanism'
        ],
        'example_response': {
            'qa_feedback': ['Example: Drum patterns could be more varied'],
            'qa_corrections': ['Example: Fixed missing instrument assignments'],
            'current_quality': 'needs_improvement',
            'restart_count': 1,
            'max_restarts': 2,
            'song_structure': {
                'tracks': 4,
                'duration': 180,
                'tempo': 120,
                'key': 'C major'
            },
            'improvement_areas': ['Instrumental content and arrangements']
        }
    })


@ai_bp.route('/song-generation/approval/<session_id>', methods=['POST'])
@handle_errors
def submit_user_approval_decision(session_id):
    """
    Submit user approval decision through progress dialog interface
    
    Expected payload:
    {
        "decision": "accept" | "improve",
        "feedback_note": "Optional user comments"
    }
    
    This endpoint handles user decisions made within the progress dialog
    """
    data = request.get_json()
    decision = data.get('decision', '')
    feedback_note = data.get('feedback_note', '')
    
    if decision not in ['accept', 'improve']:
        return jsonify({
            'success': False,
            'error': 'Decision must be either "accept" or "improve"'
        }), 400
    
    try:
        # Here you would normally:
        # 1. Retrieve the workflow state from session storage  
        # 2. Set the user_decision in the state
        # 3. Resume the LangGraph workflow execution
        # 4. Return the result
        
        # For now, return a success response with the expected behavior
        result = {
            'success': True,
            'message': f'User decision "{decision}" received and processed',
            'session_id': session_id,
            'decision': decision,
            'feedback_note': feedback_note,
            'next_action': 'complete' if decision == 'accept' else 'restart_workflow',
            'integration_status': {
                'progress_dialog': 'integrated',
                'decision_routing': 'implemented', 
                'session_management': 'pending',
                'workflow_continuation': 'pending'
            }
        }
        
        if decision == 'accept':
            result['workflow_result'] = 'Song will be completed with current version'
        else:
            result['workflow_result'] = 'AI will restart appropriate agent to address quality issues'
            result['improvement_areas'] = [
                'System will analyze QA feedback to determine restart point',
                'Workflow will continue from the most relevant agent',
                'Progress updates will show improvement iteration'
            ]
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to process user decision: {str(e)}',
            'session_id': session_id
        }), 500


@ai_bp.route('/song-generation/sessions', methods=['GET'])
@handle_errors
def list_active_approval_sessions():
    """
    List active song generation sessions waiting for user approval
    
    Future Implementation:
    - Query session storage for pending approval workflows
    - Return list of sessions with basic info
    - Include time since QA completed
    """
    return jsonify({
        'success': False,
        'message': 'Session management not yet implemented',
        'requires_implementation': [
            'Session storage system (Redis/Database)',
            'Session lifecycle management',
            'Session cleanup for completed/expired workflows'
        ],
        'example_response': {
            'active_sessions': [
                {
                    'session_id': 'song_gen_123456',
                    'created_at': '2025-01-08T10:30:00Z',
                    'qa_completed_at': '2025-01-08T10:35:00Z',
                    'song_name': 'Generated Song',
                    'status': 'awaiting_user_approval',
                    'restart_count': 1,
                    'quality_issues': 2
                }
            ]
        }
    })
