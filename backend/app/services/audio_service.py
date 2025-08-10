"""
Audio Service
Handles audio file processing, effects, and analysis
"""

import os
import uuid
import tempfile
from typing import Dict, List, Any, Optional, Tuple
import numpy as np
import librosa
import soundfile as sf
from pydub import AudioSegment
from flask import current_app
import json


class AudioService:
    """Service for audio processing and analysis"""
    
    ALLOWED_EXTENSIONS = {'wav', 'mp3', 'flac', 'aiff', 'm4a', 'ogg'}
    
    def __init__(self):
        self.upload_dir = current_app.config.get('UPLOAD_FOLDER', 'uploads')
        self._ensure_upload_dir()
    
    def _ensure_upload_dir(self):
        """Ensure upload directory exists"""
        if not os.path.exists(self.upload_dir):
            os.makedirs(self.upload_dir)
    
    @staticmethod
    def allowed_file(filename: str) -> bool:
        """Check if file extension is allowed"""
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in AudioService.ALLOWED_EXTENSIONS
    
    def process_upload(self, file) -> Dict:
        """Process uploaded audio file"""
        if not self.allowed_file(file.filename):
            raise ValueError("File type not supported")
        
        # Generate unique file ID
        file_id = str(uuid.uuid4())
        file_extension = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{file_id}.{file_extension}"
        filepath = os.path.join(self.upload_dir, filename)
        
        # Save uploaded file
        file.save(filepath)
        
        try:
            # Load and analyze audio
            audio_data, sample_rate = librosa.load(filepath, sr=None)
            
            # Get basic audio info
            duration = len(audio_data) / sample_rate
            channels = 1 if len(audio_data.shape) == 1 else audio_data.shape[0]
            
            # Generate waveform data for visualization
            waveform_data = self._generate_waveform_data(audio_data, sample_rate)
            
            # Extract metadata
            metadata = self._extract_metadata(filepath, audio_data, sample_rate)
            
            return {
                'file_id': file_id,
                'filename': file.filename,
                'duration': duration,
                'sample_rate': sample_rate,
                'channels': channels,
                'waveform_data': waveform_data,
                'metadata': metadata
            }
            
        except Exception as e:
            # Clean up file if processing fails
            if os.path.exists(filepath):
                os.remove(filepath)
            raise e
    
    def generate_waveform(self, file_id: str, resolution: int = 1000) -> List[float]:
        """Generate waveform data for visualization"""
        filepath = self.get_file_path(file_id)
        
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Audio file not found: {file_id}")
        
        # Load audio
        audio_data, sample_rate = librosa.load(filepath, sr=None)
        
        return self._generate_waveform_data(audio_data, sample_rate, resolution)
    
    def _generate_waveform_data(self, audio_data: np.ndarray, sample_rate: int, 
                               resolution: int = 1000) -> List[float]:
        """Generate downsampled waveform data for visualization"""
        # Calculate chunk size for downsampling
        chunk_size = len(audio_data) // resolution
        
        if chunk_size < 1:
            chunk_size = 1
        
        # Downsample by taking RMS of chunks
        waveform = []
        for i in range(0, len(audio_data), chunk_size):
            chunk = audio_data[i:i + chunk_size]
            rms = np.sqrt(np.mean(chunk ** 2))
            waveform.append(float(rms))
        
        return waveform[:resolution]  # Ensure exact resolution
    
    def apply_effects(self, file_id: str, effects: Dict) -> Dict:
        """Apply audio effects to a file"""
        input_path = self.get_file_path(file_id)
        
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Audio file not found: {file_id}")
        
        # Generate new file ID for processed audio
        processed_file_id = str(uuid.uuid4())
        output_path = os.path.join(self.upload_dir, f"{processed_file_id}.wav")
        
        import time
        start_time = time.time()
        
        try:
            # Load audio
            audio_data, sample_rate = librosa.load(input_path, sr=None)
            
            # Apply effects
            processed_audio = self._apply_audio_effects(audio_data, sample_rate, effects)
            
            # Save processed audio
            sf.write(output_path, processed_audio, sample_rate)
            
            processing_time = time.time() - start_time
            
            return {
                'file_id': processed_file_id,
                'processing_time': processing_time
            }
            
        except Exception as e:
            # Clean up if processing fails
            if os.path.exists(output_path):
                os.remove(output_path)
            raise e
    
    def _apply_audio_effects(self, audio_data: np.ndarray, sample_rate: int, 
                           effects: Dict) -> np.ndarray:
        """Apply various audio effects"""
        processed = audio_data.copy()
        
        # Reverb (simplified convolution reverb)
        if effects.get('reverb', 0) > 0:
            reverb_amount = effects['reverb']
            # Create simple impulse response
            reverb_length = int(sample_rate * 0.5)  # 0.5 second reverb
            impulse = np.exp(-np.linspace(0, 5, reverb_length)) * np.random.normal(0, 0.1, reverb_length)
            reverb = np.convolve(processed, impulse, mode='same') * reverb_amount
            processed = processed + reverb * reverb_amount
        
        # Delay
        if effects.get('delay', 0) > 0:
            delay_amount = effects['delay']
            delay_samples = int(sample_rate * 0.25)  # 250ms delay
            delayed = np.zeros_like(processed)
            delayed[delay_samples:] = processed[:-delay_samples]
            processed = processed + delayed * delay_amount * 0.5
        
        # Distortion
        if effects.get('distortion', 0) > 0:
            distortion_amount = effects['distortion']
            # Soft clipping distortion
            gain = 1 + distortion_amount * 10
            processed = np.tanh(processed * gain) / gain
        
        # Normalize to prevent clipping
        max_val = np.max(np.abs(processed))
        if max_val > 1.0:
            processed = processed / max_val * 0.95
        
        return processed
    
    def convert_audio(self, file_id: str, target_format: str, 
                     target_sample_rate: Optional[int] = None,
                     target_bitrate: Optional[str] = None) -> Dict:
        """Convert audio to different format"""
        input_path = self.get_file_path(file_id)
        
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Audio file not found: {file_id}")
        
        # Generate new file ID
        converted_file_id = str(uuid.uuid4())
        output_path = os.path.join(self.upload_dir, f"{converted_file_id}.{target_format}")
        
        try:
            # Load audio
            audio_data, sample_rate = librosa.load(input_path, sr=target_sample_rate)
            
            if target_format == 'wav':
                # Save as WAV
                sf.write(output_path, audio_data, sample_rate)
            else:
                # Use pydub for other formats
                # Convert to temporary WAV first
                temp_wav = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
                sf.write(temp_wav.name, audio_data, sample_rate)
                
                # Load with pydub and export
                audio_segment = AudioSegment.from_wav(temp_wav.name)
                
                export_params = {}
                if target_bitrate and target_format == 'mp3':
                    export_params['bitrate'] = target_bitrate
                
                audio_segment.export(output_path, format=target_format, **export_params)
                
                # Clean up temp file
                os.unlink(temp_wav.name)
            
            return {
                'file_id': converted_file_id,
                'sample_rate': sample_rate,
                'bitrate': target_bitrate
            }
            
        except Exception as e:
            # Clean up if conversion fails
            if os.path.exists(output_path):
                os.remove(output_path)
            raise e
    
    def analyze_audio(self, file_id: str) -> Dict:
        """Analyze audio features"""
        filepath = self.get_file_path(file_id)
        
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Audio file not found: {file_id}")
        
        # Load audio
        audio_data, sample_rate = librosa.load(filepath, sr=None)
        
        # Tempo detection
        tempo, beats = librosa.beat.beat_track(y=audio_data, sr=sample_rate)
        
        # Key detection (simplified)
        chroma = librosa.feature.chroma_stft(y=audio_data, sr=sample_rate)
        key_index = np.argmax(np.sum(chroma, axis=1))
        keys = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        estimated_key = keys[key_index]
        
        # Loudness (RMS)
        rms = librosa.feature.rms(y=audio_data)[0]
        loudness = np.mean(rms)
        
        # Spectral features
        spectral_centroids = librosa.feature.spectral_centroid(y=audio_data, sr=sample_rate)[0]
        spectral_bandwidth = librosa.feature.spectral_bandwidth(y=audio_data, sr=sample_rate)[0]
        spectral_rolloff = librosa.feature.spectral_rolloff(y=audio_data, sr=sample_rate)[0]
        
        # Zero crossing rate
        zcr = librosa.feature.zero_crossing_rate(audio_data)[0]
        
        return {
            'tempo': float(tempo),
            'key': estimated_key,
            'time_signature': '4/4',  # Simplified - would need more analysis
            'loudness': float(loudness),
            'spectral_features': {
                'centroid': float(np.mean(spectral_centroids)),
                'bandwidth': float(np.mean(spectral_bandwidth)),
                'rolloff': float(np.mean(spectral_rolloff)),
                'zero_crossing_rate': float(np.mean(zcr))
            },
            'harmonic_features': {
                'key_confidence': float(np.max(np.sum(chroma, axis=1)) / np.sum(chroma)),
                'tonal_strength': float(np.std(np.sum(chroma, axis=1)))
            }
        }
    
    def get_file_path(self, file_id: str) -> str:
        """Get full file path for a file ID"""
        # Look for file with any supported extension
        for ext in self.ALLOWED_EXTENSIONS:
            filepath = os.path.join(self.upload_dir, f"{file_id}.{ext}")
            if os.path.exists(filepath):
                return filepath
        
        raise FileNotFoundError(f"File not found: {file_id}")
    
    def export_project(self, project_id: str, format: str = 'wav', quality: str = 'high') -> Dict:
        """Export project as single audio file"""
        # This would implement project mixdown logic
        # For now, return a placeholder
        
        export_file_id = str(uuid.uuid4())
        
        # In a real implementation, this would:
        # 1. Load all project tracks
        # 2. Apply track effects and mixing
        # 3. Render to single audio file
        # 4. Apply master effects
        # 5. Export in requested format
        
        return {
            'file_id': export_file_id,
            'file_size': 1024 * 1024 * 5,  # 5MB placeholder
            'duration': 180.0  # 3 minutes placeholder
        }
    
    def export_song_from_structure(self, song_structure: Dict, format: str = 'wav', 
                                  quality: str = 'high', filename: str = 'exported_song') -> Dict:
        """Export song from JSON structure as audio file"""
        try:
            import numpy as np
            import io
            import wave
            import struct
            
            # Get song properties
            duration = song_structure.get('duration', 60)  # Default 1 minute
            tempo = song_structure.get('tempo', 120)
            tracks = song_structure.get('tracks', [])
            
            current_app.logger.info(f"Exporting song: {filename}")
            current_app.logger.info(f"Duration: {duration}s, Tempo: {tempo} BPM")
            current_app.logger.info(f"Tracks: {len(tracks)}")
            
            # Generate a simple audio file (placeholder implementation)
            sample_rate = 44100
            samples = int(duration * sample_rate)
            
            # Create a simple tone based on the song structure
            # This is a placeholder - in real implementation you'd render actual tracks
            t = np.linspace(0, duration, samples, False)
            
            # Generate a simple chord progression based on song key
            song_key = song_structure.get('key', 'C')
            base_freq = {'C': 261.63, 'D': 293.66, 'E': 329.63, 'F': 349.23, 
                        'G': 392.00, 'A': 440.00, 'B': 493.88}.get(song_key, 261.63)
            
            # Create a simple chord progression with multiple frequencies
            audio_data = (
                np.sin(2 * np.pi * base_freq * t) * 0.3 +  # Root
                np.sin(2 * np.pi * base_freq * 1.25 * t) * 0.2 +  # Third
                np.sin(2 * np.pi * base_freq * 1.5 * t) * 0.2  # Fifth
            )
            
            # Add some rhythm based on tempo
            beat_duration = 60.0 / tempo  # Duration of one beat in seconds
            for i in range(int(duration / beat_duration)):
                start_sample = int(i * beat_duration * sample_rate)
                end_sample = int((i + 0.1) * beat_duration * sample_rate)  # Short beat
                if end_sample < len(audio_data):
                    audio_data[start_sample:end_sample] *= 1.5  # Accent the beat
            
            # Normalize audio
            audio_data = audio_data / np.max(np.abs(audio_data)) * 0.8
            
            # Convert to 16-bit PCM
            audio_data_int = (audio_data * 32767).astype(np.int16)
            
            # Create WAV file in memory
            buffer = io.BytesIO()
            with wave.open(buffer, 'wb') as wav_file:
                wav_file.setnchannels(1)  # Mono
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(audio_data_int.tobytes())
            
            # Get the audio data
            buffer.seek(0)
            audio_bytes = buffer.getvalue()
            
            # Calculate file size
            file_size = len(audio_bytes)
            
            # Store the audio data temporarily (in a real app, you'd use proper storage)
            export_file_id = str(uuid.uuid4())
            
            # Store in a temporary dict (in production, use Redis or database)
            if not hasattr(self, '_temp_exports'):
                self._temp_exports = {}
            
            self._temp_exports[export_file_id] = {
                'data': audio_bytes,
                'filename': f"{filename}.{format}",
                'content_type': 'audio/wav' if format == 'wav' else f'audio/{format}',
                'size': file_size
            }
            
            return {
                'file_id': export_file_id,
                'download_url': f"/api/audio/download-export/{export_file_id}",
                'file_size': file_size,
                'duration': float(duration),
                'sample_rate': sample_rate,
                'format': format,
                'filename': f"{filename}.{format}"
            }
            
        except Exception as e:
            current_app.logger.error(f"Error exporting song from structure: {e}")
            raise Exception(f"Failed to export song: {str(e)}")
    
    def get_export_file(self, file_id: str) -> Dict:
        """Get exported file data"""
        if hasattr(self, '_temp_exports') and file_id in self._temp_exports:
            return self._temp_exports[file_id]
        raise FileNotFoundError(f"Export file not found: {file_id}")
    
    
    def _extract_metadata(self, filepath: str, audio_data: np.ndarray, sample_rate: int) -> Dict:
        """Extract metadata from audio file"""
        try:
            # Basic metadata
            metadata = {
                'duration': len(audio_data) / sample_rate,
                'sample_rate': sample_rate,
                'channels': 1 if len(audio_data.shape) == 1 else audio_data.shape[0],
                'bit_depth': 16,  # Default assumption
                'file_size': os.path.getsize(filepath)
            }
            
            # Try to get more detailed metadata using pydub
            try:
                audio_segment = AudioSegment.from_file(filepath)
                metadata.update({
                    'channels': audio_segment.channels,
                    'sample_rate': audio_segment.frame_rate,
                    'bit_depth': audio_segment.sample_width * 8
                })
            except Exception:
                pass  # Use defaults if pydub fails
            
            return metadata
            
        except Exception as e:
            current_app.logger.warning(f"Failed to extract metadata: {str(e)}")
            return {}
