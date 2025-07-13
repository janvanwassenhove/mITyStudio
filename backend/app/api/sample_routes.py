"""
Sample API Routes
Handles sample upload, storage, retrieval, and management
"""

from flask import Blueprint, request, jsonify, current_app, send_file
from werkzeug.utils import secure_filename
from app.services.sample_service import SampleService
from app.utils.decorators import handle_errors
from app.models import Sample, Tag
from app import db
import os
import uuid

sample_bp = Blueprint('samples', __name__)


@sample_bp.route('/upload', methods=['POST'])
@handle_errors
def upload_samples():
    """
    Upload and store multiple audio samples
    """
    if 'files' not in request.files:
        return jsonify({'error': 'No files provided'}), 400
    
    files = request.files.getlist('files')
    if not files or all(file.filename == '' for file in files):
        return jsonify({'error': 'No files selected'}), 400
    
    try:
        sample_service = SampleService()
        results = []
        
        # Get user_id from session/auth (for now using demo user)
        user_id = request.headers.get('X-User-ID', 'demo-user')
        
        for file in files:
            if file and sample_service.allowed_file(file.filename):
                result = sample_service.store_sample(file, user_id)
                results.append(result)
        
        return jsonify({
            'success': True,
            'samples': results,
            'uploaded_count': len(results)
        })
        
    except Exception as e:
        current_app.logger.error(f"Sample upload error: {str(e)}")
        return jsonify({'error': 'Failed to upload samples'}), 500


@sample_bp.route('/', methods=['GET'])
@handle_errors
def get_samples():
    """
    Get all samples for the current user with filtering
    """
    try:
        # Get user_id from session/auth
        user_id = request.headers.get('X-User-ID', 'demo-user')
        
        # Query parameters for filtering
        category = request.args.get('category')
        search = request.args.get('search')
        sort_by = request.args.get('sort_by', 'created_at')
        sort_order = request.args.get('sort_order', 'desc')
        
        sample_service = SampleService()
        samples = sample_service.get_user_samples(
            user_id, category, search, sort_by, sort_order
        )
        
        return jsonify({
            'success': True,
            'samples': samples,
            'total_count': len(samples)
        })
        
    except Exception as e:
        current_app.logger.error(f"Get samples error: {str(e)}")
        return jsonify({'error': 'Failed to retrieve samples'}), 500


@sample_bp.route('/<sample_id>', methods=['GET'])
@handle_errors
def get_sample(sample_id):
    """
    Get a specific sample by ID
    """
    try:
        user_id = request.headers.get('X-User-ID', 'demo-user')
        sample_service = SampleService()
        sample = sample_service.get_sample(sample_id, user_id)
        
        if not sample:
            return jsonify({'error': 'Sample not found'}), 404
            
        return jsonify({
            'success': True,
            'sample': sample
        })
        
    except Exception as e:
        current_app.logger.error(f"Get sample error: {str(e)}")
        return jsonify({'error': 'Failed to retrieve sample'}), 500


@sample_bp.route('/<sample_id>/audio', methods=['GET'])
@handle_errors
def get_sample_audio(sample_id):
    """
    Serve the actual audio file for a sample
    """
    try:
        user_id = request.headers.get('X-User-ID', 'demo-user')
        sample_service = SampleService()
        file_path = sample_service.get_sample_file_path(sample_id, user_id)
        
        if not file_path or not os.path.exists(file_path):
            return jsonify({'error': 'Sample file not found'}), 404
            
        return send_file(file_path)
        
    except Exception as e:
        current_app.logger.error(f"Get sample audio error: {str(e)}")
        return jsonify({'error': 'Failed to retrieve sample audio'}), 500


@sample_bp.route('/<sample_id>', methods=['PUT'])
@handle_errors
def update_sample(sample_id):
    """
    Update sample metadata
    """
    try:
        user_id = request.headers.get('X-User-ID', 'demo-user')
        data = request.get_json()
        
        sample_service = SampleService()
        updated_sample = sample_service.update_sample(sample_id, user_id, data)
        
        if not updated_sample:
            return jsonify({'error': 'Sample not found'}), 404
            
        return jsonify({
            'success': True,
            'sample': updated_sample
        })
        
    except Exception as e:
        current_app.logger.error(f"Update sample error: {str(e)}")
        return jsonify({'error': 'Failed to update sample'}), 500


@sample_bp.route('/<sample_id>', methods=['DELETE'])
@handle_errors
def delete_sample(sample_id):
    """
    Delete a sample
    """
    try:
        user_id = request.headers.get('X-User-ID', 'demo-user')
        sample_service = SampleService()
        
        if sample_service.delete_sample(sample_id, user_id):
            return jsonify({
                'success': True,
                'message': 'Sample deleted successfully'
            })
        else:
            return jsonify({'error': 'Sample not found'}), 404
            
    except Exception as e:
        current_app.logger.error(f"Delete sample error: {str(e)}")
        return jsonify({'error': 'Failed to delete sample'}), 500


@sample_bp.route('/categories', methods=['GET'])
@handle_errors
def get_categories():
    """
    Get all available sample categories
    """
    categories = [
        'drums', 'bass', 'melodic', 'vocals', 'fx', 'loops',
        'oneshots', 'ambient', 'percussion', 'uncategorized'
    ]
    
    return jsonify({
        'success': True,
        'categories': categories
    })


@sample_bp.route('/tags', methods=['GET'])
@handle_errors
def get_tags():
    """
    Get all available tags
    """
    try:
        tags = db.session.query(Tag).all()
        tag_list = [{'id': tag.id, 'name': tag.name} for tag in tags]
        
        return jsonify({
            'success': True,
            'tags': tag_list
        })
        
    except Exception as e:
        current_app.logger.error(f"Get tags error: {str(e)}")
        return jsonify({'error': 'Failed to retrieve tags'}), 500


@sample_bp.route('/bulk-delete', methods=['POST'])
@handle_errors
def bulk_delete_samples():
    """
    Delete multiple samples at once
    """
    try:
        user_id = request.headers.get('X-User-ID', 'demo-user')
        data = request.get_json()
        sample_ids = data.get('sample_ids', [])
        
        if not sample_ids:
            return jsonify({'error': 'No sample IDs provided'}), 400
            
        sample_service = SampleService()
        deleted_count = sample_service.bulk_delete_samples(sample_ids, user_id)
        
        return jsonify({
            'success': True,
            'deleted_count': deleted_count,
            'message': f'Deleted {deleted_count} samples'
        })
        
    except Exception as e:
        current_app.logger.error(f"Bulk delete error: {str(e)}")
        return jsonify({'error': 'Failed to delete samples'}), 500
