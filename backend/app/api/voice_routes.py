"""
Voice Training and Synthesis API Routes
Handles DiffSinger voice training, synthesis, and management
"""

from flask import Blueprint, request, jsonify, current_app, send_file
from werkzeug.utils import secure_filename
from app.services.voice_service import VoiceService
from app.models.song_structure import AudioClip
from app.utils.decorators import handle_errors
import os
import tempfile
import uuid

voice_bp = Blueprint('voice', __name__)


@voice_bp.route('/voices', methods=['GET'])
@handle_errors
def get_available_voices():
    """
    Get list of available voice profiles
    """
    try:
        voice_service = VoiceService()
        voices = voice_service.get_available_voices()
        
        return jsonify({
            'voices': voices,
            'total': len(voices)
        })
        
    except Exception as e:
        current_app.logger.error(f"Error fetching voices: {str(e)}")
        return jsonify({'error': 'Failed to fetch available voices'}), 500


@voice_bp.route('/voices/<voice_id>', methods=['DELETE'])
@handle_errors
def delete_voice(voice_id):
    """
    Delete a custom voice profile
    """
    try:
        voice_service = VoiceService()
        success = voice_service.delete_voice(voice_id)
        
        if success:
            return jsonify({'message': 'Voice deleted successfully'})
        else:
            return jsonify({'error': 'Voice not found'}), 404
            
    except Exception as e:
        current_app.logger.error(f"Error deleting voice {voice_id}: {str(e)}")
        return jsonify({'error': 'Failed to delete voice'}), 500


@voice_bp.route('/test/<voice_id>', methods=['POST'])
@handle_errors
def test_voice(voice_id):
    """
    Generate a test audio sample for a voice (singing by default with chord accompaniment)
    """
    try:
        data = request.get_json() or {}
        test_text = data.get('text', 'mitystudio forever')
        
        voice_service = VoiceService()
        audio_file = None
        
        # Check if user specifically wants spoken voice only
        force_spoken = data.get('spoken', False)
        
        if not force_spoken:
            # Default to singing with a nice melody and chord progression
            try:
                # Define a pleasant melody for the test phrase
                # "mi-ty-stu-di-o for-e-ver" (8 syllables)
                # Using a simple chord progression: C - Am - F - G
                test_notes = data.get('notes', ['C4', 'E4', 'G4', 'A4', 'F4', 'G4', 'E4', 'C4'])
                
                # Define chord progression that complements the melody
                chord_progression = data.get('chordName', 'C')  # Start with C major
                
                current_app.logger.info(f"Generating singing voice test for {voice_id} with chord: {chord_progression}")
                audio_file = voice_service.synthesize_speech(
                    text=test_text,
                    voice_id=voice_id,
                    notes=test_notes,
                    chord_name=chord_progression,
                    duration=4.0  # Give enough time for the melody and chords
                )
            except Exception as e:
                current_app.logger.warning(f"Singing synthesis failed for voice {voice_id}: {str(e)}")
                audio_file = None
        
        # Fallback to spoken voice if singing failed or explicitly requested
        if not audio_file:
            current_app.logger.info(f"Generating spoken voice test for {voice_id}")
            audio_file = voice_service.test_voice(voice_id, test_text)
        
        if audio_file:
            return send_file(
                audio_file,
                mimetype='audio/wav',
                as_attachment=True,
                download_name=f'voice_test_{voice_id}.wav'
            )
        else:
            return jsonify({'error': 'Voice not found'}), 404
            
    except Exception as e:
        current_app.logger.error(f"Error testing voice {voice_id}: {str(e)}")
        return jsonify({'error': 'Failed to test voice'}), 500


@voice_bp.route('/test-singing/<voice_id>', methods=['POST'])
@handle_errors
def test_voice_singing(voice_id):
    """
    Generate a singing test sample for a voice with musical notes and chord progression
    """
    try:
        data = request.get_json() or {}
        test_text = data.get('text', 'mitystudio forever')
        
        # Define a more elaborate melody for the test phrase
        # "mi-ty-stu-di-o for-e-ver" (8 syllables)
        # Using a more complex melody with harmony
        test_notes = data.get('notes', ['C4', 'D4', 'E4', 'F4', 'G4', 'A4', 'G4', 'C5'])
        
        # Define a nice chord progression: C - Am - F - G (I - vi - IV - V)
        chord_name = data.get('chordName', 'C')
        
        voice_service = VoiceService()
        
        current_app.logger.info(f"Generating advanced singing voice test for {voice_id} with chord: {chord_name}")
        audio_file = voice_service.synthesize_speech(
            text=test_text,
            voice_id=voice_id,
            notes=test_notes,
            chord_name=chord_name,
            duration=5.0  # Longer duration for more elaborate performance
        )
        
        if audio_file:
            return send_file(
                audio_file,
                mimetype='audio/wav',
                as_attachment=True,
                download_name=f'voice_singing_test_{voice_id}.wav'
            )
        else:
            return jsonify({'error': 'Failed to generate singing voice test'}), 500
            
    except Exception as e:
        current_app.logger.error(f"Error testing singing voice {voice_id}: {str(e)}")
        return jsonify({'error': 'Failed to test singing voice'}), 500


@voice_bp.route('/train/recording', methods=['POST'])
@handle_errors
def train_voice_from_recording():
    """
    Train a new voice from a single recording
    """
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file provided'}), 400
    
    voice_name = request.form.get('voiceName')
    if not voice_name:
        return jsonify({'error': 'Voice name is required'}), 400
    
    audio_file = request.files['audio']
    if audio_file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    try:
        # Get optional parameters
        duration = float(request.form.get('duration', 0))
        sample_rate = int(request.form.get('sampleRate', 44100))
        language = request.form.get('language', 'en')
        
        voice_service = VoiceService()
        job_id = voice_service.train_voice_from_recording(
            voice_name=voice_name,
            audio_file=audio_file,
            duration=duration,
            sample_rate=sample_rate,
            language=language
        )
        
        return jsonify({
            'jobId': job_id,
            'message': 'Voice training started',
            'voiceName': voice_name
        })
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Error training voice from recording: {str(e)}")
        return jsonify({'error': 'Failed to start voice training'}), 500


@voice_bp.route('/train/files', methods=['POST'])
@handle_errors
def train_voice_from_files():
    """
    Train a new voice from multiple audio files
    """
    voice_name = request.form.get('voiceName')
    if not voice_name:
        return jsonify({'error': 'Voice name is required'}), 400
    
    # Get all audio files
    audio_files = []
    for key in request.files:
        if key.startswith('audio_'):
            audio_files.append(request.files[key])
    
    if not audio_files:
        return jsonify({'error': 'No audio files provided'}), 400
    
    try:
        # Get optional parameters
        language = request.form.get('language', 'en')
        epochs = int(request.form.get('epochs', 100))
        speaker_embedding = request.form.get('speakerEmbedding', 'true').lower() == 'true'
        
        voice_service = VoiceService()
        job_id = voice_service.train_voice_from_files(
            voice_name=voice_name,
            audio_files=audio_files,
            language=language,
            epochs=epochs,
            speaker_embedding=speaker_embedding
        )
        
        return jsonify({
            'jobId': job_id,
            'message': 'Voice training started',
            'voiceName': voice_name,
            'fileCount': len(audio_files)
        })
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Error training voice from files: {str(e)}")
        return jsonify({'error': 'Failed to start voice training'}), 500


@voice_bp.route('/training/<job_id>', methods=['GET'])
@handle_errors
def get_training_status(job_id):
    """
    Get the status of a voice training job
    """
    try:
        voice_service = VoiceService()
        status = voice_service.get_training_status(job_id)
        
        if status:
            return jsonify(status)
        else:
            return jsonify({'error': 'Training job not found'}), 404
            
    except Exception as e:
        current_app.logger.error(f"Error getting training status {job_id}: {str(e)}")
        return jsonify({'error': 'Failed to get training status'}), 500


@voice_bp.route('/training/<job_id>/cancel', methods=['POST'])
@handle_errors
def cancel_training(job_id):
    """
    Cancel a voice training job
    """
    try:
        voice_service = VoiceService()
        success = voice_service.cancel_training(job_id)
        
        if success:
            return jsonify({'message': 'Training job cancelled'})
        else:
            return jsonify({'error': 'Training job not found'}), 404
            
    except Exception as e:
        current_app.logger.error(f"Error cancelling training {job_id}: {str(e)}")
        return jsonify({'error': 'Failed to cancel training'}), 500


@voice_bp.route('/synthesize', methods=['POST'])
@handle_errors
def synthesize_speech():
    """
    Synthesize speech using a trained voice with optional musical parameters
    """
    try:
        data = request.get_json()
        
        if not data or 'text' not in data or 'voiceId' not in data:
            return jsonify({'error': 'Text and voiceId are required'}), 400
        
        text = data['text']
        voice_id = data['voiceId']
        
        # Standard synthesis parameters
        speed = data.get('speed', 1.0)
        pitch = data.get('pitch', 0.0)
        energy = data.get('energy', 1.0)
        
        # Musical parameters for singing synthesis
        notes = data.get('notes', [])
        chord_name = data.get('chordName')
        start_time = data.get('startTime', 0.0)
        duration = data.get('duration')
        
        voice_service = VoiceService()
        audio_file = voice_service.synthesize_speech(
            text=text,
            voice_id=voice_id,
            speed=speed,
            pitch=pitch,
            energy=energy,
            notes=notes,
            chord_name=chord_name,
            start_time=start_time,
            duration=duration
        )
        
        if audio_file:
            return send_file(
                audio_file,
                mimetype='audio/wav',
                as_attachment=True,
                download_name=f'synthesized_{voice_id}.wav'
            )
        else:
            return jsonify({'error': 'Voice not found'}), 404
            
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Error synthesizing speech: {str(e)}")
        return jsonify({'error': 'Failed to synthesize speech'}), 500


@voice_bp.route('/synthesize-multi-voice', methods=['POST'])
@handle_errors
def synthesize_multi_voice():
    """
    Synthesize a multi-voice lyrics clip using the new voices structure
    """
    try:
        from app.models.song_structure import SongStructure, AudioClip
        
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Clip data is required'}), 400
        
        # Validate that this is a proper multi-voice structure
        voices_data = data.get('voices', [])
        if not voices_data:
            return jsonify({'error': 'Voices array is required for multi-voice synthesis'}), 400
        
        # Validate the clip structure
        try:
            clip = AudioClip.from_dict(data)
            if not clip.has_multi_voice():
                return jsonify({'error': 'This endpoint requires multi-voice structure'}), 400
            
            if not clip.validate_lyrics_structure():
                return jsonify({'error': 'Invalid lyrics structure - cannot mix simple and advanced formats'}), 400
                
        except Exception as e:
            current_app.logger.error(f"Clip validation failed: {e}")
            return jsonify({'error': 'Invalid clip structure'}), 400
        
        # Perform synthesis
        voice_service = VoiceService()
        audio_file = voice_service.synthesize_multi_voice_clip(data)
        
        if audio_file:
            return send_file(
                audio_file,
                mimetype='audio/wav',
                as_attachment=True,
                download_name=f'multi_voice_{data.get("id", "clip")}.wav'
            )
        else:
            return jsonify({'error': 'Failed to synthesize multi-voice clip'}), 500
            
    except Exception as e:
        current_app.logger.error(f"Error synthesizing multi-voice clip: {str(e)}")
        return jsonify({'error': 'Failed to synthesize multi-voice clip'}), 500


@voice_bp.route('/validate-lyrics-structure', methods=['POST'])
@handle_errors
def validate_lyrics_structure():
    """
    Validate a lyrics clip structure for compliance with the new contract
    """
    try:
        from app.models.song_structure import AudioClip
        
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Clip data is required'}), 400
        
        # Try to parse as AudioClip
        try:
            clip = AudioClip.from_dict(data)
        except Exception as e:
            return jsonify({
                'valid': False,
                'error': f'Failed to parse clip structure: {str(e)}'
            }), 400
        
        # Validate structure
        validation_result = {
            'valid': True,
            'is_lyrics_clip': clip.is_lyrics_clip(),
            'has_multi_voice': clip.has_multi_voice(),
            'structure_valid': clip.validate_lyrics_structure(),
            'errors': [],
            'warnings': []
        }
        
        if not clip.validate_lyrics_structure():
            validation_result['valid'] = False
            validation_result['errors'].append('Cannot mix simple and advanced lyrics structures')
        
        if clip.is_lyrics_clip():
            # Additional validation for lyrics clips
            if clip.has_multi_voice():
                # Validate multi-voice structure
                for i, voice in enumerate(clip.voices):
                    if not voice.voice_id:
                        validation_result['errors'].append(f'Voice {i} missing voice_id')
                    if not voice.lyrics:
                        validation_result['errors'].append(f'Voice {voice.voice_id} has no lyrics fragments')
                    
                    for j, fragment in enumerate(voice.lyrics):
                        if not fragment.text:
                            validation_result['warnings'].append(f'Voice {voice.voice_id} fragment {j} has no text')
                        if not fragment.notes:
                            validation_result['warnings'].append(f'Voice {voice.voice_id} fragment {j} has no notes')
                        
                        # Validate timing
                        if fragment.duration is None and fragment.durations is None:
                            validation_result['warnings'].append(f'Voice {voice.voice_id} fragment {j} has no duration specified')
                        elif fragment.durations and len(fragment.durations) != len(fragment.notes):
                            validation_result['errors'].append(f'Voice {voice.voice_id} fragment {j} has mismatched durations and notes count')
            else:
                # Validate simple structure
                if not any([clip.text, clip.voiceId]):
                    validation_result['warnings'].append('Simple lyrics structure is incomplete')
        
        if validation_result['errors']:
            validation_result['valid'] = False
            
        return jsonify(validation_result)
        
    except Exception as e:
        current_app.logger.error(f"Error validating lyrics structure: {str(e)}")
        return jsonify({'error': 'Failed to validate lyrics structure'}), 500


@voice_bp.route('/test-with-chords/<voice_id>', methods=['POST'])
@handle_errors
def test_voice_with_chords(voice_id):
    """
    Generate a singing test with a full chord progression accompaniment
    """
    try:
        data = request.get_json() or {}
        test_text = data.get('text', 'mitystudio forever')
        
        # Define chord progressions to choose from
        chord_progressions = {
            'classic': 'C',      # Simple C major
            'pop': 'Am',         # Am - F - C - G progression
            'jazz': 'Cmaj7',     # Jazz harmony
            'folk': 'G',         # G - C - D progression
            'romantic': 'F'      # F - C - Dm - Bb progression
        }
        
        progression_type = data.get('progression', 'classic')
        chord_name = chord_progressions.get(progression_type, 'C')
        
        # Advanced melody that works well with chord progressions
        # "mi-ty-stu-di-o for-e-ver" (8 syllables)
        advanced_melodies = {
            'classic': ['C4', 'E4', 'G4', 'A4', 'F4', 'G4', 'E4', 'C4'],
            'pop': ['A4', 'C5', 'B4', 'A4', 'F4', 'G4', 'A4', 'F4'],
            'jazz': ['C4', 'E4', 'G4', 'B4', 'A4', 'F4', 'D4', 'C4'],
            'folk': ['G4', 'B4', 'C5', 'D5', 'C5', 'B4', 'A4', 'G4'],
            'romantic': ['F4', 'A4', 'C5', 'D5', 'Bb4', 'C5', 'A4', 'F4']
        }
        
        test_notes = data.get('notes', advanced_melodies.get(progression_type, advanced_melodies['classic']))
        
        voice_service = VoiceService()
        
        current_app.logger.info(f"Generating {progression_type} style singing for {voice_id} with chord: {chord_name}")
        audio_file = voice_service.synthesize_speech(
            text=test_text,
            voice_id=voice_id,
            notes=test_notes,
            chord_name=chord_name,
            duration=6.0  # Longer for full chord progression
        )
        
        if audio_file:
            return send_file(
                audio_file,
                mimetype='audio/wav',
                as_attachment=True,
                download_name=f'voice_chords_{progression_type}_{voice_id}.wav'
            )
        else:
            return jsonify({'error': 'Failed to generate chord-based voice test'}), 500
            
    except Exception as e:
        current_app.logger.error(f"Error testing voice with chords {voice_id}: {str(e)}")
        return jsonify({'error': 'Failed to test voice with chords'}), 500
