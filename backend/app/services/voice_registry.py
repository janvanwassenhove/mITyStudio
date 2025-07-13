"""
Voice Registry Module
Handles voice profile management and storage
"""

import json
import shutil
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
from flask import current_app

logger = logging.getLogger(__name__)


class VoiceRegistry:
    """Manages voice profiles and registry"""
    
    def __init__(self, voices_dir: Path):
        self.voices_dir = voices_dir
        self.voice_registry_file = self.voices_dir / 'registry.json'
        self.voice_registry = self._load_voice_registry()
    
    def _load_voice_registry(self) -> Dict[str, Any]:
        """Load voice registry from file"""
        if self.voice_registry_file.exists():
            try:
                with open(self.voice_registry_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading voice registry: {e}")
        
        # Return default builtin voices
        return {
            'voices': [
                {
                    'id': 'default',
                    'name': 'Default Voice',
                    'type': 'builtin',
                    'trained': True,
                    'language': 'en',
                    'created_at': '2024-01-01T00:00:00Z'
                },
                {
                    'id': 'male-01',
                    'name': 'Male Voice 1', 
                    'type': 'builtin',
                    'trained': True,
                    'language': 'en',
                    'created_at': '2024-01-01T00:00:00Z'
                },
                {
                    'id': 'female-01',
                    'name': 'Female Voice 1',
                    'type': 'builtin', 
                    'trained': True,
                    'language': 'en',
                    'created_at': '2024-01-01T00:00:00Z'
                }
            ]
        }

    def _save_voice_registry(self):
        """Save voice registry to file"""
        try:
            with open(self.voice_registry_file, 'w', encoding='utf-8') as f:
                json.dump(self.voice_registry, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving voice registry: {e}")

    def get_available_voices(self) -> List[Dict[str, Any]]:
        """Get list of available voice profiles"""
        return self.voice_registry.get('voices', [])

    def get_voice(self, voice_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific voice by ID"""
        voices = self.voice_registry.get('voices', [])
        return next((v for v in voices if v['id'] == voice_id), None)

    def add_voice(self, voice_data: Dict[str, Any]) -> bool:
        """Add a new voice to the registry"""
        try:
            voices = self.voice_registry.get('voices', [])
            
            # Check if voice ID already exists
            if any(v['id'] == voice_data['id'] for v in voices):
                logger.warning(f"Voice ID {voice_data['id']} already exists")
                return False
            
            voices.append(voice_data)
            self._save_voice_registry()
            logger.info(f"Added voice: {voice_data['name']} ({voice_data['id']})")
            return True
            
        except Exception as e:
            logger.error(f"Error adding voice: {e}")
            return False

    def update_voice(self, voice_id: str, updates: Dict[str, Any]) -> bool:
        """Update an existing voice in the registry"""
        try:
            voices = self.voice_registry.get('voices', [])
            
            for i, voice in enumerate(voices):
                if voice['id'] == voice_id:
                    voices[i].update(updates)
                    self._save_voice_registry()
                    logger.info(f"Updated voice: {voice_id}")
                    return True
            
            logger.warning(f"Voice not found for update: {voice_id}")
            return False
            
        except Exception as e:
            logger.error(f"Error updating voice: {e}")
            return False

    def delete_voice(self, voice_id: str) -> bool:
        """Delete a custom voice profile"""
        voices = self.voice_registry.get('voices', [])
        
        # Find the voice
        voice_index = None
        for i, voice in enumerate(voices):
            if voice['id'] == voice_id:
                # Don't allow deletion of builtin voices
                if voice.get('type') == 'builtin':
                    raise ValueError("Cannot delete builtin voices")
                voice_index = i
                break
        
        if voice_index is None:
            return False
        
        # Remove voice data
        voice_dir = self.voices_dir / voice_id
        if voice_dir.exists():
            shutil.rmtree(voice_dir)
        
        # Remove from registry
        voices.pop(voice_index)
        self._save_voice_registry()
        
        logger.info(f"Deleted voice: {voice_id}")
        return True

    def is_builtin_voice(self, voice_id: str) -> bool:
        """Check if a voice is a builtin voice"""
        voice = self.get_voice(voice_id)
        return voice and voice.get('type') == 'builtin'

    def get_custom_voices(self) -> List[Dict[str, Any]]:
        """Get only custom (non-builtin) voices"""
        voices = self.get_available_voices()
        return [v for v in voices if v.get('type') != 'builtin']

    def get_builtin_voices(self) -> List[Dict[str, Any]]:
        """Get only builtin voices"""
        voices = self.get_available_voices()
        return [v for v in voices if v.get('type') == 'builtin']
