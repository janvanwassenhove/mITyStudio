"""
Score Processing Service
Handles musical score sheet and tablature processing, OCR, and JSON generation
"""

import os
import json
import uuid
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import logging
from flask import current_app

class ScoreService:
    """Service for processing musical scores and tablatures"""
    
    def __init__(self):
        self.upload_dir = Path(os.getenv('UPLOAD_DIR', 'uploads'))
        self.scores_dir = self.upload_dir / 'scores'
        self.scores_dir.mkdir(parents=True, exist_ok=True)
        
        # Metadata storage file
        self.metadata_file = self.scores_dir / 'scores_metadata.json'
        self.metadata = self._load_metadata()
    
    def _get_logger(self):
        """Get logger that works both inside and outside Flask context"""
        try:
            return current_app.logger
        except RuntimeError:
            return logging.getLogger(__name__)
    
    def _load_metadata(self) -> Dict:
        """Load scores metadata from file"""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                self._get_logger().error(f"Error loading scores metadata: {e}")
        
        return {}
    
    def _save_metadata(self):
        """Save scores metadata to file"""
        try:
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(self.metadata, f, indent=2, default=str)
        except Exception as e:
            self._get_logger().error(f"Error saving scores metadata: {e}")
    
    def process_score_file(self, file) -> Dict[str, Any]:
        """
        Process an uploaded score file
        """
        file_id = str(uuid.uuid4())
        filename = file.filename
        file_extension = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
        
        # Create directory for this score
        score_dir = self.scores_dir / file_id
        score_dir.mkdir(exist_ok=True)
        
        # Save the uploaded file
        file_path = score_dir / f"original.{file_extension}"
        file.save(file_path)
        
        # Determine file category and processing method
        category = self._get_file_category(filename)
        
        try:
            # Process based on file type
            analysis = self._analyze_score_file(file_path, category)
            
            # Store metadata
            metadata = {
                'file_id': file_id,
                'original_filename': filename,
                'file_path': str(file_path),
                'file_size': file_path.stat().st_size,
                'category': category,
                'extension': file_extension,
                'upload_date': datetime.utcnow().isoformat(),
                'analysis': analysis,
                'status': 'processed'
            }
            
            self.metadata[file_id] = metadata
            self._save_metadata()
            
            return {
                'file_id': file_id,
                'filename': filename,
                'category': category,
                'status': 'success',
                'analysis': analysis,
                'message': f'Successfully processed {category} file'
            }
            
        except Exception as e:
            self._get_logger().error(f"Error processing score file {filename}: {e}")
            
            # Store error metadata
            error_metadata = {
                'file_id': file_id,
                'original_filename': filename,
                'file_path': str(file_path),
                'category': category,
                'extension': file_extension,
                'upload_date': datetime.utcnow().isoformat(),
                'status': 'error',
                'error': str(e)
            }
            
            self.metadata[file_id] = error_metadata
            self._save_metadata()
            
            return {
                'file_id': file_id,
                'filename': filename,
                'category': category,
                'status': 'error',
                'error': str(e),
                'message': f'Failed to process {category} file: {str(e)}'
            }
    
    def _get_file_category(self, filename: str) -> str:
        """Determine the category of the file"""
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
    
    def _analyze_score_file(self, file_path: Path, category: str) -> Dict[str, Any]:
        """
        Analyze a score file based on its category
        """
        if category == 'sheet_music':
            return self._analyze_sheet_music(file_path)
        elif category == 'tablature':
            return self._analyze_tablature(file_path)
        elif category == 'musicxml':
            return self._analyze_musicxml(file_path)
        elif category == 'midi':
            return self._analyze_midi(file_path)
        elif category == 'notation':
            return self._analyze_notation(file_path)
        elif category == 'text_tab':
            return self._analyze_text_tab(file_path)
        else:
            return {'error': 'Unsupported file format'}
    
    def _analyze_sheet_music(self, file_path: Path) -> Dict[str, Any]:
        """
        Analyze sheet music images/PDFs using OCR and music notation recognition
        """
        # For now, return basic analysis - can be enhanced with actual OCR/OMR libraries
        analysis = {
            'type': 'sheet_music',
            'detected_elements': {
                'staff_lines': 'detected',
                'clefs': ['treble', 'bass'],
                'key_signature': 'C major (estimated)',
                'time_signature': '4/4 (estimated)',
                'notes': 'multiple',
                'chords': 'present'
            },
            'estimated_tempo': 120,
            'estimated_key': 'C',
            'difficulty_level': 'intermediate',
            'suggested_instruments': ['piano', 'guitar', 'vocals'],
            'note': 'Basic analysis - OCR/OMR processing can be enhanced with specialized libraries'
        }
        
        return analysis
    
    def _analyze_tablature(self, file_path: Path) -> Dict[str, Any]:
        """
        Analyze guitar tablature files (Guitar Pro, etc.)
        """
        # Basic analysis for tablature files
        analysis = {
            'type': 'tablature',
            'instrument': 'guitar',
            'tuning': 'standard (E-A-D-G-B-E)',
            'estimated_key': 'Em',
            'estimated_tempo': 120,
            'fret_positions': [0, 12],  # Range of fret positions used
            'techniques': ['picking', 'fretting'],
            'difficulty_level': 'intermediate',
            'suggested_instruments': ['guitar', 'electric_guitar'],
            'note': 'Tablature analysis - can be enhanced with Guitar Pro SDK or similar libraries'
        }
        
        return analysis
    
    def _analyze_musicxml(self, file_path: Path) -> Dict[str, Any]:
        """
        Analyze MusicXML files
        """
        try:
            # Basic XML parsing to extract musical information
            import xml.etree.ElementTree as ET
            
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            # Extract basic information
            title = ""
            composer = ""
            key = "C"
            time_signature = "4/4"
            tempo = 120
            
            # Look for title and composer in work element
            work = root.find('.//work')
            if work is not None:
                work_title = work.find('work-title')
                if work_title is not None:
                    title = work_title.text
            
            identification = root.find('.//identification')
            if identification is not None:
                creator = identification.find('.//creator[@type="composer"]')
                if creator is not None:
                    composer = creator.text
            
            # Look for key signature
            key_elem = root.find('.//key')
            if key_elem is not None:
                fifths = key_elem.find('fifths')
                if fifths is not None:
                    # Convert fifths to key name (simplified)
                    key_map = {0: 'C', 1: 'G', 2: 'D', 3: 'A', 4: 'E', 5: 'B', 6: 'F#',
                              -1: 'F', -2: 'Bb', -3: 'Eb', -4: 'Ab', -5: 'Db', -6: 'Gb'}
                    key = key_map.get(int(fifths.text), 'C')
            
            # Look for time signature
            time_elem = root.find('.//time')
            if time_elem is not None:
                beats = time_elem.find('beats')
                beat_type = time_elem.find('beat-type')
                if beats is not None and beat_type is not None:
                    time_signature = f"{beats.text}/{beat_type.text}"
            
            # Count parts/instruments
            parts = root.findall('.//part-list/score-part')
            instruments = [part.find('part-name').text if part.find('part-name') is not None else 'Unknown' 
                          for part in parts]
            
            analysis = {
                'type': 'musicxml',
                'title': title,
                'composer': composer,
                'key': key,
                'time_signature': time_signature,
                'estimated_tempo': tempo,
                'instruments': instruments,
                'parts_count': len(parts),
                'difficulty_level': 'intermediate',
                'note': 'MusicXML parsing successful'
            }
            
        except Exception as e:
            analysis = {
                'type': 'musicxml',
                'error': f'XML parsing error: {str(e)}',
                'estimated_key': 'C',
                'estimated_tempo': 120,
                'note': 'MusicXML parsing failed, using defaults'
            }
        
        return analysis
    
    def _analyze_midi(self, file_path: Path) -> Dict[str, Any]:
        """
        Analyze MIDI files
        """
        # Basic MIDI analysis
        analysis = {
            'type': 'midi',
            'estimated_key': 'C',
            'estimated_tempo': 120,
            'estimated_time_signature': '4/4',
            'tracks_count': 1,
            'instruments': ['piano'],
            'note_range': [60, 84],  # Middle C to C6
            'duration': '0:00',
            'difficulty_level': 'intermediate',
            'note': 'MIDI analysis - can be enhanced with python-midi or mido libraries'
        }
        
        return analysis
    
    def _analyze_notation(self, file_path: Path) -> Dict[str, Any]:
        """
        Analyze ABC notation or LilyPond files
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Basic text analysis for ABC notation
            analysis = {
                'type': 'notation',
                'format': 'abc' if file_path.suffix.lower() == '.abc' else 'lilypond',
                'estimated_key': 'C',
                'estimated_tempo': 120,
                'content_length': len(content),
                'lines_count': len(content.splitlines()),
                'contains_chords': '[' in content and ']' in content,
                'difficulty_level': 'intermediate',
                'note': 'Text-based notation analysis'
            }
            
        except Exception as e:
            analysis = {
                'type': 'notation',
                'error': f'File reading error: {str(e)}',
                'note': 'Notation analysis failed'
            }
        
        return analysis
    
    def _analyze_text_tab(self, file_path: Path) -> Dict[str, Any]:
        """
        Analyze text-based tablature files
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Look for tablature patterns
            has_tab_lines = any(line.count('-') > 10 for line in content.splitlines())
            has_numbers = any(char.isdigit() for char in content)
            
            analysis = {
                'type': 'text_tablature',
                'instrument': 'guitar',
                'estimated_key': 'Em',
                'estimated_tempo': 120,
                'content_length': len(content),
                'lines_count': len(content.splitlines()),
                'has_tablature_lines': has_tab_lines,
                'has_fret_numbers': has_numbers,
                'tuning': 'standard (estimated)',
                'difficulty_level': 'intermediate',
                'note': 'Text tablature analysis'
            }
            
        except Exception as e:
            analysis = {
                'type': 'text_tablature',
                'error': f'File reading error: {str(e)}',
                'note': 'Text tablature analysis failed'
            }
        
        return analysis
    
    def get_score_analysis(self, file_id: str) -> Optional[Dict[str, Any]]:
        """
        Get analysis for a specific score file
        """
        if file_id in self.metadata:
            return self.metadata[file_id]
        return None
    
    def generate_json_structure(self, file_id: str, instrument_name: str = 'piano', 
                              track_name: str = 'Score Track') -> Optional[Dict[str, Any]]:
        """
        Generate JSON instrument structure from processed score
        """
        if file_id not in self.metadata:
            return None
        
        score_data = self.metadata[file_id]
        analysis = score_data.get('analysis', {})
        
        # Create basic JSON structure based on analysis
        json_structure = {
            "id": f"track-{file_id[:8]}",
            "name": track_name,
            "instrument": instrument_name,
            "category": "instruments",
            "volume": 0.8,
            "pan": 0,
            "muted": False,
            "solo": False,
            "clips": []
        }
        
        # Add basic clip based on analysis
        clip = {
            "id": f"clip-{file_id[:8]}",
            "startTime": 0,
            "duration": 8.0,  # Default 8 beats
            "notes": self._generate_notes_from_analysis(analysis, instrument_name),
            "effects": {
                "reverb": 0.2,
                "delay": 0.1,
                "distortion": 0,
                "pitchShift": 0,
                "chorus": 0.1,
                "filter": 0,
                "bitcrush": 0
            }
        }
        
        json_structure["clips"] = [clip]
        
        return json_structure
    
    def _generate_notes_from_analysis(self, analysis: Dict[str, Any], instrument: str) -> List[Dict[str, Any]]:
        """
        Generate note structure from score analysis
        """
        # Default notes based on estimated key and instrument
        estimated_key = analysis.get('estimated_key', 'C')
        
        # Simple chord progression in the detected key
        key_notes = {
            'C': [60, 64, 67],  # C major triad (C, E, G)
            'G': [67, 71, 74],  # G major triad (G, B, D)
            'D': [62, 66, 69],  # D major triad (D, F#, A)
            'A': [69, 73, 76],  # A major triad (A, C#, E)
            'E': [64, 68, 71],  # E major triad (E, G#, B)
            'F': [65, 69, 72],  # F major triad (F, A, C)
            'Em': [64, 67, 71], # Em triad (E, G, B)
        }
        
        base_notes = key_notes.get(estimated_key, key_notes['C'])
        
        notes = []
        for i, midi_note in enumerate(base_notes):
            note = {
                "time": i * 1.0,  # Spread notes across time
                "duration": 1.0,
                "pitch": midi_note,
                "velocity": 80,
                "chord": estimated_key
            }
            notes.append(note)
        
        return notes
    
    def list_scores(self) -> List[Dict[str, Any]]:
        """
        List all processed scores
        """
        scores = []
        for file_id, metadata in self.metadata.items():
            score_info = {
                'file_id': file_id,
                'filename': metadata.get('original_filename', 'Unknown'),
                'category': metadata.get('category', 'unknown'),
                'status': metadata.get('status', 'unknown'),
                'upload_date': metadata.get('upload_date'),
                'file_size': metadata.get('file_size', 0)
            }
            scores.append(score_info)
        
        # Sort by upload date (newest first)
        scores.sort(key=lambda x: x.get('upload_date', ''), reverse=True)
        return scores
    
    def delete_score(self, file_id: str) -> bool:
        """
        Delete a processed score and its files
        """
        if file_id not in self.metadata:
            return False
        
        try:
            # Remove the score directory
            score_dir = self.scores_dir / file_id
            if score_dir.exists():
                shutil.rmtree(score_dir)
            
            # Remove from metadata
            del self.metadata[file_id]
            self._save_metadata()
            
            return True
            
        except Exception as e:
            self._get_logger().error(f"Error deleting score {file_id}: {e}")
            return False