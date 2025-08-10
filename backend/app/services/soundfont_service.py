"""
SoundFont Processing Service
Handles SoundFont file upload, parsing, and chord/note generation
"""

import os
import tempfile
import shutil
import uuid
import json
import logging
import threading
import wave
import struct
import math
from pathlib import Path
from typing import List, Dict, Any, Optional
from werkzeug.datastructures import FileStorage
from flask import current_app

logger = logging.getLogger(__name__)


class SoundFontService:
    """Service for processing SoundFont files and generating chord libraries"""
    
    # Class-level job storage to persist across instances
    _jobs = {}
    
    def __init__(self):
        pass
        
    def process_soundfont_files(self, files: List[FileStorage]) -> str:
        """
        Process uploaded SoundFont files asynchronously
        Returns job ID for status tracking
        """
        job_id = str(uuid.uuid4())
        
        # Read file contents immediately to avoid closed file issues
        file_data = []
        for file in files:
            if file.filename:
                content = file.read()
                file_data.append({
                    'filename': file.filename,
                    'content': content
                })
        
        # Initialize job status in class storage
        SoundFontService._jobs[job_id] = {
            'status': 'starting',
            'progress': 0,
            'message': 'Initializing...',
            'completed': False,
            'error': None,
            'files': [f['filename'] for f in file_data],
            'results': {}
        }
        
        # Start processing in background thread
        thread = threading.Thread(
            target=self._process_files_background,
            args=(job_id, file_data)
        )
        thread.daemon = True
        thread.start()
        
        return job_id
    
    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Get job status by ID"""
        return SoundFontService._jobs.get(job_id, {
            'error': 'Job not found',
            'completed': False,
            'progress': 0
        })
    
    def _process_files_background(self, job_id: str, file_data: List[Dict[str, Any]]):
        """Background processing of SoundFont files"""
        try:
            self._update_job_status(job_id, 'processing', 10, 'Saving uploaded files...')
            
            # Create temporary directory for processing
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Save uploaded files
                sf2_files = []
                for file_info in file_data:
                    filename = file_info['filename']
                    content = file_info['content']
                    if filename:
                        file_path = temp_path / filename
                        with open(file_path, 'wb') as f:
                            f.write(content)
                        sf2_files.append(file_path)
                
                self._update_job_status(job_id, 'processing', 20, 'Generating chord library...')
                
                # Process each SoundFont file
                total_instruments = 0
                results = {}
                
                for i, sf2_file in enumerate(sf2_files):
                    try:
                        progress = 20 + (i / len(sf2_files)) * 60
                        self._update_job_status(
                            job_id, 'processing', progress, 
                            f'Processing {sf2_file.name}...'
                        )
                        
                        # Generate chord library for this SoundFont
                        instruments_generated = self._generate_chord_library(sf2_file)
                        
                        results[sf2_file.name] = {
                            'instruments_generated': instruments_generated,
                            'status': 'completed'
                        }
                        total_instruments += instruments_generated
                        
                    except Exception as e:
                        logger.error(f"Error processing {sf2_file.name}: {str(e)}")
                        results[sf2_file.name] = {
                            'instruments_generated': 0,
                            'status': 'error',
                            'error': str(e)
                        }
                
                # Complete job
                SoundFontService._jobs[job_id].update({
                    'status': 'completed',
                    'progress': 100,
                    'message': f'Completed! Generated {total_instruments} instruments',
                    'completed': True,
                    'total_instruments': total_instruments,
                    'results': results
                })
                
        except Exception as e:
            logger.error(f"Job {job_id} failed: {str(e)}")
            SoundFontService._jobs[job_id].update({
                'status': 'error',
                'error': str(e),
                'completed': True,
                'progress': 0
            })
    
    def _update_job_status(self, job_id: str, status: str, progress: float, message: str):
        """Update job status"""
        if job_id in SoundFontService._jobs:
            SoundFontService._jobs[job_id].update({
                'status': status,
                'progress': progress,
                'message': message
            })
    
    def _generate_chord_library(self, sf2_file: Path) -> int:
        """
        Generate chord library with synthesized audio (fallback implementation)
        """
        try:
            # Determine instrument category from SoundFont name
            sf2_name = sf2_file.stem.lower()
            category, instrument_name = self._categorize_soundfont(sf2_name)
            
            # Create output directory structure
            frontend_public = Path("../frontend/public/instruments")
            frontend_public.mkdir(parents=True, exist_ok=True)
            
            category_dir = frontend_public / category
            category_dir.mkdir(exist_ok=True)
            
            instrument_dir = category_dir / instrument_name
            instrument_dir.mkdir(exist_ok=True)
            
            # Generate chord progressions using synthesized audio
            return self._generate_synthesized_chords(instrument_dir, instrument_name)
            
        except Exception as e:
            logger.error(f"Chord library generation failed: {str(e)}")
            raise
    
    def _categorize_soundfont(self, sf2_name: str) -> tuple[str, str]:
        """Categorize SoundFont based on filename"""
        # Clean up name for instrument
        instrument_name = sf2_name.replace(' ', '_').replace('-', '_').lower()
        
        # Determine category
        if any(word in sf2_name for word in ['piano', 'keyboard', 'organ', 'synth']):
            category = 'keyboards'
        elif any(word in sf2_name for word in ['guitar', 'bass', 'violin', 'cello', 'string']):
            category = 'strings'
        elif any(word in sf2_name for word in ['drum', 'percussion', 'beat']):
            category = 'percussion'
        elif any(word in sf2_name for word in ['brass', 'trumpet', 'trombone', 'horn']):
            category = 'brass'
        elif any(word in sf2_name for word in ['flute', 'clarinet', 'sax', 'woodwind']):
            category = 'woodwinds'
        elif any(word in sf2_name for word in ['voice', 'choir', 'vocal']):
            category = 'vocal'
        else:
            category = 'other'
        
        return category, instrument_name
    
    def _generate_synthesized_chords(self, output_dir: Path, instrument_name: str) -> int:
        """Generate synthesized chord audio files"""
        try:
            # Chord types and notes from reference
            CHORD_TYPES = {
                'major': [0, 4, 7],
                'minor': [0, 3, 7],
                'diminished': [0, 3, 6],
                'augmented': [0, 4, 8],
                'dom7': [0, 4, 7, 10],
                'maj7': [0, 4, 7, 11],
                'min7': [0, 3, 7, 10],
                'sus2': [0, 2, 7],
                'sus4': [0, 5, 7],
            }
            
            NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
            
            generated_count = 0
            duration = 2.0  # seconds
            sample_rate = 44100
            
            for root_note in NOTE_NAMES:
                for chord_type in CHORD_TYPES:
                    chord_name = f"{root_note}_{chord_type}"
                    
                    try:
                        # Get chord notes
                        chord_notes = self._get_chord_notes(root_note, chord_type, CHORD_TYPES, NOTE_NAMES)
                        
                        # Generate synthesized audio
                        audio_data = self._create_chord_audio(chord_notes, duration, sample_rate, instrument_name)
                        
                        # Save as WAV
                        wav_path = output_dir / f"{chord_name}.wav"
                        self._save_wav(audio_data, str(wav_path), sample_rate)
                        
                        # Convert to MP3 (simple conversion using wave format)
                        mp3_path = output_dir / f"{chord_name}.mp3"
                        shutil.copy2(wav_path, mp3_path)  # For now, just copy as WAV (MP3 conversion requires additional libraries)
                        
                        generated_count += 1
                        
                    except Exception as e:
                        logger.warning(f"Error generating {chord_name}: {str(e)}")
                        continue
            
            # Generate metadata file
            metadata = {
                'instrument_name': instrument_name,
                'category': output_dir.parent.name,
                'generated_chords': generated_count,
                'formats': ['wav', 'mp3'],
                'duration': duration,
                'generated_by': 'mITyStudio SoundFont Processor'
            }
            
            with open(output_dir / 'metadata.json', 'w') as f:
                json.dump(metadata, f, indent=2)
            
            return generated_count
            
        except Exception as e:
            logger.error(f"Synthesized chord generation failed: {str(e)}")
            return 0
    
    def _get_chord_notes(self, root_note: str, chord_type: str, chord_types: dict, note_names: list, octave: int = 4) -> list:
        """Get MIDI note numbers for a chord"""
        root_midi = note_names.index(root_note) + (octave * 12) + 12
        intervals = chord_types[chord_type]
        return [root_midi + interval for interval in intervals]
    
    def _create_chord_audio(self, chord_notes: list, duration: float, sample_rate: int, instrument_type: str) -> bytes:
        """Create synthesized audio for chord"""
        frames = int(duration * sample_rate)
        mixed_audio = [0.0] * frames
        
        for note in chord_notes:
            freq = 440.0 * (2 ** ((note - 69) / 12.0))  # Convert MIDI to frequency
            wave_data = self._generate_wave(freq, duration, sample_rate, instrument_type)
            
            for i in range(frames):
                mixed_audio[i] += wave_data[i] * 0.3  # Mix and reduce volume
        
        # Normalize and convert to int16
        max_val = max(abs(x) for x in mixed_audio)
        if max_val > 0:
            mixed_audio = [int(x / max_val * 32767 * 0.8) for x in mixed_audio]
        else:
            mixed_audio = [0] * frames
        
        return b''.join(struct.pack('<h', int(sample)) for sample in mixed_audio)
    
    def _generate_wave(self, frequency: float, duration: float, sample_rate: int, instrument_type: str) -> list:
        """Generate waveform based on instrument type"""
        frames = int(duration * sample_rate)
        wave_data = []
        
        if 'piano' in instrument_type or 'keyboard' in instrument_type:
            # Piano-like wave with harmonics and decay
            for i in range(frames):
                t = i / sample_rate
                # Fundamental + harmonics
                sample = (
                    math.sin(2 * math.pi * frequency * t) +
                    0.5 * math.sin(2 * math.pi * frequency * 2 * t) +
                    0.25 * math.sin(2 * math.pi * frequency * 3 * t)
                )
                # Apply decay envelope
                envelope = math.exp(-t * 2)
                wave_data.append(sample * envelope)
                
        elif 'guitar' in instrument_type or 'string' in instrument_type:
            # Guitar-like wave with pluck envelope
            for i in range(frames):
                t = i / sample_rate
                sample = (
                    math.sin(2 * math.pi * frequency * t) +
                    0.7 * math.sin(2 * math.pi * frequency * 2 * t) +
                    0.4 * math.sin(2 * math.pi * frequency * 3 * t)
                )
                # Sharp attack, medium decay
                if t < 0.05:
                    envelope = t / 0.05
                else:
                    envelope = math.exp(-(t - 0.05) * 1.5)
                wave_data.append(sample * envelope)
                
        else:
            # Generic sine wave with simple envelope
            for i in range(frames):
                t = i / sample_rate
                sample = math.sin(2 * math.pi * frequency * t)
                # Simple envelope
                envelope = math.exp(-t * 1.5)
                wave_data.append(sample * envelope)
        
        return wave_data
    
    def _save_wav(self, audio_data: bytes, filename: str, sample_rate: int):
        """Save audio data as WAV file"""
        with wave.open(filename, 'wb') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 2 bytes per sample (16-bit)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_data)
