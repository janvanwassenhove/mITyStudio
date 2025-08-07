"""
User Sample Management API Routes
Handles user-uploaded sample metadata and integration with AI agents
"""

from flask import Blueprint, request, jsonify, current_app
from app.utils.decorators import handle_errors
import json
import os
from typing import Dict, List, Any

sample_bp = Blueprint('samples', __name__)

# In-memory storage for sample metadata (in production, use database)
_user_samples_metadata = {}

@sample_bp.route('/metadata', methods=['POST'])
@handle_errors
def store_sample_metadata():
    """
    Store metadata for user-uploaded samples from frontend
    Expected format matches LocalSample interface from frontend
    """
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    # Validate required fields
    required_fields = ['id', 'name', 'category']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    try:
        # Store the metadata
        sample_id = data['id']
        _user_samples_metadata[sample_id] = {
            'id': data['id'],
            'name': data['name'],
            'duration': data.get('duration'),
            'category': data['category'],
            'tags': data.get('tags', []),
            'bpm': data.get('bpm'),
            'key': data.get('key'),
            'waveform': data.get('waveform', []),
            'created_at': data.get('createdAt'),
            'updated_at': data.get('updatedAt')
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
    Search user samples by metadata criteria
    """
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No search criteria provided'}), 400
    
    try:
        # Search criteria
        category = data.get('category')
        tags = data.get('tags', [])
        bpm_range = data.get('bpm_range')  # [min, max]
        key = data.get('key')
        duration_range = data.get('duration_range')  # [min, max]
        
        results = []
        
        for sample_id, metadata in _user_samples_metadata.items():
            # Check category
            if category and metadata.get('category') != category:
                continue
            
            # Check tags
            if tags and not any(tag in metadata.get('tags', []) for tag in tags):
                continue
            
            # Check BPM range
            if bpm_range and metadata.get('bpm'):
                bpm = metadata['bpm']
                if bpm < bpm_range[0] or bpm > bpm_range[1]:
                    continue
            
            # Check key
            if key and metadata.get('key') != key:
                continue
            
            # Check duration range
            if duration_range and metadata.get('duration'):
                duration = metadata['duration']
                if duration < duration_range[0] or duration > duration_range[1]:
                    continue
            
            results.append(metadata)
        
        return jsonify({
            'results': results,
            'count': len(results),
            'search_criteria': data
        })
        
    except Exception as e:
        current_app.logger.error(f"Error searching samples: {str(e)}")
        return jsonify({'error': 'Failed to search samples'}), 500


def get_user_samples_for_agents() -> Dict[str, Any]:
    """
    Get formatted user sample metadata for AI agents
    Returns organized data structure for music generation
    """
    try:
        # Organize samples by category
        organized_samples = {}
        
        for sample_id, metadata in _user_samples_metadata.items():
            category = metadata.get('category', 'uncategorized')
            
            if category not in organized_samples:
                organized_samples[category] = []
            
            # Create agent-friendly format
            sample_info = {
                'name': metadata['name'],
                'id': sample_id,
                'tags': metadata.get('tags', []),
                'bpm': metadata.get('bpm'),
                'key': metadata.get('key'),
                'duration': metadata.get('duration'),
                'category': category
            }
            
            organized_samples[category].append(sample_info)
        
        return organized_samples
        
    except Exception as e:
        current_app.logger.error(f"Error organizing samples for agents: {str(e)}")
        return {}
