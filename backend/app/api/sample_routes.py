"""
User Sample Management API Routes
Handles user-uploaded sample metadata and integration with AI agents
Enhanced with advanced audio analysis and tagging
"""

from flask import Blueprint, request, jsonify, current_app
from app.utils.decorators import handle_errors
from app.services.audio_analysis_service import analyze_sample, AudioAnalysisResult
import json
import os
from typing import Dict, List, Any
import tempfile
import base64

sample_bp = Blueprint('samples', __name__)

# In-memory storage for sample metadata (in production, use database)
_user_samples_metadata = {}

@sample_bp.route('/analyze', methods=['POST'])
@handle_errors
def analyze_uploaded_sample():
    """
    Analyze uploaded audio file and return comprehensive metadata
    Accepts audio file data and performs advanced AI-based analysis
    """
    try:
        data = request.get_json()
        
        if not data or 'audioData' not in data:
            return jsonify({'error': 'No audio data provided'}), 400
        
        # Decode base64 audio data
        audio_data = base64.b64decode(data['audioData'])
        
        # Create temporary file for analysis
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            temp_file.write(audio_data)
            temp_file_path = temp_file.name
        
        try:
            # Perform advanced audio analysis
            analysis_result = analyze_sample(temp_file_path)
            
            # Convert analysis result to dictionary
            enhanced_metadata = {
                # Basic properties
                'duration': analysis_result.duration,
                'tempo': analysis_result.tempo,
                'key': analysis_result.key,
                'time_signature': analysis_result.time_signature,
                
                # Enhanced categorization
                'track_type': analysis_result.track_type.value,
                'primary_category': analysis_result.primary_category,
                'secondary_categories': analysis_result.secondary_categories,
                
                # Vibe and mood
                'vibe': analysis_result.vibe.value,
                'energy_level': analysis_result.energy_level,
                'valence': analysis_result.valence,
                'danceability': analysis_result.danceability,
                
                # Semantic tags
                'instrument_tags': analysis_result.instrument_tags,
                'genre_tags': analysis_result.genre_tags,
                'mood_tags': analysis_result.mood_tags,
                'style_tags': analysis_result.style_tags,
                
                # Combined tags for easy searching
                'all_tags': (analysis_result.instrument_tags + 
                           analysis_result.genre_tags + 
                           analysis_result.mood_tags + 
                           analysis_result.style_tags),
                
                # AI-generated description
                'ai_description': analysis_result.auto_description,
                
                # Technical features (for advanced users/debugging)
                'technical_analysis': {
                    'spectral_centroid_mean': analysis_result.spectral_centroid_mean,
                    'spectral_rolloff_mean': analysis_result.spectral_rolloff_mean,
                    'zero_crossing_rate': analysis_result.zero_crossing_rate,
                    'yamnet_classifications': analysis_result.yamnet_top_classes[:5]  # Top 5
                }
            }
            
            current_app.logger.info(f"Successfully analyzed audio sample: {analysis_result.primary_category}")
            
            return jsonify({
                'success': True,
                'analysis': enhanced_metadata,
                'message': 'Audio analysis completed successfully'
            })
            
        finally:
            # Clean up temporary file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
        
    except Exception as e:
        current_app.logger.error(f"Error analyzing audio sample: {str(e)}")
        return jsonify({'error': 'Failed to analyze audio sample'}), 500


@sample_bp.route('/metadata', methods=['POST'])
@handle_errors
def store_sample_metadata():
    """
    Store metadata for user-uploaded samples from frontend
    Now enhanced with AI analysis results
    """
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    # Validate required fields
    required_fields = ['id', 'name']  # Relaxed requirements since AI can fill in category
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    try:
        # Store the enhanced metadata
        sample_id = data['id']
        _user_samples_metadata[sample_id] = {
            'id': data['id'],
            'name': data['name'],
            'duration': data.get('duration'),
            'category': data.get('category', 'other'),
            'tags': data.get('tags', []),
            'bpm': data.get('bpm'),
            'key': data.get('key'),
            'waveform': data.get('waveform', []),
            'created_at': data.get('createdAt'),
            'updated_at': data.get('updatedAt'),
            
            # Enhanced AI analysis fields
            'track_type': data.get('track_type'),
            'primary_category': data.get('primary_category', data.get('category', 'other')),
            'secondary_categories': data.get('secondary_categories', []),
            'vibe': data.get('vibe'),
            'energy_level': data.get('energy_level'),
            'valence': data.get('valence'),
            'danceability': data.get('danceability'),
            'instrument_tags': data.get('instrument_tags', []),
            'genre_tags': data.get('genre_tags', []),
            'mood_tags': data.get('mood_tags', []),
            'style_tags': data.get('style_tags', []),
            'all_tags': data.get('all_tags', data.get('tags', [])),
            'ai_description': data.get('ai_description'),
            'time_signature': data.get('time_signature'),
            'technical_analysis': data.get('technical_analysis', {})
        }
        
        current_app.logger.info(f"Stored metadata for sample: {sample_id}")
        
        return jsonify({
            'success': True,
            'sample_id': sample_id,
            'message': 'Sample metadata stored successfully'
        })
        
    except Exception as e:
        current_app.logger.error(f"Error storing sample metadata: {str(e)}")
        return jsonify({'error': 'Failed to store sample metadata'}), 500


@sample_bp.route('/metadata/bulk', methods=['POST'])
@handle_errors
def store_bulk_sample_metadata():
    """
    Store metadata for multiple user-uploaded samples at once
    """
    data = request.get_json()
    
    if not data or 'samples' not in data:
        return jsonify({'error': 'No samples data provided'}), 400
    
    samples = data['samples']
    if not isinstance(samples, list):
        return jsonify({'error': 'Samples must be an array'}), 400
    
    try:
        stored_count = 0
        errors = []
        
        for sample in samples:
            try:
                # Validate required fields
                required_fields = ['id', 'name', 'category']
                for field in required_fields:
                    if field not in sample:
                        errors.append(f"Sample {sample.get('id', 'unknown')}: Missing field {field}")
                        continue
                
                # Store the metadata
                sample_id = sample['id']
                _user_samples_metadata[sample_id] = {
                    'id': sample['id'],
                    'name': sample['name'],
                    'duration': sample.get('duration'),
                    'category': sample['category'],
                    'tags': sample.get('tags', []),
                    'bpm': sample.get('bpm'),
                    'key': sample.get('key'),
                    'waveform': sample.get('waveform', []),
                    'created_at': sample.get('createdAt'),
                    'updated_at': sample.get('updatedAt')
                }
                stored_count += 1
                
            except Exception as e:
                errors.append(f"Sample {sample.get('id', 'unknown')}: {str(e)}")
        
        current_app.logger.info(f"Stored metadata for {stored_count} samples")
        
        return jsonify({
            'success': True,
            'stored_count': stored_count,
            'errors': errors,
            'message': f'Stored {stored_count} samples successfully'
        })
        
    except Exception as e:
        current_app.logger.error(f"Error storing bulk sample metadata: {str(e)}")
        return jsonify({'error': 'Failed to store sample metadata'}), 500


@sample_bp.route('/metadata', methods=['GET'])
@handle_errors
def get_all_sample_metadata():
    """
    Get all user sample metadata for AI agents
    """
    try:
        return jsonify({
            'samples': _user_samples_metadata,
            'count': len(_user_samples_metadata)
        })
        
    except Exception as e:
        current_app.logger.error(f"Error retrieving sample metadata: {str(e)}")
        return jsonify({'error': 'Failed to retrieve sample metadata'}), 500


@sample_bp.route('/metadata/<sample_id>', methods=['GET'])
@handle_errors
def get_sample_metadata(sample_id):
    """
    Get metadata for a specific sample
    """
    try:
        if sample_id not in _user_samples_metadata:
            return jsonify({'error': 'Sample not found'}), 404
        
        return jsonify(_user_samples_metadata[sample_id])
        
    except Exception as e:
        current_app.logger.error(f"Error retrieving sample metadata: {str(e)}")
        return jsonify({'error': 'Failed to retrieve sample metadata'}), 500


@sample_bp.route('/metadata/<sample_id>', methods=['DELETE'])
@handle_errors
def delete_sample_metadata(sample_id):
    """
    Delete metadata for a specific sample
    """
    try:
        if sample_id not in _user_samples_metadata:
            return jsonify({'error': 'Sample not found'}), 404
        
        del _user_samples_metadata[sample_id]
        
        current_app.logger.info(f"Deleted metadata for sample: {sample_id}")
        
        return jsonify({
            'success': True,
            'message': 'Sample metadata deleted successfully'
        })
        
    except Exception as e:
        current_app.logger.error(f"Error deleting sample metadata: {str(e)}")
        return jsonify({'error': 'Failed to delete sample metadata'}), 500


@sample_bp.route('/search', methods=['POST'])
@handle_errors
def search_samples():
    """
    Enhanced search for user samples by metadata criteria
    Now supports AI-generated tags, vibe, track type, and semantic search
    """
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No search criteria provided'}), 400
    
    try:
        # Enhanced search criteria
        category = data.get('category')
        tags = data.get('tags', [])
        bpm_range = data.get('bpm_range')  # [min, max]
        key = data.get('key')
        duration_range = data.get('duration_range')  # [min, max]
        
        # New AI-enhanced criteria
        track_type = data.get('track_type')  # vocals, instrumentals, vocals_and_instrumentals
        vibe = data.get('vibe')  # energetic, chill, dark, etc.
        energy_range = data.get('energy_range')  # [min, max] 0.0-1.0
        genre_tags = data.get('genre_tags', [])
        mood_tags = data.get('mood_tags', [])
        instrument_tags = data.get('instrument_tags', [])
        text_search = data.get('text_search', '').lower()  # Search in descriptions and names
        
        results = []
        
        for sample_id, metadata in _user_samples_metadata.items():
            # Traditional criteria
            if category and metadata.get('primary_category', metadata.get('category')) != category:
                continue
            
            # Enhanced tag matching (now includes AI tags)
            all_sample_tags = set(metadata.get('all_tags', []) + metadata.get('tags', []))
            if tags and not any(tag.lower() in [t.lower() for t in all_sample_tags] for tag in tags):
                continue
            
            # BPM range
            if bpm_range and metadata.get('bpm'):
                bmp_value = metadata.get('bpm') or metadata.get('tempo')
                if bmp_value and (bmp_value < bpm_range[0] or bmp_value > bpm_range[1]):
                    continue
            
            # Key matching
            if key and metadata.get('key') != key:
                continue
            
            # Duration range
            if duration_range and metadata.get('duration'):
                duration = metadata['duration']
                if duration < duration_range[0] or duration > duration_range[1]:
                    continue
            
            # NEW: Track type filtering
            if track_type and metadata.get('track_type') != track_type:
                continue
            
            # NEW: Vibe filtering
            if vibe and metadata.get('vibe') != vibe:
                continue
            
            # NEW: Energy level range
            if energy_range and metadata.get('energy_level') is not None:
                energy = metadata['energy_level']
                if energy < energy_range[0] or energy > energy_range[1]:
                    continue
            
            # NEW: Genre tag matching
            if genre_tags:
                sample_genres = set([g.lower() for g in metadata.get('genre_tags', [])])
                search_genres = set([g.lower() for g in genre_tags])
                if not search_genres.intersection(sample_genres):
                    continue
            
            # NEW: Mood tag matching  
            if mood_tags:
                sample_moods = set([m.lower() for m in metadata.get('mood_tags', [])])
                search_moods = set([m.lower() for m in mood_tags])
                if not search_moods.intersection(sample_moods):
                    continue
            
            # NEW: Instrument tag matching
            if instrument_tags:
                sample_instruments = set([i.lower() for i in metadata.get('instrument_tags', [])])
                search_instruments = set([i.lower() for i in instrument_tags])
                if not search_instruments.intersection(sample_instruments):
                    continue
            
            # NEW: Text search in names and descriptions
            if text_search:
                searchable_text = ' '.join([
                    metadata.get('name', '').lower(),
                    metadata.get('ai_description', '').lower(),
                    ' '.join(metadata.get('all_tags', [])).lower()
                ])
                if text_search not in searchable_text:
                    continue
            
            results.append(metadata)
        
        # Sort results by relevance (could be enhanced with ML scoring)
        # For now, sort by energy level if searching by vibe, otherwise by name
        if vibe or energy_range:
            results.sort(key=lambda x: x.get('energy_level', 0.5), reverse=True)
        else:
            results.sort(key=lambda x: x.get('name', '').lower())
        
        return jsonify({
            'results': results,
            'count': len(results),
            'search_criteria': data,
            'message': f'Found {len(results)} matching samples'
        })
        
    except Exception as e:
        current_app.logger.error(f"Error searching samples: {str(e)}")
        return jsonify({'error': 'Failed to search samples'}), 500


def get_user_samples_for_agents() -> Dict[str, Any]:
    """
    Get enhanced user sample metadata for AI agents
    Returns organized data structure with rich AI-generated metadata
    """
    try:
        # Organize samples by multiple criteria for better AI understanding
        organized_samples = {
            'by_category': {},
            'by_track_type': {},
            'by_vibe': {},
            'by_genre': {},
            'all_samples': []
        }
        
        for sample_id, metadata in _user_samples_metadata.items():
            # Create comprehensive agent-friendly format
            sample_info = {
                'name': metadata['name'],
                'id': sample_id,
                'duration': metadata.get('duration'),
                'bpm': metadata.get('bpm', metadata.get('tempo')),
                'key': metadata.get('key'),
                
                # AI-enhanced metadata
                'track_type': metadata.get('track_type', 'unknown'),
                'primary_category': metadata.get('primary_category', metadata.get('category', 'other')),
                'secondary_categories': metadata.get('secondary_categories', []),
                'vibe': metadata.get('vibe', 'unknown'),
                'energy_level': metadata.get('energy_level'),
                'valence': metadata.get('valence'),
                'danceability': metadata.get('danceability'),
                
                # Rich tagging
                'instrument_tags': metadata.get('instrument_tags', []),
                'genre_tags': metadata.get('genre_tags', []),
                'mood_tags': metadata.get('mood_tags', []),
                'style_tags': metadata.get('style_tags', []),
                'all_tags': metadata.get('all_tags', metadata.get('tags', [])),
                
                # AI description for context
                'description': metadata.get('ai_description', ''),
                'time_signature': metadata.get('time_signature'),
                
                # Legacy fields for backwards compatibility
                'category': metadata.get('primary_category', metadata.get('category', 'other')),
                'tags': metadata.get('all_tags', metadata.get('tags', []))
            }
            
            # Add to all samples
            organized_samples['all_samples'].append(sample_info)
            
            # Organize by category
            category = sample_info['primary_category']
            if category not in organized_samples['by_category']:
                organized_samples['by_category'][category] = []
            organized_samples['by_category'][category].append(sample_info)
            
            # Organize by track type
            track_type = sample_info['track_type']
            if track_type and track_type != 'unknown':
                if track_type not in organized_samples['by_track_type']:
                    organized_samples['by_track_type'][track_type] = []
                organized_samples['by_track_type'][track_type].append(sample_info)
            
            # Organize by vibe
            vibe = sample_info['vibe']
            if vibe and vibe != 'unknown':
                if vibe not in organized_samples['by_vibe']:
                    organized_samples['by_vibe'][vibe] = []
                organized_samples['by_vibe'][vibe].append(sample_info)
            
            # Organize by genre tags
            for genre in sample_info['genre_tags']:
                if genre not in organized_samples['by_genre']:
                    organized_samples['by_genre'][genre] = []
                organized_samples['by_genre'][genre].append(sample_info)
        
        # Add summary statistics for AI context
        total_samples = len(_user_samples_metadata)
        organized_samples['summary'] = {
            'total_samples': total_samples,
            'categories': list(organized_samples['by_category'].keys()),
            'track_types': list(organized_samples['by_track_type'].keys()),
            'vibes': list(organized_samples['by_vibe'].keys()),
            'genres': list(organized_samples['by_genre'].keys()),
            'avg_bpm': sum([s.get('bpm', 0) for s in organized_samples['all_samples'] if s.get('bpm')]) / 
                      max(1, len([s for s in organized_samples['all_samples'] if s.get('bpm')])),
            'has_vocals': len(organized_samples['by_track_type'].get('vocals', [])) + 
                         len(organized_samples['by_track_type'].get('vocals_and_instrumentals', [])),
            'instrumentals_only': len(organized_samples['by_track_type'].get('instrumentals', []))
        }
        
        return organized_samples
        
    except Exception as e:
        current_app.logger.error(f"Error organizing samples for agents: {str(e)}")
        return {
            'by_category': {},
            'by_track_type': {},
            'by_vibe': {},
            'by_genre': {},
            'all_samples': [],
            'summary': {'total_samples': 0}
        }
