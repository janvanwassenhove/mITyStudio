"""
Project Service
Handles project management, tracks, and song structure
"""

import uuid
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from flask import current_app


class ProjectService:
    """Service for managing music projects"""
    
    def __init__(self):
        # In a real implementation, this would use a database
        # For demo purposes, we'll use in-memory storage
        self.projects = {}
        self.tracks = {}
        self.clips = {}
    
    def get_user_projects(self, user_id: str, page: int = 1, per_page: int = 10) -> Dict:
        """Get all projects for a user"""
        user_projects = [p for p in self.projects.values() if p.get('user_id') == user_id]
        
        # Sort by updated date
        user_projects.sort(key=lambda x: x.get('updated_at', ''), reverse=True)
        
        # Paginate
        start = (page - 1) * per_page
        end = start + per_page
        paginated_projects = user_projects[start:end]
        
        return {
            'items': paginated_projects,
            'total': len(user_projects),
            'pages': (len(user_projects) + per_page - 1) // per_page
        }
    
    def create_project(self, name: str, description: str = '', genre: str = 'pop',
                      tempo: int = 120, key: str = 'C', time_signature: str = '4/4',
                      user_id: str = 'default') -> Dict:
        """Create a new project"""
        project_id = str(uuid.uuid4())
        
        project = {
            'id': project_id,
            'name': name,
            'description': description,
            'genre': genre,
            'tempo': tempo,
            'key': key,
            'time_signature': time_signature,
            'user_id': user_id,
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat(),
            'track_count': 0,
            'duration': 0,
            'settings': {
                'master_volume': 0.8,
                'master_effects': {
                    'reverb': 0.0,
                    'delay': 0.0,
                    'compressor': 0.0,
                    'limiter': 0.8
                }
            }
        }
        
        self.projects[project_id] = project
        return project
    
    def get_project(self, project_id: str) -> Optional[Dict]:
        """Get a specific project"""
        project = self.projects.get(project_id)
        if not project:
            return None
        
        # Include tracks in project data
        project_tracks = self.get_project_tracks(project_id)
        project['tracks'] = project_tracks
        
        return project
    
    def update_project(self, project_id: str, updates: Dict) -> Optional[Dict]:
        """Update a project"""
        if project_id not in self.projects:
            return None
        
        project = self.projects[project_id]
        
        # Update allowed fields
        updatable_fields = [
            'name', 'description', 'genre', 'tempo', 'key', 
            'time_signature', 'settings', 'duration'
        ]
        
        for field in updatable_fields:
            if field in updates:
                project[field] = updates[field]
        
        project['updated_at'] = datetime.utcnow().isoformat()
        
        self.projects[project_id] = project
        return project
    
    def delete_project(self, project_id: str) -> bool:
        """Delete a project"""
        if project_id not in self.projects:
            return False
        
        # Delete associated tracks and clips
        project_tracks = [t for t in self.tracks.values() if t.get('project_id') == project_id]
        for track in project_tracks:
            self.delete_track(project_id, track['id'])
        
        # Delete project
        del self.projects[project_id]
        return True
    
    def get_project_tracks(self, project_id: str) -> List[Dict]:
        """Get all tracks for a project"""
        project_tracks = [t for t in self.tracks.values() if t.get('project_id') == project_id]
        
        # Sort by order
        project_tracks.sort(key=lambda x: x.get('order', 0))
        
        # Include clips for each track
        for track in project_tracks:
            track_clips = [c for c in self.clips.values() if c.get('track_id') == track['id']]
            track_clips.sort(key=lambda x: x.get('start_time', 0))
            track['clips'] = track_clips
        
        return project_tracks
    
    def add_track(self, project_id: str, name: str, instrument: str = 'piano',
                 volume: float = 0.8, pan: float = 0.0, muted: bool = False,
                 soloed: bool = False) -> Dict:
        """Add a track to a project"""
        if project_id not in self.projects:
            raise ValueError(f"Project not found: {project_id}")
        
        track_id = str(uuid.uuid4())
        
        # Get current track count for ordering
        existing_tracks = [t for t in self.tracks.values() if t.get('project_id') == project_id]
        order = len(existing_tracks)
        
        track = {
            'id': track_id,
            'project_id': project_id,
            'name': name,
            'instrument': instrument,
            'volume': volume,
            'pan': pan,
            'muted': muted,
            'soloed': soloed,
            'order': order,
            'effects': {
                'reverb': 0.0,
                'delay': 0.0,
                'distortion': 0.0,
                'eq': {
                    'low': 0.0,
                    'mid': 0.0,
                    'high': 0.0
                }
            },
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat()
        }
        
        self.tracks[track_id] = track
        
        # Update project track count
        self.projects[project_id]['track_count'] = len(existing_tracks) + 1
        self.projects[project_id]['updated_at'] = datetime.utcnow().isoformat()
        
        return track
    
    def update_track(self, project_id: str, track_id: str, updates: Dict) -> Optional[Dict]:
        """Update a track"""
        if track_id not in self.tracks:
            return None
        
        track = self.tracks[track_id]
        
        # Verify track belongs to project
        if track.get('project_id') != project_id:
            return None
        
        # Update allowed fields
        updatable_fields = [
            'name', 'instrument', 'volume', 'pan', 'muted', 'soloed',
            'effects', 'order'
        ]
        
        for field in updatable_fields:
            if field in updates:
                track[field] = updates[field]
        
        track['updated_at'] = datetime.utcnow().isoformat()
        
        self.tracks[track_id] = track
        
        # Update project timestamp
        if project_id in self.projects:
            self.projects[project_id]['updated_at'] = datetime.utcnow().isoformat()
        
        return track
    
    def delete_track(self, project_id: str, track_id: str) -> bool:
        """Delete a track"""
        if track_id not in self.tracks:
            return False
        
        track = self.tracks[track_id]
        
        # Verify track belongs to project
        if track.get('project_id') != project_id:
            return False
        
        # Delete associated clips
        track_clips = [c for c in self.clips.values() if c.get('track_id') == track_id]
        for clip in track_clips:
            del self.clips[clip['id']]
        
        # Delete track
        del self.tracks[track_id]
        
        # Update project track count
        if project_id in self.projects:
            remaining_tracks = [t for t in self.tracks.values() if t.get('project_id') == project_id]
            self.projects[project_id]['track_count'] = len(remaining_tracks)
            self.projects[project_id]['updated_at'] = datetime.utcnow().isoformat()
        
        return True
    
    def add_clip(self, project_id: str, track_id: str, start_time: float,
                duration: float, clip_type: str = 'synth', instrument: str = 'piano',
                **kwargs) -> Dict:
        """Add a clip to a track"""
        if track_id not in self.tracks:
            raise ValueError(f"Track not found: {track_id}")
        
        track = self.tracks[track_id]
        if track.get('project_id') != project_id:
            raise ValueError(f"Track does not belong to project: {project_id}")
        
        clip_id = str(uuid.uuid4())
        
        clip = {
            'id': clip_id,
            'track_id': track_id,
            'start_time': start_time,
            'duration': duration,
            'type': clip_type,
            'instrument': instrument,
            'volume': kwargs.get('volume', 0.7),
            'effects': kwargs.get('effects', {
                'reverb': 0.0,
                'delay': 0.0,
                'distortion': 0.0
            }),
            'midi_data': kwargs.get('midi_data', []),
            'audio_file_id': kwargs.get('audio_file_id'),
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat()
        }
        
        self.clips[clip_id] = clip
        
        # Update project duration if needed
        clip_end_time = start_time + duration
        if project_id in self.projects:
            current_duration = self.projects[project_id].get('duration', 0)
            if clip_end_time > current_duration:
                self.projects[project_id]['duration'] = clip_end_time
            self.projects[project_id]['updated_at'] = datetime.utcnow().isoformat()
        
        return clip
    
    def export_project(self, project_id: str, format_type: str = 'json',
                      include_audio: bool = False) -> Dict:
        """Export project data"""
        project = self.get_project(project_id)
        
        if not project:
            raise ValueError(f"Project not found: {project_id}")
        
        if format_type == 'json':
            # Export as JSON
            export_data = {
                'project': project,
                'format': 'mITyStudio Project',
                'version': '1.0',
                'exported_at': datetime.utcnow().isoformat()
            }
            
            if not include_audio:
                # Remove audio file references
                for track in export_data['project'].get('tracks', []):
                    for clip in track.get('clips', []):
                        if 'audio_file_id' in clip:
                            del clip['audio_file_id']
            
            return export_data
        
        else:
            raise ValueError(f"Unsupported export format: {format_type}")
    
    def import_project(self, import_data: Dict, user_id: str = 'default') -> Dict:
        """Import project from exported data"""
        if import_data.get('format') != 'mITyStudio Project':
            raise ValueError("Invalid project format")
        
        project_data = import_data.get('project', {})
        
        # Create new project
        new_project = self.create_project(
            name=f"{project_data.get('name', 'Imported Project')} (Copy)",
            description=project_data.get('description', ''),
            genre=project_data.get('genre', 'pop'),
            tempo=project_data.get('tempo', 120),
            key=project_data.get('key', 'C'),
            time_signature=project_data.get('time_signature', '4/4'),
            user_id=user_id
        )
        
        project_id = new_project['id']
        
        # Import tracks and clips
        for track_data in project_data.get('tracks', []):
            new_track = self.add_track(
                project_id=project_id,
                name=track_data.get('name', 'Imported Track'),
                instrument=track_data.get('instrument', 'piano'),
                volume=track_data.get('volume', 0.8),
                pan=track_data.get('pan', 0.0),
                muted=track_data.get('muted', False),
                soloed=track_data.get('soloed', False)
            )
            
            # Import clips
            for clip_data in track_data.get('clips', []):
                self.add_clip(
                    project_id=project_id,
                    track_id=new_track['id'],
                    start_time=clip_data.get('start_time', 0),
                    duration=clip_data.get('duration', 4),
                    clip_type=clip_data.get('type', 'synth'),
                    instrument=clip_data.get('instrument', 'piano'),
                    volume=clip_data.get('volume', 0.7),
                    effects=clip_data.get('effects', {}),
                    midi_data=clip_data.get('midi_data', [])
                )
        
        return new_project
