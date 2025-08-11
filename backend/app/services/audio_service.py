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
from pathlib import Path


class AudioService:
    """Service for audio processing and analysis"""
    
    ALLOWED_EXTENSIONS = {'wav', 'mp3', 'flac', 'aiff', 'm4a', 'ogg'}
    
    def __init__(self):
        self.upload_dir = current_app.config.get('UPLOAD_FOLDER', 'uploads')
        self.export_dir = current_app.config.get('EXPORT_FOLDER', 'temp_exports')
        self._ensure_upload_dir()
        self._ensure_export_dir()
        # Clean up old exports on service initialization
        self.cleanup_old_exports(1)  # Clean files older than 1 hour
        
        # Initialize sample cache for instrument samples
        self.sample_cache = {}
        self.instruments_root = self._get_instruments_path()
    
    def _ensure_upload_dir(self):
        """Ensure upload directory exists"""
        if not os.path.exists(self.upload_dir):
            os.makedirs(self.upload_dir)
    
    def _ensure_export_dir(self):
        """Ensure export directory exists"""
        if not os.path.exists(self.export_dir):
            os.makedirs(self.export_dir)
    
    def _get_instruments_path(self) -> Path:
        """Get the path to the instruments directory"""
        try:
            current_file = Path(__file__).resolve()
            project_root = current_file.parent.parent.parent.parent
            instruments_path = project_root / 'frontend' / 'public' / 'instruments'
            current_app.logger.info(f"Instruments path: {instruments_path}")
            return instruments_path
        except Exception as e:
            current_app.logger.error(f"Error getting instruments path: {e}")
            return Path('frontend/public/instruments')
    
    def _get_instrument_category(self, instrument: str) -> str:
        """Determine the category for an instrument"""
        category_mapping = {
            'piano': 'keyboards',
            'electric-piano': 'keyboards', 
            'keyboard': 'keyboards',
            'guitar': 'strings',
            'electric-guitar': 'strings',
            'acoustic-guitar': 'strings',
            'bass': 'strings',
            'electric-bass': 'strings',
            'drums': 'percussion',
            'percussion': 'percussion',
            'violin': 'strings',
            'cello': 'strings',
            'trumpet': 'brass',
            'trombone': 'brass',
            'horn': 'brass',
            'flute': 'woodwinds',
            'saxophone': 'woodwinds',
            'clarinet': 'woodwinds',
            'vocals': 'vocal',
            'voice': 'vocal'
        }
        
        instrument_lower = instrument.lower()
        for key, category in category_mapping.items():
            if key in instrument_lower:
                return category
        
        # Default fallback
        return 'other'
    
    def _find_instrument_samples(self, category: str, instrument: str) -> Dict[str, str]:
        """Find available sample files for an instrument"""
        samples = {}
        
        try:
            if not self.instruments_root.exists():
                current_app.logger.warning(f"Instruments root not found: {self.instruments_root}")
                return samples
            
            # Look for the instrument in the category
            category_dir = self.instruments_root / category
            if not category_dir.exists():
                current_app.logger.warning(f"Category directory not found: {category_dir}")
                return samples
            
            # Try multiple instrument name variations
            instrument_variations = [
                instrument,
                instrument.title(),
                instrument.replace('-', '_'),
                instrument.replace('_', '-'),
                instrument.replace(' ', '_')
            ]
            
            instrument_dir = None
            for variation in instrument_variations:
                test_dir = category_dir / variation
                if test_dir.exists():
                    instrument_dir = test_dir
                    current_app.logger.info(f"Found instrument directory: {instrument_dir}")
                    break
            
            if not instrument_dir:
                current_app.logger.warning(f"Instrument directory not found for {instrument} in {category}")
                return samples
            
            # Look for sample files in different structures
            # Structure 1: direct format folders (mp3/, wav/)
            for format_dir in ['mp3', 'wav']:
                format_path = instrument_dir / format_dir
                if format_path.exists():
                    for sample_file in format_path.iterdir():
                        if sample_file.is_file() and sample_file.suffix.lower() in ['.mp3', '.wav']:
                            chord_name = sample_file.stem
                            samples[chord_name] = str(sample_file)
            
            # Structure 2: duration-based folders (1.0s/mp3/, 2.0s/wav/, etc.)
            if not samples:  # Only try this if no samples found in direct structure
                for duration_dir in instrument_dir.iterdir():
                    if duration_dir.is_dir() and duration_dir.name not in ['mp3', 'wav', 'midi']:
                        for format_dir in ['mp3', 'wav']:
                            format_path = duration_dir / format_dir
                            if format_path.exists():
                                for sample_file in format_path.iterdir():
                                    if sample_file.is_file() and sample_file.suffix.lower() in ['.mp3', '.wav']:
                                        chord_name = sample_file.stem
                                        samples[chord_name] = str(sample_file)
            
            current_app.logger.info(f"Found {len(samples)} samples for {category}/{instrument}")
            return samples
            
        except Exception as e:
            current_app.logger.error(f"Error finding samples for {category}/{instrument}: {e}")
            return samples
    
    def _load_audio_sample(self, sample_path: str, target_duration: float = None) -> np.ndarray:
        """Load an audio sample file and optionally adjust its duration"""
        try:
            current_app.logger.info(f"Loading audio sample: {sample_path}")
            
            # Load the audio file
            audio_data, original_sr = librosa.load(sample_path, sr=44100, mono=False)
            
            # Ensure stereo output
            if audio_data.ndim == 1:
                # Convert mono to stereo
                audio_data = np.stack([audio_data, audio_data])
            elif audio_data.ndim == 2 and audio_data.shape[0] > 2:
                # Take first two channels if more than stereo
                audio_data = audio_data[:2]
            
            # Adjust duration if specified
            if target_duration:
                target_samples = int(target_duration * 44100)
                current_samples = audio_data.shape[1]
                
                if current_samples < target_samples:
                    # Loop the audio to reach target duration
                    repeats = int(np.ceil(target_samples / current_samples))
                    audio_data = np.tile(audio_data, (1, repeats))
                    audio_data = audio_data[:, :target_samples]
                elif current_samples > target_samples:
                    # Trim to target duration
                    audio_data = audio_data[:, :target_samples]
            
            return audio_data
            
        except Exception as e:
            current_app.logger.error(f"Error loading audio sample {sample_path}: {e}")
            return None
    
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
        """Export song from JSON structure as audio file with full track rendering"""
        try:
            import numpy as np
            import io
            import wave
            import struct
            
            # Get song properties
            duration = song_structure.get('duration', 60)  # Default 1 minute
            tempo = song_structure.get('tempo', 120)
            song_key = song_structure.get('key', 'C')
            tracks = song_structure.get('tracks', [])
            
            current_app.logger.info(f"Exporting song: {filename}")
            current_app.logger.info(f"Duration: {duration}s, Tempo: {tempo} BPM, Key: {song_key}")
            current_app.logger.info(f"Tracks: {len(tracks)}")
            
            # Audio settings
            sample_rate = 44100
            samples = int(duration * sample_rate)
            
            # Initialize master audio buffer (stereo)
            master_audio = np.zeros((2, samples), dtype=np.float64)
            
            # Process each track
            for track_idx, track in enumerate(tracks):
                current_app.logger.info(f"Processing track {track_idx + 1}: {track.get('name', 'Unknown')} ({track.get('instrument', 'Unknown')})")
                
                if track.get('muted', False):
                    current_app.logger.info(f"  Skipping muted track: {track.get('name')}")
                    continue
                
                # Generate track audio
                track_audio = self._render_track_audio(track, duration, sample_rate, tempo, song_key)
                
                if track_audio is not None:
                    # Apply track volume and pan
                    track_volume = track.get('volume', 0.8)
                    track_pan = track.get('pan', 0.0)  # -1.0 (left) to 1.0 (right)
                    
                    # Calculate stereo positioning
                    left_gain = track_volume * (1.0 - max(0, track_pan))
                    right_gain = track_volume * (1.0 + min(0, track_pan))
                    
                    # Ensure track_audio is stereo and the right length
                    if track_audio.ndim == 1:
                        # Convert mono to stereo
                        track_audio = np.stack([track_audio, track_audio])
                    
                    if track_audio.shape[1] > samples:
                        track_audio = track_audio[:, :samples]
                    elif track_audio.shape[1] < samples:
                        # Pad with zeros
                        padded = np.zeros((2, samples))
                        padded[:, :track_audio.shape[1]] = track_audio
                        track_audio = padded
                    
                    # Mix into master with panning
                    master_audio[0, :] += track_audio[0, :] * left_gain   # Left channel
                    master_audio[1, :] += track_audio[1, :] * right_gain  # Right channel
                    
                    current_app.logger.info(f"  Mixed track with volume={track_volume:.2f}, pan={track_pan:.2f}")
            
            # Apply master effects and normalize
            master_audio = self._apply_master_effects(master_audio)
            
            # Normalize to prevent clipping
            max_amplitude = np.max(np.abs(master_audio))
            if max_amplitude > 0:
                master_audio = master_audio / max_amplitude * 0.8
            
            # Convert to stereo 16-bit PCM (transpose to interleaved format)
            audio_data_int = (master_audio.T * 32767).astype(np.int16)
            
            # Create WAV file in memory
            buffer = io.BytesIO()
            with wave.open(buffer, 'wb') as wav_file:
                wav_file.setnchannels(2)  # Stereo
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(audio_data_int.tobytes())
            
            # Get the audio data
            buffer.seek(0)
            audio_bytes = buffer.getvalue()
            
            # Calculate file size
            file_size = len(audio_bytes)
            
            # Store the audio data in a temporary file
            export_file_id = str(uuid.uuid4())
            export_filename = f"{filename}.{format.lower()}"
            
            # Save to temporary export directory
            export_path = os.path.join(self.export_dir, f"{export_file_id}.wav")
            with open(export_path, 'wb') as f:
                f.write(audio_bytes)
            
            # Save metadata
            metadata_path = os.path.join(self.export_dir, f"{export_file_id}.json")
            metadata = {
                'filename': export_filename,
                'content_type': 'audio/wav' if format.lower() == 'wav' else f'audio/{format.lower()}',
                'size': file_size,
                'original_format': format.lower()
            }
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f)
            
            return {
                'file_id': export_file_id,
                'download_url': f"/api/audio/download-export/{export_file_id}",
                'file_size': file_size,
                'duration': float(duration),
                'sample_rate': sample_rate,
                'format': format.lower(),
                'filename': export_filename
            }
            
        except Exception as e:
            current_app.logger.error(f"Error exporting song from structure: {e}")
            raise Exception(f"Failed to export song: {str(e)}")
    
    def _render_track_audio(self, track: Dict, duration: float, sample_rate: int, tempo: int, song_key: str) -> np.ndarray:
        """Render audio for a single track based on its clips and instrument"""
        try:
            samples = int(duration * sample_rate)
            # Create stereo track audio
            track_audio = np.zeros((2, samples), dtype=np.float64)
            
            clips = track.get('clips', [])
            instrument = track.get('instrument', 'synth')
            
            current_app.logger.info(f"    Rendering {len(clips)} clips for {instrument}")
            
            for clip in clips:
                clip_audio = self._render_clip_audio(clip, sample_rate, tempo, song_key, instrument)
                if clip_audio is not None:
                    # Ensure clip_audio is stereo
                    if clip_audio.ndim == 1:
                        # Convert mono to stereo
                        clip_audio = np.stack([clip_audio, clip_audio])
                    
                    # Position clip in track timeline
                    start_time = clip.get('startTime', 0)
                    start_sample = int(start_time * sample_rate)
                    end_sample = min(start_sample + clip_audio.shape[1], samples)
                    
                    if start_sample < samples:
                        # Mix clip into track
                        clip_length = end_sample - start_sample
                        track_audio[:, start_sample:end_sample] += clip_audio[:, :clip_length]
            
            return track_audio
            
        except Exception as e:
            current_app.logger.error(f"Error rendering track audio: {e}")
            return None
    
    def _render_clip_audio(self, clip: Dict, sample_rate: int, tempo: int, song_key: str, instrument: str) -> np.ndarray:
        """Render audio for a single clip based on its content and instrument"""
        try:
            clip_duration = clip.get('duration', 4)
            samples = int(clip_duration * sample_rate)
            
            # Extract notes from clip - handle both direct notes and lyrics structure
            notes = self._extract_notes_from_clip(clip, instrument, song_key)
            
            current_app.logger.info(f"      Rendering clip: duration={clip_duration}s, notes={notes[:3] if len(notes) > 3 else notes}")
            
            # Determine instrument category
            category = self._get_instrument_category(instrument)
            
            # Try to use actual samples first
            sample_audio = self._render_clip_with_samples(clip, samples, sample_rate, notes, category, instrument)
            if sample_audio is not None:
                current_app.logger.info(f"      ✅ Used actual samples for {instrument}")
                return sample_audio
            
            # Fallback to synthetic audio if no samples found
            current_app.logger.info(f"      ⚠️ No samples found for {instrument}, using synthetic audio")
            
            # Render based on instrument type (fallback synthetic)
            if instrument in ['drums', 'percussion']:
                return self._render_drum_clip(clip, samples, sample_rate, tempo)
            elif instrument in ['bass', 'electric-bass']:
                return self._render_bass_clip(clip, samples, sample_rate, notes)
            elif instrument in ['piano', 'electric-piano', 'keyboard']:
                return self._render_piano_clip(clip, samples, sample_rate, notes)
            elif instrument in ['guitar', 'electric-guitar']:
                return self._render_guitar_clip(clip, samples, sample_rate, notes)
            elif instrument == 'vocals':
                return self._render_vocal_clip(clip, samples, sample_rate, notes)
            else:
                # Default synth rendering
                return self._render_synth_clip(clip, samples, sample_rate, notes)
                
        except Exception as e:
            current_app.logger.error(f"Error rendering clip audio: {e}")
            return np.zeros(int(clip.get('duration', 4) * sample_rate))
    
    def _render_clip_with_samples(self, clip: Dict, total_samples: int, sample_rate: int, notes: List[str], category: str, instrument: str) -> Optional[np.ndarray]:
        """Render a clip using actual instrument samples"""
        try:
            # Find available samples for this instrument
            available_samples = self._find_instrument_samples(category, instrument)
            if not available_samples:
                return None
            
            current_app.logger.info(f"      Found {len(available_samples)} samples for {category}/{instrument}")
            current_app.logger.info(f"      Available samples: {list(available_samples.keys())[:5]}...")
            
            # Create stereo output
            audio_output = np.zeros((2, total_samples))
            
            clip_duration = total_samples / sample_rate
            note_duration = clip_duration / len(notes) if notes else clip_duration
            
            for i, note in enumerate(notes):
                # Find best matching sample
                sample_path = self._find_best_sample_match(note, available_samples)
                if not sample_path:
                    current_app.logger.warning(f"      No sample found for note: {note}")
                    continue
                
                # Load the sample
                sample_audio = self._load_audio_sample(sample_path, note_duration)
                if sample_audio is None:
                    continue
                
                # Position the sample in the timeline
                start_sample = int(i * note_duration * sample_rate)
                end_sample = min(start_sample + sample_audio.shape[1], total_samples)
                sample_length = end_sample - start_sample
                
                if sample_length > 0:
                    # Mix the sample into the output
                    volume = clip.get('volume', 0.8)
                    audio_output[:, start_sample:end_sample] += sample_audio[:, :sample_length] * volume
            
            return audio_output
            
        except Exception as e:
            current_app.logger.error(f"Error rendering clip with samples: {e}")
            return None
    
    def _find_best_sample_match(self, note: str, available_samples: Dict[str, str]) -> Optional[str]:
        """Find the best matching sample for a given note/chord"""
        try:
            # Direct match first
            if note in available_samples:
                return available_samples[note]
            
            # Parse the note to extract the base note and any additional info
            base_note = self._parse_note_name(note)
            
            # Create comprehensive list of variations to try
            note_variations = []
            
            # Original note variations
            note_variations.extend([
                note,
                note.replace('#', 's'),  # Convert # to s (C# -> Cs)
                note.replace('s', '#'),  # Convert s to # (Cs -> C#)
                note.upper(),
                note.lower(),
            ])
            
            # Base note variations (for octave notes like C4, E5, etc.)
            if base_note:
                note_variations.extend([
                    base_note,
                    f"{base_note}_major",
                    f"{base_note}_minor",
                    f"{base_note}_note",
                    f"{base_note.upper()}_major",
                    f"{base_note.upper()}_minor",
                    f"{base_note.lower()}_major",
                    f"{base_note.lower()}_minor",
                ])
            
            # If note doesn't contain chord type, add major/minor variations
            if '_' not in note and not any(char.isdigit() for char in note):
                note_variations.extend([
                    f"{note}_major",
                    f"{note}_minor", 
                    f"{note}_note"
                ])
            
            # Try each variation
            for variation in note_variations:
                if variation in available_samples:
                    current_app.logger.info(f"      Found sample match: {note} -> {variation}")
                    return available_samples[variation]
            
            # Advanced matching: try to find chord samples that contain the base note
            if base_note:
                for sample_name in available_samples.keys():
                    if base_note.lower() in sample_name.lower():
                        current_app.logger.info(f"      Found partial match: {note} -> {sample_name}")
                        return available_samples[sample_name]
            
            # Fallback to any available sample
            if available_samples:
                fallback = list(available_samples.values())[0]
                current_app.logger.info(f"      Using fallback sample for {note}: {Path(fallback).stem}")
                return fallback
            
            return None
            
        except Exception as e:
            current_app.logger.error(f"Error finding sample match for {note}: {e}")
            return None
    
    def _parse_note_name(self, note: str) -> Optional[str]:
        """Parse a note string to extract the base note name"""
        try:
            # Handle different note formats:
            # - "C4", "F#5", "Bb3" -> "C", "F#", "Bb"
            # - "C_major", "Am_minor" -> "C", "Am"
            # - "C", "F#", "Bb" -> "C", "F#", "Bb"
            
            # Remove octave numbers
            import re
            note_without_octave = re.sub(r'\d+', '', note)
            
            # Handle chord notation (e.g., "C_major" -> "C")
            if '_' in note_without_octave:
                base_note = note_without_octave.split('_')[0]
            else:
                base_note = note_without_octave
            
            # Clean up the base note
            base_note = base_note.strip()
            
            # Validate it's a proper note (starts with A-G)
            if base_note and base_note[0].upper() in 'ABCDEFG':
                return base_note
            
            return None
            
        except Exception as e:
            current_app.logger.error(f"Error parsing note name {note}: {e}")
            return None
    
    def _extract_notes_from_clip(self, clip: Dict, instrument: str, song_key: str) -> list:
        """Extract notes from a clip, handling both direct notes and lyrics structure"""
        try:
            # First, check for direct notes array
            if 'notes' in clip and clip['notes']:
                return clip['notes']
            
            # For vocal clips, check for lyrics structure
            if instrument == 'vocals' and 'lyrics' in clip:
                extracted_notes = []
                for lyric_fragment in clip['lyrics']:
                    if 'notes' in lyric_fragment and lyric_fragment['notes']:
                        extracted_notes.extend(lyric_fragment['notes'])
                
                if extracted_notes:
                    current_app.logger.info(f"      Extracted {len(extracted_notes)} notes from lyrics structure")
                    return extracted_notes
            
            # If no notes found, generate default ones
            current_app.logger.info(f"      No notes found in clip, generating defaults for {instrument}")
            return self._generate_default_notes(instrument, song_key)
            
        except Exception as e:
            current_app.logger.error(f"Error extracting notes from clip: {e}")
            return self._generate_default_notes(instrument, song_key)
    
    def _generate_default_notes(self, instrument: str, song_key: str) -> list:
        """Generate appropriate default notes for an instrument"""
        # Basic note mapping for different keys
        key_scales = {
            'C': ['C4', 'D4', 'E4', 'F4', 'G4', 'A4', 'B4', 'C5'],
            'G': ['G4', 'A4', 'B4', 'C5', 'D5', 'E5', 'F#5', 'G5'],
            'F': ['F4', 'G4', 'A4', 'Bb4', 'C5', 'D5', 'E5', 'F5'],
            'D': ['D4', 'E4', 'F#4', 'G4', 'A4', 'B4', 'C#5', 'D5'],
            'A': ['A4', 'B4', 'C#5', 'D5', 'E5', 'F#5', 'G#5', 'A5'],
            'E': ['E4', 'F#4', 'G#4', 'A4', 'B4', 'C#5', 'D#5', 'E5'],
        }
        
        scale = key_scales.get(song_key, key_scales['C'])
        
        if instrument in ['drums', 'percussion']:
            return ['C4'] * 8  # Consistent drum hits
        elif instrument in ['bass', 'electric-bass']:
            # Lower octave for bass
            return [note.replace('4', '2').replace('5', '3') for note in scale[:4]]
        elif instrument in ['piano', 'guitar']:
            # Chord progression pattern
            return [scale[0], scale[2], scale[4], scale[0]]  # I-iii-V-I pattern
        else:
            return scale[:4]  # Simple melody
    
    def _render_drum_clip(self, clip: Dict, samples: int, sample_rate: int, tempo: int) -> np.ndarray:
        """Render drum/percussion audio"""
        audio_mono = np.zeros(samples)
        
        # Create a basic drum pattern based on tempo
        beat_duration = 60.0 / tempo
        beat_samples = int(beat_duration * sample_rate)
        
        # Basic kick and snare pattern
        for beat in range(int(samples / beat_samples)):
            beat_start = beat * beat_samples
            
            if beat % 4 == 0 or beat % 4 == 2:  # Kick on 1 and 3
                # Generate kick drum (low frequency thump)
                kick_duration = int(0.1 * sample_rate)
                t = np.linspace(0, 0.1, kick_duration, False)
                kick = np.sin(2 * np.pi * 60 * t) * np.exp(-t * 30) * 0.8
                
                end_idx = min(beat_start + len(kick), samples)
                audio_mono[beat_start:end_idx] += kick[:end_idx - beat_start]
            
            if beat % 4 == 1 or beat % 4 == 3:  # Snare on 2 and 4
                # Generate snare (noise burst with tone)
                snare_duration = int(0.05 * sample_rate)
                t = np.linspace(0, 0.05, snare_duration, False)
                noise = np.random.normal(0, 0.3, snare_duration)
                tone = np.sin(2 * np.pi * 200 * t) * 0.4
                snare = (noise + tone) * np.exp(-t * 40) * 0.6
                
                end_idx = min(beat_start + len(snare), samples)
                audio_mono[beat_start:end_idx] += snare[:end_idx - beat_start]
        
        # Convert to stereo
        return np.stack([audio_mono, audio_mono])
    
    def _render_bass_clip(self, clip: Dict, samples: int, sample_rate: int, notes: list) -> np.ndarray:
        """Render bass audio"""
        audio_mono = np.zeros(samples)
        t = np.linspace(0, samples / sample_rate, samples, False)
        
        # Note to frequency mapping (bass range)
        note_frequencies = {
            'C2': 65.4, 'D2': 73.4, 'E2': 82.4, 'F2': 87.3, 'G2': 98.0, 'A2': 110.0, 'B2': 123.5,
            'C3': 130.8, 'D3': 146.8, 'E3': 164.8, 'F3': 174.6, 'G3': 196.0, 'A3': 220.0, 'B3': 246.9
        }
        
        note_duration = samples / len(notes) if notes else samples
        
        for i, note in enumerate(notes):
            freq = note_frequencies.get(note, 82.4)  # Default to E2
            start_sample = int(i * note_duration)
            end_sample = int((i + 1) * note_duration)
            
            # Generate bass tone with harmonics
            note_t = t[start_sample:end_sample]
            bass_tone = (
                np.sin(2 * np.pi * freq * note_t) * 0.7 +           # Fundamental
                np.sin(2 * np.pi * freq * 2 * note_t) * 0.2 +       # Octave
                np.sin(2 * np.pi * freq * 3 * note_t) * 0.1         # Third harmonic
            )
            
            # Apply envelope (attack, sustain, release)
            envelope = np.ones_like(bass_tone)
            attack_samples = int(0.02 * sample_rate)  # 20ms attack
            release_samples = int(0.1 * sample_rate)  # 100ms release
            
            if len(envelope) > attack_samples:
                envelope[:attack_samples] = np.linspace(0, 1, attack_samples)
            if len(envelope) > release_samples:
                envelope[-release_samples:] = np.linspace(1, 0, release_samples)
                
            audio_mono[start_sample:end_sample] += bass_tone * envelope
        
        # Convert to stereo
        return np.stack([audio_mono, audio_mono])
    
    def _render_piano_clip(self, clip: Dict, samples: int, sample_rate: int, notes: list) -> np.ndarray:
        """Render piano audio"""
        audio_mono = np.zeros(samples)
        
        # Piano note frequencies
        note_frequencies = {
            'C4': 261.6, 'D4': 293.7, 'E4': 329.6, 'F4': 349.2, 'G4': 392.0, 'A4': 440.0, 'B4': 493.9,
            'C5': 523.3, 'D5': 587.3, 'E5': 659.3, 'F5': 698.5, 'G5': 784.0, 'A5': 880.0, 'B5': 987.8
        }
        
        note_duration = samples / len(notes) if notes else samples
        
        for i, note in enumerate(notes):
            freq = note_frequencies.get(note, 261.6)  # Default to C4
            start_sample = int(i * note_duration)
            end_sample = int((i + 1) * note_duration)
            length = end_sample - start_sample
            
            # Generate piano-like tone with harmonics and decay
            t = np.linspace(0, length / sample_rate, length, False)
            piano_tone = (
                np.sin(2 * np.pi * freq * t) * 0.5 +                    # Fundamental
                np.sin(2 * np.pi * freq * 2 * t) * 0.2 +                # Octave
                np.sin(2 * np.pi * freq * 3 * t) * 0.1 +                # Third harmonic
                np.sin(2 * np.pi * freq * 4 * t) * 0.05                 # Fourth harmonic
            )
            
            # Piano-like envelope (quick attack, exponential decay)
            envelope = np.exp(-t * 2) * (1 - np.exp(-t * 50))
            
            audio_mono[start_sample:end_sample] += piano_tone * envelope
        
        # Convert to stereo
        return np.stack([audio_mono, audio_mono])
    
    def _render_guitar_clip(self, clip: Dict, samples: int, sample_rate: int, notes: list) -> np.ndarray:
        """Render guitar audio"""
        audio_mono = np.zeros(samples)
        
        # Guitar note frequencies
        note_frequencies = {
            'E2': 82.4, 'A2': 110.0, 'D3': 146.8, 'G3': 196.0, 'B3': 246.9, 'E4': 329.6,
            'F3': 174.6, 'C4': 261.6, 'F4': 349.2, 'A4': 440.0, 'C5': 523.3
        }
        
        note_duration = samples / len(notes) if notes else samples
        
        for i, note in enumerate(notes):
            freq = note_frequencies.get(note, 196.0)  # Default to G3
            start_sample = int(i * note_duration)
            end_sample = int((i + 1) * note_duration)
            length = end_sample - start_sample
            
            # Generate guitar-like tone with slight distortion
            t = np.linspace(0, length / sample_rate, length, False)
            guitar_tone = np.sin(2 * np.pi * freq * t)
            
            # Add slight distortion for guitar character
            guitar_tone = np.tanh(guitar_tone * 2) * 0.7
            
            # Guitar envelope (pluck attack, sustained decay)
            envelope = np.exp(-t * 1.5) * (1 - np.exp(-t * 100))
            
            audio_mono[start_sample:end_sample] += guitar_tone * envelope
        
        # Convert to stereo
        return np.stack([audio_mono, audio_mono])
    
    def _render_vocal_clip(self, clip: Dict, samples: int, sample_rate: int, notes: list) -> np.ndarray:
        """Render vocal audio"""
        audio_mono = np.zeros(samples)
        
        # Vocal frequencies (typically in singing range)
        note_frequencies = {
            'C4': 261.6, 'D4': 293.7, 'E4': 329.6, 'F4': 349.2, 'G4': 392.0, 'A4': 440.0, 'B4': 493.9,
            'C5': 523.3, 'D5': 587.3, 'E5': 659.3, 'F5': 698.5, 'G5': 784.0
        }
        
        note_duration = samples / len(notes) if notes else samples
        
        for i, note in enumerate(notes):
            freq = note_frequencies.get(note, 349.2)  # Default to F4
            start_sample = int(i * note_duration)
            end_sample = int((i + 1) * note_duration)
            length = end_sample - start_sample
            
            # Generate vocal-like tone with formants
            t = np.linspace(0, length / sample_rate, length, False)
            
            # Basic vocal tone with formants simulation
            vocal_tone = (
                np.sin(2 * np.pi * freq * t) * 0.6 +                   # Fundamental
                np.sin(2 * np.pi * freq * 2 * t) * 0.3 +               # First formant
                np.sin(2 * np.pi * freq * 3 * t) * 0.1                 # Second formant
            )
            
            # Add vibrato
            vibrato = 1 + 0.05 * np.sin(2 * np.pi * 5 * t)
            vocal_tone *= vibrato
            
            # Vocal envelope (smooth attack and release)
            envelope = np.ones_like(vocal_tone)
            attack_samples = int(0.1 * sample_rate)
            release_samples = int(0.1 * sample_rate)
            
            if len(envelope) > attack_samples:
                envelope[:attack_samples] = np.linspace(0, 1, attack_samples)
            if len(envelope) > release_samples:
                envelope[-release_samples:] = np.linspace(1, 0, release_samples)
            
            audio_mono[start_sample:end_sample] += vocal_tone * envelope
        
        # Convert to stereo
        return np.stack([audio_mono, audio_mono])
    
    def _render_synth_clip(self, clip: Dict, samples: int, sample_rate: int, notes: list) -> np.ndarray:
        """Render synthesizer audio"""
        audio_mono = np.zeros(samples)
        
        # Synth note frequencies
        note_frequencies = {
            'C4': 261.6, 'D4': 293.7, 'E4': 329.6, 'F4': 349.2, 'G4': 392.0, 'A4': 440.0, 'B4': 493.9,
            'C5': 523.3, 'D5': 587.3, 'E5': 659.3, 'F5': 698.5, 'G5': 784.0
        }
        
        note_duration = samples / len(notes) if notes else samples
        
        for i, note in enumerate(notes):
            freq = note_frequencies.get(note, 261.6)  # Default to C4
            start_sample = int(i * note_duration)
            end_sample = int((i + 1) * note_duration)
            length = end_sample - start_sample
            
            # Generate synthetic tone
            t = np.linspace(0, length / sample_rate, length, False)
            
            # Different waveforms for synth character
            saw_wave = 2 * (freq * t - np.floor(freq * t + 0.5))
            square_wave = np.sign(np.sin(2 * np.pi * freq * t))
            sine_wave = np.sin(2 * np.pi * freq * t)
            
            # Blend waveforms for rich synth sound
            synth_tone = (sine_wave * 0.5 + saw_wave * 0.3 + square_wave * 0.2) * 0.4
            
            # Synth envelope (ADSR)
            envelope = np.ones_like(synth_tone)
            attack = int(0.05 * sample_rate)
            decay = int(0.1 * sample_rate)
            release = int(0.2 * sample_rate)
            
            if len(envelope) > attack:
                envelope[:attack] = np.linspace(0, 1, attack)
            if len(envelope) > attack + decay:
                envelope[attack:attack+decay] = np.linspace(1, 0.7, decay)
            if len(envelope) > release:
                envelope[-release:] = np.linspace(envelope[-release], 0, release)
            
            audio_mono[start_sample:end_sample] += synth_tone * envelope
        
        # Convert to stereo
        return np.stack([audio_mono, audio_mono])
    
    def _apply_master_effects(self, audio: np.ndarray) -> np.ndarray:
        """Apply master effects to the final audio mix"""
        try:
            # Simple master compression (basic limiting)
            threshold = 0.8
            ratio = 4.0
            
            for channel in range(audio.shape[1]):
                channel_audio = audio[:, channel]
                
                # Simple peak limiting
                peaks = np.abs(channel_audio) > threshold
                if np.any(peaks):
                    over_threshold = channel_audio[peaks]
                    compressed = np.sign(over_threshold) * (
                        threshold + (np.abs(over_threshold) - threshold) / ratio
                    )
                    channel_audio[peaks] = compressed
                
                audio[:, channel] = channel_audio
            
            return audio
            
        except Exception as e:
            current_app.logger.error(f"Error applying master effects: {e}")
            return audio
    
    def get_export_file(self, file_id: str) -> Dict:
        """Get exported file data"""
        try:
            # Check if audio file exists
            export_path = os.path.join(self.export_dir, f"{file_id}.wav")
            metadata_path = os.path.join(self.export_dir, f"{file_id}.json")
            
            if not os.path.exists(export_path) or not os.path.exists(metadata_path):
                raise FileNotFoundError(f"Export file not found: {file_id}")
            
            # Load metadata
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            
            # Load audio data
            with open(export_path, 'rb') as f:
                audio_data = f.read()
            
            return {
                'data': audio_data,
                'filename': metadata['filename'],
                'content_type': metadata['content_type'],
                'size': metadata['size']
            }
        except FileNotFoundError:
            raise
        except Exception as e:
            current_app.logger.error(f"Error loading export file {file_id}: {e}")
            raise FileNotFoundError(f"Export file not found: {file_id}")
    
    def cleanup_export_file(self, file_id: str):
        """Clean up temporary export files"""
        try:
            export_path = os.path.join(self.export_dir, f"{file_id}.wav")
            metadata_path = os.path.join(self.export_dir, f"{file_id}.json")
            
            if os.path.exists(export_path):
                os.remove(export_path)
            if os.path.exists(metadata_path):
                os.remove(metadata_path)
                
        except Exception as e:
            current_app.logger.error(f"Error cleaning up export file {file_id}: {e}")
    
    def cleanup_old_exports(self, max_age_hours: int = 1):
        """Clean up export files older than specified hours"""
        try:
            import time
            current_time = time.time()
            max_age_seconds = max_age_hours * 3600
            
            for filename in os.listdir(self.export_dir):
                filepath = os.path.join(self.export_dir, filename)
                if os.path.isfile(filepath):
                    file_age = current_time - os.path.getctime(filepath)
                    if file_age > max_age_seconds:
                        os.remove(filepath)
                        current_app.logger.info(f"Cleaned up old export file: {filename}")
                        
        except Exception as e:
            current_app.logger.error(f"Error cleaning up old exports: {e}")


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
