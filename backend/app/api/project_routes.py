"""
Project Management API Routes
Handles project CRUD operations, tracks, and song structure
"""

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.services.project_service import ProjectService
from app.utils.decorators import handle_errors
from datetime import datetime

project_bp = Blueprint('projects', __name__)


@project_bp.route('/', methods=['GET'])
@handle_errors
def get_projects():
    """
    Get all projects for the user
    """
    user_id = request.args.get('user_id', 'default')  # For demo purposes
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    try:
        project_service = ProjectService()
        projects = project_service.get_user_projects(
            user_id=user_id,
            page=page,
            per_page=per_page
        )
        
        return jsonify({
            'projects': projects['items'],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': projects['total'],
                'pages': projects['pages']
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Get projects error: {str(e)}")
        return jsonify({'error': 'Failed to retrieve projects'}), 500


@project_bp.route('/', methods=['POST'])
@handle_errors
def create_project():
    """
    Create a new project
    """
    data = request.get_json()
    name = data.get('name', 'Untitled Project')
    description = data.get('description', '')
    genre = data.get('genre', 'pop')
    tempo = data.get('tempo', 120)
    key = data.get('key', 'C')
    time_signature = data.get('time_signature', '4/4')
    user_id = data.get('user_id', 'default')
    
    try:
        project_service = ProjectService()
        project = project_service.create_project(
            name=name,
            description=description,
            genre=genre,
            tempo=tempo,
            key=key,
            time_signature=time_signature,
            user_id=user_id
        )
        
        return jsonify({
            'project': project,
            'message': 'Project created successfully'
        }), 201
        
    except Exception as e:
        current_app.logger.error(f"Create project error: {str(e)}")
        return jsonify({'error': 'Failed to create project'}), 500


@project_bp.route('/<project_id>', methods=['GET'])
@handle_errors
def get_project(project_id):
    """
    Get a specific project
    """
    try:
        project_service = ProjectService()
        project = project_service.get_project(project_id)
        
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        return jsonify({'project': project})
        
    except Exception as e:
        current_app.logger.error(f"Get project error: {str(e)}")
        return jsonify({'error': 'Failed to retrieve project'}), 500


@project_bp.route('/<project_id>', methods=['PUT'])
@handle_errors
def update_project(project_id):
    """
    Update a project
    """
    data = request.get_json()
    
    try:
        project_service = ProjectService()
        project = project_service.update_project(project_id, data)
        
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        return jsonify({
            'project': project,
            'message': 'Project updated successfully'
        })
        
    except Exception as e:
        current_app.logger.error(f"Update project error: {str(e)}")
        return jsonify({'error': 'Failed to update project'}), 500


@project_bp.route('/<project_id>', methods=['DELETE'])
@handle_errors
def delete_project(project_id):
    """
    Delete a project
    """
    try:
        project_service = ProjectService()
        success = project_service.delete_project(project_id)
        
        if not success:
            return jsonify({'error': 'Project not found'}), 404
        
        return jsonify({'message': 'Project deleted successfully'})
        
    except Exception as e:
        current_app.logger.error(f"Delete project error: {str(e)}")
        return jsonify({'error': 'Failed to delete project'}), 500


@project_bp.route('/<project_id>/tracks', methods=['GET'])
@handle_errors
def get_tracks(project_id):
    """
    Get all tracks for a project
    """
    try:
        project_service = ProjectService()
        tracks = project_service.get_project_tracks(project_id)
        
        return jsonify({'tracks': tracks})
        
    except Exception as e:
        current_app.logger.error(f"Get tracks error: {str(e)}")
        return jsonify({'error': 'Failed to retrieve tracks'}), 500


@project_bp.route('/<project_id>/tracks', methods=['POST'])
@handle_errors
def add_track(project_id):
    """
    Add a track to a project
    """
    data = request.get_json()
    name = data.get('name', 'New Track')
    instrument = data.get('instrument', 'piano')
    volume = data.get('volume', 0.8)
    pan = data.get('pan', 0.0)
    muted = data.get('muted', False)
    soloed = data.get('soloed', False)
    
    try:
        project_service = ProjectService()
        track = project_service.add_track(
            project_id=project_id,
            name=name,
            instrument=instrument,
            volume=volume,
            pan=pan,
            muted=muted,
            soloed=soloed
        )
        
        return jsonify({
            'track': track,
            'message': 'Track added successfully'
        }), 201
        
    except Exception as e:
        current_app.logger.error(f"Add track error: {str(e)}")
        return jsonify({'error': 'Failed to add track'}), 500


@project_bp.route('/<project_id>/tracks/<track_id>', methods=['PUT'])
@handle_errors
def update_track(project_id, track_id):
    """
    Update a track
    """
    data = request.get_json()
    
    try:
        project_service = ProjectService()
        track = project_service.update_track(project_id, track_id, data)
        
        if not track:
            return jsonify({'error': 'Track not found'}), 404
        
        return jsonify({
            'track': track,
            'message': 'Track updated successfully'
        })
        
    except Exception as e:
        current_app.logger.error(f"Update track error: {str(e)}")
        return jsonify({'error': 'Failed to update track'}), 500


@project_bp.route('/<project_id>/tracks/<track_id>', methods=['DELETE'])
@handle_errors
def delete_track(project_id, track_id):
    """
    Delete a track
    """
    try:
        project_service = ProjectService()
        success = project_service.delete_track(project_id, track_id)
        
        if not success:
            return jsonify({'error': 'Track not found'}), 404
        
        return jsonify({'message': 'Track deleted successfully'})
        
    except Exception as e:
        current_app.logger.error(f"Delete track error: {str(e)}")
        return jsonify({'error': 'Failed to delete track'}), 500


@project_bp.route('/<project_id>/clips', methods=['POST'])
@handle_errors
def add_clip(project_id):
    """
    Add a clip to a track
    """
    data = request.get_json()
    track_id = data.get('track_id')
    start_time = data.get('start_time', 0)
    duration = data.get('duration', 4)
    clip_type = data.get('type', 'synth')
    instrument = data.get('instrument', 'piano')
    
    if not track_id:
        return jsonify({'error': 'Track ID is required'}), 400
    
    try:
        project_service = ProjectService()
        clip = project_service.add_clip(
            project_id=project_id,
            track_id=track_id,
            start_time=start_time,
            duration=duration,
            clip_type=clip_type,
            instrument=instrument,
            **data
        )
        
        return jsonify({
            'clip': clip,
            'message': 'Clip added successfully'
        }), 201
        
    except Exception as e:
        current_app.logger.error(f"Add clip error: {str(e)}")
        return jsonify({'error': 'Failed to add clip'}), 500


@project_bp.route('/<project_id>/export', methods=['POST'])
@handle_errors
def export_project(project_id):
    """
    Export project data
    """
    data = request.get_json()
    format_type = data.get('format', 'json')
    include_audio = data.get('include_audio', False)
    
    try:
        project_service = ProjectService()
        export_data = project_service.export_project(
            project_id=project_id,
            format_type=format_type,
            include_audio=include_audio
        )
        
        return jsonify({
            'export_data': export_data,
            'format': format_type,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        current_app.logger.error(f"Export project error: {str(e)}")
        return jsonify({'error': 'Failed to export project'}), 500


@project_bp.route('/from-song-structure', methods=['POST'])
@handle_errors
def create_project_from_song_structure():
    """
    Create a new project from a generated song structure
    """
    data = request.get_json()
    song_structure = data.get('song_structure')
    user_id = data.get('user_id', 'default')
    
    if not song_structure:
        return jsonify({'error': 'Song structure is required'}), 400
    
    try:
        project_service = ProjectService()
        project = project_service.create_project_from_song_structure(
            song_structure=song_structure,
            user_id=user_id
        )
        
        return jsonify({
            'project': project,
            'message': 'Project created successfully from song structure'
        })
        
    except Exception as e:
        current_app.logger.error(f"Create project from song structure error: {str(e)}")
        return jsonify({'error': f'Failed to create project: {str(e)}'}), 500


@project_bp.route('/<project_id>/update-from-song-structure', methods=['PUT'])
@handle_errors
def update_project_from_song_structure(project_id):
    """
    Update an existing project with a new song structure
    """
    data = request.get_json()
    song_structure = data.get('song_structure')
    
    if not song_structure:
        return jsonify({'error': 'Song structure is required'}), 400
    
    try:
        project_service = ProjectService()
        project = project_service.update_project_from_song_structure(
            project_id=project_id,
            song_structure=song_structure
        )
        
        return jsonify({
            'project': project,
            'message': 'Project updated successfully from song structure'
        })
        
    except Exception as e:
        current_app.logger.error(f"Update project from song structure error: {str(e)}")
        return jsonify({'error': f'Failed to update project: {str(e)}'}), 500
