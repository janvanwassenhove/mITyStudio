"""
Musical Score Processing API Routes
Handles musical score sheet and tablature uploads, processing, and analysis
"""

from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
from app.utils.decorators import handle_errors
import os
import tempfile
from pathlib import Path
import uuid
from typing import Dict, List, Any, Optional
import json

score_bp = Blueprint('score', __name__)

# Supported file types for musical scores
ALLOWED_EXTENSIONS = {
    # Sheet music formats
    'pdf', 'png', 'jpg', 'jpeg', 'tiff', 'bmp', 'svg',
    # Tablature formats
    'gtp', 'gpx', 'gp5', 'gp4', 'ptb', 'tef',
    # Music notation formats
    'xml', 'musicxml', 'mxl', 'mid', 'midi', 'abc', 'ly',
    # Text-based formats
    'txt', 'tab'
}

# File size limits (in bytes)
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_FILES_PER_UPLOAD = 5

def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_file_category(filename: str) -> str:
    """Determine the category of the uploaded file"""
    extension = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    
    if extension in ['pdf', 'png', 'jpg', 'jpeg', 'tiff', 'bmp', 'svg']:
        return 'sheet_music'
    elif extension in ['gtp', 'gpx', 'gp5', 'gp4', 'ptb', 'tef']:
        return 'tablature'
    elif extension in ['xml', 'musicxml', 'mxl']:
        return 'musicxml'
    elif extension in ['mid', 'midi']:
        return 'midi'
    elif extension in ['abc', 'ly']:
        return 'notation'
    elif extension in ['txt', 'tab']:
        return 'text_tab'
    else:
        return 'unknown'

@score_bp.route('/upload', methods=['POST'])
@handle_errors
def upload_score_sheets():
    """
    Upload musical score sheets or tablatures for AI analysis
    """
    if 'files' not in request.files:
        return jsonify({'error': 'No files provided'}), 400
    
    files = request.files.getlist('files')
    if not files or all(f.filename == '' for f in files):
        return jsonify({'error': 'No files selected'}), 400
    
    if len(files) > MAX_FILES_PER_UPLOAD:
        return jsonify({'error': f'Maximum {MAX_FILES_PER_UPLOAD} files allowed per upload'}), 400
    
    # Validate files
    valid_files = []
    for file in files:
        if file.filename and allowed_file(file.filename):
            # Check file size
            file.seek(0, 2)  # Seek to end
            file_size = file.tell()
            file.seek(0)  # Reset to beginning
            
            if file_size > MAX_FILE_SIZE:
                return jsonify({'error': f'File {file.filename} exceeds maximum size of {MAX_FILE_SIZE // (1024*1024)}MB'}), 400
            
            valid_files.append(file)
    
    if not valid_files:
        return jsonify({'error': 'No valid score files found. Supported formats: PDF, images (PNG, JPG), Guitar Pro (GTP, GPX), MusicXML, MIDI, ABC, LilyPond, text tabs'}), 400
    
    try:
        from app.services.score_service import ScoreService
        
        score_service = ScoreService()
        results = []
        
        # Process each file
        for file in valid_files:
            result = score_service.process_score_file(file)
            results.append(result)
        
        return jsonify({
            'success': True,
            'files_processed': len(results),
            'results': results,
            'message': f'Successfully processed {len(results)} score file(s)'
        })
        
    except Exception as e:
        current_app.logger.error(f"Score processing error: {str(e)}")
        return jsonify({'error': f'Failed to process score files: {str(e)}'}), 500

@score_bp.route('/analyze/<file_id>', methods=['GET'])
@handle_errors
def analyze_score(file_id: str):
    """
    Get detailed analysis of a processed score file
    """
    try:
        from app.services.score_service import ScoreService
        
        score_service = ScoreService()
        analysis = score_service.get_score_analysis(file_id)
        
        if not analysis:
            return jsonify({'error': 'Score analysis not found'}), 404
        
        return jsonify(analysis)
        
    except Exception as e:
        current_app.logger.error(f"Score analysis error: {str(e)}")
        return jsonify({'error': 'Failed to analyze score'}), 500

@score_bp.route('/generate-json/<file_id>', methods=['POST'])
@handle_errors
def generate_json_structure(file_id: str):
    """
    Generate JSON instrument structure from processed score
    """
    data = request.get_json()
    instrument_name = data.get('instrument', 'piano')  # Default instrument
    track_name = data.get('trackName', 'Score Track')
    
    try:
        from app.services.score_service import ScoreService
        
        score_service = ScoreService()
        json_structure = score_service.generate_json_structure(
            file_id, 
            instrument_name=instrument_name,
            track_name=track_name
        )
        
        if not json_structure:
            return jsonify({'error': 'Could not generate JSON structure from score'}), 404
        
        return jsonify({
            'success': True,
            'json_structure': json_structure,
            'file_id': file_id,
            'instrument': instrument_name,
            'track_name': track_name
        })
        
    except Exception as e:
        current_app.logger.error(f"JSON generation error: {str(e)}")
        return jsonify({'error': 'Failed to generate JSON structure'}), 500

@score_bp.route('/supported-formats', methods=['GET'])
def get_supported_formats():
    """
    Get list of supported score file formats
    """
    formats = {
        'sheet_music': {
            'extensions': ['pdf', 'png', 'jpg', 'jpeg', 'tiff', 'bmp', 'svg'],
            'description': 'Sheet music images and PDFs'
        },
        'tablature': {
            'extensions': ['gtp', 'gpx', 'gp5', 'gp4', 'ptb', 'tef'],
            'description': 'Guitar tablature files (Guitar Pro, PowerTab)'
        },
        'musicxml': {
            'extensions': ['xml', 'musicxml', 'mxl'],
            'description': 'MusicXML notation files'
        },
        'midi': {
            'extensions': ['mid', 'midi'],
            'description': 'MIDI files'
        },
        'notation': {
            'extensions': ['abc', 'ly'],
            'description': 'ABC notation and LilyPond files'
        },
        'text_tab': {
            'extensions': ['txt', 'tab'],
            'description': 'Text-based tablature'
        }
    }
    
    return jsonify({
        'supported_formats': formats,
        'max_file_size': f'{MAX_FILE_SIZE // (1024*1024)}MB',
        'max_files_per_upload': MAX_FILES_PER_UPLOAD,
        'all_extensions': sorted(list(ALLOWED_EXTENSIONS))
    })

@score_bp.route('/list', methods=['GET'])
@handle_errors
def list_uploaded_scores():
    """
    List all uploaded and processed score files
    """
    try:
        from app.services.score_service import ScoreService
        
        score_service = ScoreService()
        scores = score_service.list_scores()
        
        return jsonify({
            'scores': scores,
            'count': len(scores)
        })
        
    except Exception as e:
        current_app.logger.error(f"Score listing error: {str(e)}")
        return jsonify({'error': 'Failed to list scores'}), 500

@score_bp.route('/delete/<file_id>', methods=['DELETE'])
@handle_errors
def delete_score(file_id: str):
    """
    Delete a processed score file
    """
    try:
        from app.services.score_service import ScoreService
        
        score_service = ScoreService()
        success = score_service.delete_score(file_id)
        
        if not success:
            return jsonify({'error': 'Score not found'}), 404
        
        return jsonify({
            'success': True,
            'message': 'Score deleted successfully'
        })
        
    except Exception as e:
        current_app.logger.error(f"Score deletion error: {str(e)}")
        return jsonify({'error': 'Failed to delete score'}), 500