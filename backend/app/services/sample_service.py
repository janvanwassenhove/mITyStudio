"""
Sample Service
Handles sample file storage, processing, and metadata management
"""

import os
import uuid
import shutil
from typing import Dict, List, Any, Optional
import numpy as np
import librosa
import soundfile as sf
from pydub import AudioSegment
from flask import current_app
from sqlalchemy.orm import sessionmaker
from sqlalchemy import or_, desc, asc
from app.models import Sample, Tag, sample_tags
from app import db
import json


class SampleService:
    """Service for sample management and storage"""
    
    ALLOWED_EXTENSIONS = {'wav', 'mp3', 'flac', 'aiff', 'm4a', 'ogg', 'aac'}
    SAMPLE_CATEGORIES = {
        'drums', 'bass', 'melodic', 'vocals', 'fx', 'loops',
        'oneshots', 'ambient', 'percussion', 'uncategorized'
    }
    
    def __init__(self):
        self.samples_dir = os.path.join(current_app.config.get('UPLOAD_FOLDER', 'uploads'), 'samples')
        self._ensure_samples_dir()
    
    def _ensure_samples_dir(self):
        """Ensure samples directory exists"""
        if not os.path.exists(self.samples_dir):
            os.makedirs(self.samples_dir)
    
    @staticmethod
    def allowed_file(filename: str) -> bool:
        """Check if file extension is allowed"""
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in SampleService.ALLOWED_EXTENSIONS
    
    def store_sample(self, file, user_id: str) -> Dict:
        """Store uploaded sample file and create database record"""
        if not self.allowed_file(file.filename):
            raise ValueError("File type not supported")
        
        # Generate unique sample ID and file path
        sample_id = str(uuid.uuid4())
        file_extension = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{sample_id}.{file_extension}"
        file_path = os.path.join(self.samples_dir, filename)
        
        # Save the file
        file.save(file_path)
        
        try:
            # Analyze audio file
            audio_data, sample_rate = librosa.load(file_path, sr=None)
            duration = len(audio_data) / sample_rate
            
            # Generate waveform data for visualization
            waveform_data = self._generate_waveform(audio_data, target_length=1000)
            
            # Extract audio features
            audio_features = self._extract_features(audio_data, sample_rate)
            
            # Get file info
            file_size = os.path.getsize(file_path)
            
            # Detect basic audio properties
            channels = 1 if len(audio_data.shape) == 1 else audio_data.shape[1]
            
            # Auto-categorize based on filename
            category = self._auto_categorize(file.filename)
            
            # Create database record
            sample = Sample(
                id=sample_id,
                name=os.path.splitext(file.filename)[0],
                original_filename=file.filename,
                file_path=file_path,
                file_size=file_size,
                duration=duration,
                sample_rate=sample_rate,
                channels=channels,
                category=category,
                waveform_data=waveform_data,
                audio_features=audio_features,
                user_id=user_id
            )
            
            db.session.add(sample)
            db.session.commit()
            
            return self._sample_to_dict(sample)
            
        except Exception as e:
            # Clean up file if database operation fails
            if os.path.exists(file_path):
                os.remove(file_path)
            raise e
    
    def get_user_samples(self, user_id: str, category: str = None, 
                        search: str = None, sort_by: str = 'created_at', 
                        sort_order: str = 'desc') -> List[Dict]:
        """Get all samples for a user with optional filtering"""
        query = db.session.query(Sample).filter(Sample.user_id == user_id)
        
        # Apply category filter
        if category and category != 'all':
            query = query.filter(Sample.category == category)
        
        # Apply search filter
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    Sample.name.ilike(search_term),
                    Sample.original_filename.ilike(search_term)
                )
            )
        
        # Apply sorting
        if hasattr(Sample, sort_by):
            sort_column = getattr(Sample, sort_by)
            if sort_order == 'desc':
                query = query.order_by(desc(sort_column))
            else:
                query = query.order_by(asc(sort_column))
        
        samples = query.all()
        return [self._sample_to_dict(sample) for sample in samples]
    
    def get_sample(self, sample_id: str, user_id: str) -> Optional[Dict]:
        """Get a specific sample by ID"""
        sample = db.session.query(Sample).filter(
            Sample.id == sample_id,
            Sample.user_id == user_id
        ).first()
        
        return self._sample_to_dict(sample) if sample else None
    
    def get_sample_file_path(self, sample_id: str, user_id: str) -> Optional[str]:
        """Get the file path for a sample"""
        sample = db.session.query(Sample).filter(
            Sample.id == sample_id,
            Sample.user_id == user_id
        ).first()
        
        return sample.file_path if sample else None
    
    def update_sample(self, sample_id: str, user_id: str, data: Dict) -> Optional[Dict]:
        """Update sample metadata"""
        sample = db.session.query(Sample).filter(
            Sample.id == sample_id,
            Sample.user_id == user_id
        ).first()
        
        if not sample:
            return None
        
        # Update allowed fields
        if 'name' in data:
            sample.name = data['name']
        if 'category' in data and data['category'] in self.SAMPLE_CATEGORIES:
            sample.category = data['category']
        if 'bpm' in data:
            sample.bpm = data['bpm']
        if 'key' in data:
            sample.key = data['key']
        
        # Handle tags
        if 'tags' in data:
            self._update_sample_tags(sample, data['tags'])
        
        db.session.commit()
        return self._sample_to_dict(sample)
    
    def delete_sample(self, sample_id: str, user_id: str) -> bool:
        """Delete a sample and its file"""
        sample = db.session.query(Sample).filter(
            Sample.id == sample_id,
            Sample.user_id == user_id
        ).first()
        
        if not sample:
            return False
        
        # Delete file
        try:
            if os.path.exists(sample.file_path):
                os.remove(sample.file_path)
        except Exception as e:
            current_app.logger.warning(f"Failed to delete sample file: {e}")
        
        # Delete database record
        db.session.delete(sample)
        db.session.commit()
        
        return True
    
    def bulk_delete_samples(self, sample_ids: List[str], user_id: str) -> int:
        """Delete multiple samples"""
        samples = db.session.query(Sample).filter(
            Sample.id.in_(sample_ids),
            Sample.user_id == user_id
        ).all()
        
        deleted_count = 0
        for sample in samples:
            # Delete file
            try:
                if os.path.exists(sample.file_path):
                    os.remove(sample.file_path)
            except Exception as e:
                current_app.logger.warning(f"Failed to delete sample file: {e}")
            
            # Delete database record
            db.session.delete(sample)
            deleted_count += 1
        
        db.session.commit()
        return deleted_count
    
    def _generate_waveform(self, audio_data: np.ndarray, target_length: int = 1000) -> List[float]:
        """Generate downsampled waveform data for visualization"""
        if len(audio_data) <= target_length:
            return audio_data.tolist()
        
        # Calculate the step size for downsampling
        step = len(audio_data) // target_length
        
        # Downsample by taking max values in each chunk for better visualization
        waveform = []
        for i in range(0, len(audio_data), step):
            chunk = audio_data[i:i + step]
            if len(chunk) > 0:
                waveform.append(float(np.max(np.abs(chunk))))
        
        return waveform[:target_length]
    
    def _extract_features(self, audio_data: np.ndarray, sample_rate: int) -> Dict:
        """Extract audio features for analysis"""
        try:
            # Basic tempo detection
            tempo, _ = librosa.beat.beat_track(y=audio_data, sr=sample_rate)
            
            # Spectral features
            spectral_centroids = librosa.feature.spectral_centroid(y=audio_data, sr=sample_rate)[0]
            spectral_rolloff = librosa.feature.spectral_rolloff(y=audio_data, sr=sample_rate)[0]
            zero_crossing_rate = librosa.feature.zero_crossing_rate(audio_data)[0]
            
            # RMS energy
            rms = librosa.feature.rms(y=audio_data)[0]
            
            return {
                'tempo': float(tempo),
                'spectral_centroid_mean': float(np.mean(spectral_centroids)),
                'spectral_rolloff_mean': float(np.mean(spectral_rolloff)),
                'zero_crossing_rate_mean': float(np.mean(zero_crossing_rate)),
                'rms_mean': float(np.mean(rms))
            }
        except Exception as e:
            current_app.logger.warning(f"Feature extraction failed: {e}")
            return {}
    
    def _auto_categorize(self, filename: str) -> str:
        """Auto-categorize sample based on filename"""
        filename_lower = filename.lower()
        
        if any(keyword in filename_lower for keyword in ['kick', 'bass', 'sub']):
            return 'bass'
        elif any(keyword in filename_lower for keyword in ['drum', 'snare', 'hat', 'cymbal']):
            return 'drums'
        elif any(keyword in filename_lower for keyword in ['vocal', 'voice', 'sung']):
            return 'vocals'
        elif any(keyword in filename_lower for keyword in ['loop', 'phrase']):
            return 'loops'
        elif any(keyword in filename_lower for keyword in ['fx', 'effect', 'sweep', 'rise']):
            return 'fx'
        elif any(keyword in filename_lower for keyword in ['lead', 'synth', 'pluck', 'chord']):
            return 'melodic'
        elif any(keyword in filename_lower for keyword in ['perc', 'shaker', 'clap']):
            return 'percussion'
        elif any(keyword in filename_lower for keyword in ['ambient', 'pad', 'texture']):
            return 'ambient'
        elif any(keyword in filename_lower for keyword in ['one', 'shot', 'hit']):
            return 'oneshots'
        else:
            return 'uncategorized'
    
    def _update_sample_tags(self, sample: Sample, tag_names: List[str]):
        """Update tags for a sample"""
        # Clear existing tags
        sample.tags.clear()
        
        # Add new tags
        for tag_name in tag_names:
            if not tag_name.strip():
                continue
                
            # Find or create tag
            tag = db.session.query(Tag).filter(Tag.name == tag_name.strip()).first()
            if not tag:
                tag = Tag(id=str(uuid.uuid4()), name=tag_name.strip())
                db.session.add(tag)
            
            sample.tags.append(tag)
    
    def _sample_to_dict(self, sample: Sample) -> Dict:
        """Convert sample model to dictionary"""
        return {
            'id': sample.id,
            'name': sample.name,
            'original_filename': sample.original_filename,
            'file_size': sample.file_size,
            'duration': sample.duration,
            'sample_rate': sample.sample_rate,
            'channels': sample.channels,
            'bpm': sample.bpm,
            'key': sample.key,
            'category': sample.category,
            'waveform_data': sample.waveform_data,
            'audio_features': sample.audio_features,
            'tags': [tag.name for tag in sample.tags],
            'created_at': sample.created_at.isoformat(),
            'updated_at': sample.updated_at.isoformat(),
            'url': f'/api/samples/{sample.id}/audio'  # URL to access the audio file
        }
