"""
Audio Processing API Routes
Handles audio file processing, waveform generation, and audio effects
"""

from flask import Blueprint, request, jsonify, current_app, send_file
from werkzeug.utils import secure_filename
from app.services.audio_service import AudioService
from app.utils.decorators import handle_errors
import os
import tempfile

audio_bp = Blueprint('audio', __name__)


@audio_bp.route('/upload', methods=['POST'])
@handle_errors
def upload_audio():
    """
    Upload and process audio files
    """
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not AudioService.allowed_file(file.filename):
        return jsonify({'error': 'File type not supported'}), 400
    
    try:
        audio_service = AudioService()
        result = audio_service.process_upload(file)
        
        return jsonify({
            'file_id': result['file_id'],
            'filename': result['filename'],
            'duration': result['duration'],
            'sample_rate': result['sample_rate'],
            'channels': result['channels'],
            'waveform_data': result['waveform_data'],
            'metadata': result['metadata']
        })
        
    except Exception as e:
        current_app.logger.error(f"Audio upload error: {str(e)}")
        return jsonify({'error': 'Failed to process audio file'}), 500


@audio_bp.route('/waveform/<file_id>', methods=['GET'])
@handle_errors
def get_waveform(file_id):
    """
    Generate waveform data for audio file
    """
    resolution = request.args.get('resolution', 1000, type=int)
    
    try:
        audio_service = AudioService()
        waveform_data = audio_service.generate_waveform(file_id, resolution)
        
        return jsonify({
            'file_id': file_id,
            'waveform': waveform_data,
            'resolution': resolution
        })
        
    except FileNotFoundError:
        return jsonify({'error': 'Audio file not found'}), 404
    except Exception as e:
        current_app.logger.error(f"Waveform generation error: {str(e)}")
        return jsonify({'error': 'Failed to generate waveform'}), 500


@audio_bp.route('/effects/apply', methods=['POST'])
@handle_errors
def apply_effects():
    """
    Apply audio effects to a file
    """
    data = request.get_json()
    file_id = data.get('file_id')
    effects = data.get('effects', {})
    
    if not file_id:
        return jsonify({'error': 'File ID is required'}), 400
    
    try:
        audio_service = AudioService()
        result = audio_service.apply_effects(file_id, effects)
        
        return jsonify({
            'processed_file_id': result['file_id'],
            'original_file_id': file_id,
            'effects_applied': effects,
            'processing_time': result['processing_time']
        })
        
    except FileNotFoundError:
        return jsonify({'error': 'Audio file not found'}), 404
    except Exception as e:
        current_app.logger.error(f"Effects processing error: {str(e)}")
        return jsonify({'error': 'Failed to apply effects'}), 500


@audio_bp.route('/convert', methods=['POST'])
@handle_errors
def convert_audio():
    """
    Convert audio between different formats
    """
    data = request.get_json()
    file_id = data.get('file_id')
    target_format = data.get('format', 'wav')
    target_sample_rate = data.get('sample_rate')
    target_bitrate = data.get('bitrate')
    
    if not file_id:
        return jsonify({'error': 'File ID is required'}), 400
    
    try:
        audio_service = AudioService()
        result = audio_service.convert_audio(
            file_id=file_id,
            target_format=target_format,
            target_sample_rate=target_sample_rate,
            target_bitrate=target_bitrate
        )
        
        return jsonify({
            'converted_file_id': result['file_id'],
            'original_file_id': file_id,
            'format': target_format,
            'sample_rate': result['sample_rate'],
            'bitrate': result.get('bitrate')
        })
        
    except FileNotFoundError:
        return jsonify({'error': 'Audio file not found'}), 404
    except Exception as e:
        current_app.logger.error(f"Audio conversion error: {str(e)}")
        return jsonify({'error': 'Failed to convert audio'}), 500


@audio_bp.route('/analyze', methods=['POST'])
@handle_errors
def analyze_audio():
    """
    Analyze audio features (tempo, key, etc.)
    """
    data = request.get_json()
    file_id = data.get('file_id')
    
    if not file_id:
        return jsonify({'error': 'File ID is required'}), 400
    
    try:
        audio_service = AudioService()
        analysis = audio_service.analyze_audio(file_id)
        
        return jsonify({
            'file_id': file_id,
            'tempo': analysis['tempo'],
            'key': analysis['key'],
            'time_signature': analysis['time_signature'],
            'loudness': analysis['loudness'],
            'spectral_features': analysis['spectral_features'],
            'harmonic_features': analysis['harmonic_features']
        })
        
    except FileNotFoundError:
        return jsonify({'error': 'Audio file not found'}), 404
    except Exception as e:
        current_app.logger.error(f"Audio analysis error: {str(e)}")
        return jsonify({'error': 'Failed to analyze audio'}), 500


@audio_bp.route('/download/<file_id>', methods=['GET'])
@handle_errors
def download_audio(file_id):
    """
    Download processed audio file
    """
    try:
        audio_service = AudioService()
        file_path = audio_service.get_file_path(file_id)
        
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404
        
        return send_file(
            file_path,
            as_attachment=True,
            download_name=f"processed_{file_id}.wav"
        )
        
    except Exception as e:
        current_app.logger.error(f"Audio download error: {str(e)}")
        return jsonify({'error': 'Failed to download file'}), 500


@audio_bp.route('/export', methods=['POST'])
@handle_errors
def export_project():
    """
    Export entire project as audio file
    """
    data = request.get_json()
    project_id = data.get('project_id')
    format = data.get('format', 'wav')
    quality = data.get('quality', 'high')
    
    if not project_id:
        return jsonify({'error': 'Project ID is required'}), 400
    
    try:
        audio_service = AudioService()
        export_result = audio_service.export_project(
            project_id=project_id,
            format=format,
            quality=quality
        )
        
        return jsonify({
            'export_file_id': export_result['file_id'],
            'project_id': project_id,
            'format': format,
            'quality': quality,
            'file_size': export_result['file_size'],
            'duration': export_result['duration']
        })
        
    except Exception as e:
        current_app.logger.error(f"Project export error: {str(e)}")
        return jsonify({'error': 'Failed to export project'}), 500


@audio_bp.route('/supported-formats', methods=['GET'])
def get_supported_formats():
    """
    Get list of supported audio formats
    """
    return jsonify({
        'input_formats': ['wav', 'mp3', 'flac', 'aiff', 'm4a', 'ogg'],
        'output_formats': ['wav', 'mp3', 'flac', 'aiff'],
        'effects': [
            'reverb', 'delay', 'chorus', 'distortion', 'compressor',
            'equalizer', 'limiter', 'gate', 'filter', 'modulation'
        ]
    })
