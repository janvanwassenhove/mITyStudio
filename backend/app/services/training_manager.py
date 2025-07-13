"""
Training Manager Module
Handles voice training jobs and progress tracking
"""

import uuid
import time
import threading
import json
import logging
from typing import List, Dict, Optional, Any
from pathlib import Path
from werkzeug.datastructures import FileStorage
import librosa
import soundfile as sf

from .diffsinger_engine import DiffSingerEngine, DiffSingerConfig
from .training_monitor import training_monitor
from .voice_registry import VoiceRegistry
from .voice_analyzer import VoiceAnalyzer
from .transcription_service import TranscriptionService

logger = logging.getLogger(__name__)


class TrainingManager:
    """Manages voice training jobs and progress"""
    
    def __init__(self, training_dir: Path, models_dir: Path, voices_dir: Path, voice_registry: VoiceRegistry):
        self.training_dir = training_dir
        self.models_dir = models_dir
        self.voices_dir = voices_dir
        self.voice_registry = voice_registry
        
        # Initialize DiffSinger engine
        self.diffsinger = DiffSingerEngine(
            models_dir=str(self.models_dir),
            data_dir=str(self.training_dir)
        )
        
        # Initialize voice analyzer
        self.voice_analyzer = VoiceAnalyzer()
        
        # Initialize transcription service
        self.transcription_service = TranscriptionService()
        
        # Start training monitor
        training_monitor.start_monitoring()
        
        # Training job tracking with persistence
        self.jobs_file = self.training_dir / 'training_jobs.json'
        self.training_jobs = self._load_jobs()
    
    def _load_jobs(self) -> Dict[str, Any]:
        """Load training jobs from file"""
        try:
            if self.jobs_file.exists():
                with open(self.jobs_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load training jobs: {e}")
        return {}
    
    def _save_jobs(self):
        """Save training jobs to file"""
        try:
            with open(self.jobs_file, 'w') as f:
                json.dump(self.training_jobs, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save training jobs: {e}")
    
    def train_voice_from_recording(self, voice_name: str, audio_file: FileStorage, 
                                 duration: float, sample_rate: int, language: str = 'en') -> str:
        """Train a new voice from a single recording"""
        
        # Validate input
        if duration < 10:  # Minimum 10 seconds
            raise ValueError("Recording must be at least 10 seconds long")
        
        if not self._is_audio_file(audio_file.filename):
            raise ValueError("Invalid audio file format")
        
        # Generate job ID
        job_id = str(uuid.uuid4())
        voice_id = f"voice-{int(time.time())}"
        
        # Create training directory
        job_dir = self.training_dir / job_id
        job_dir.mkdir(exist_ok=True)
        
        # Save audio file with proper extension
        original_filename = audio_file.filename or 'recording'
        is_wav_input = self._is_wav_file(original_filename)
        
        # Always save as WAV for training consistency
        audio_path = job_dir / 'recording.wav'
        audio_file.save(str(audio_path))
        
        # Convert to proper WAV format for training if needed
        self._prepare_audio_file(str(audio_path), sample_rate)
        
        logger.info(f"Voice training started: {voice_name}")
        logger.info(f"  - Original file: {original_filename} ({'WAV' if is_wav_input else 'converted to WAV'})")
        logger.info(f"  - Training file: recording.wav")
        logger.info(f"  - Duration: {duration}s")
        logger.info(f"  - Sample rate: {sample_rate}Hz")
        logger.info(f"  - Language: {language}")
        
        # Create training job
        training_job = {
            'id': job_id,
            'voiceId': voice_id,
            'voiceName': voice_name,
            'status': 'pending',
            'progress': 0,
            'audioFiles': ['recording.wav'],
            'language': language,
            'type': 'recording',
            'created_at': time.time()
        }
        
        self.training_jobs[job_id] = training_job
        self._save_jobs()  # Persist the job
        
        # Start training in background
        threading.Thread(target=self._run_training, args=(job_id,), daemon=True).start()
        
        return job_id

    def train_voice_from_files(self, voice_name: str, audio_files: List[FileStorage],
                             language: str = 'en', epochs: int = 100, 
                             speaker_embedding: bool = True) -> str:
        """Train a new voice from multiple audio files"""
        
        if len(audio_files) < 1:
            raise ValueError("At least one audio file is required")
        
        # Validate all files
        for file in audio_files:
            if not self._is_audio_file(file.filename):
                raise ValueError(f"Invalid audio file format: {file.filename}")
        
        # Generate job ID
        job_id = str(uuid.uuid4())
        voice_id = f"voice-{int(time.time())}"
        
        # Create training directory
        job_dir = self.training_dir / job_id
        job_dir.mkdir(exist_ok=True)
        
        # Save all audio files
        file_names = []
        for i, audio_file in enumerate(audio_files):
            original_filename = audio_file.filename or f'audio_{i:03d}'
            is_wav_input = self._is_wav_file(original_filename)
            
            # Always save as WAV for training consistency
            filename = f"audio_{i:03d}.wav"
            audio_path = job_dir / filename
            audio_file.save(str(audio_path))
            
            # Convert to proper format
            self._prepare_audio_file(str(audio_path))
            file_names.append(filename)
            
            logger.info(f"  - File {i+1}: {original_filename} -> {filename} ({'WAV' if is_wav_input else 'converted to WAV'})")
        
        # Create training job
        training_job = {
            'id': job_id,
            'voiceId': voice_id,
            'voiceName': voice_name,
            'status': 'pending',
            'progress': 0,
            'audioFiles': file_names,
            'language': language,
            'epochs': epochs,
            'speakerEmbedding': speaker_embedding,
            'type': 'files',
            'created_at': time.time()
        }
        
        self.training_jobs[job_id] = training_job
        self._save_jobs()  # Persist the job
        
        # Start training in background
        threading.Thread(target=self._run_training, args=(job_id,), daemon=True).start()
        
        return job_id

    def get_training_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of a training job"""
        return self.training_jobs.get(job_id)

    def cancel_training(self, job_id: str) -> bool:
        """Cancel a training job"""
        if job_id not in self.training_jobs:
            return False
        
        job = self.training_jobs[job_id]
        if job['status'] in ['completed', 'failed']:
            return False
        
        job['status'] = 'cancelled'
        self._save_jobs()  # Persist the change
        return True

    def _is_audio_file(self, filename: str) -> bool:
        """Check if file is a supported audio format"""
        if not filename:
            return False
        allowed_extensions = {'.wav', '.mp3', '.m4a', '.flac', '.ogg', '.webm'}
        return Path(filename).suffix.lower() in allowed_extensions

    def _is_wav_file(self, filename: str) -> bool:
        """Check if file is already in WAV format"""
        if not filename:
            return False
        return Path(filename).suffix.lower() == '.wav'

    def _prepare_audio_file(self, audio_path: str, target_sample_rate: int = 22050):
        """Prepare audio file for training (resample, normalize, convert to WAV)"""
        try:
            logger.info(f"Preparing audio file for training: {audio_path}")
            
            # Load audio (librosa automatically handles various formats)
            audio, sr = librosa.load(audio_path, sr=target_sample_rate)
            
            # Log original audio properties
            logger.info(f"  - Original sample rate: {sr}Hz")
            logger.info(f"  - Audio duration: {len(audio) / sr:.2f}s")
            logger.info(f"  - Audio shape: {audio.shape}")
            
            # Normalize audio to prevent clipping
            audio = librosa.util.normalize(audio)
            
            # Ensure we have the right sample rate for voice training
            if sr != target_sample_rate:
                logger.info(f"  - Resampling to {target_sample_rate}Hz for optimal training")
            
            # Save as high-quality WAV (16-bit PCM) for training
            sf.write(audio_path, audio, target_sample_rate, subtype='PCM_16')
            
            logger.info(f"✅ Audio file prepared successfully: {audio_path}")
            
        except Exception as e:
            logger.error(f"❌ Error preparing audio file {audio_path}: {e}")
            raise

    def _run_training(self, job_id: str):
        """Run the actual training process using DiffSinger"""
        job = self.training_jobs.get(job_id)
        if not job:
            return
        
        try:
            job['status'] = 'processing'
            self._save_jobs()  # Persist status change
            job_dir = self.training_dir / job_id
            voice_id = job['voiceId']
            voice_name = job['voiceName']
            
            # Prepare training configuration
            training_config = DiffSingerConfig.create_training_config(
                voice_name=voice_name,
                language=job.get('language', 'en'),
                epochs=job.get('epochs', 100),
                speaker_embedding=job.get('speakerEmbedding', True)
            )
            
            # Get audio files for training
            audio_files = []
            for filename in job['audioFiles']:
                audio_path = job_dir / filename
                if audio_path.exists():
                    audio_files.append(str(audio_path))
            
            if not audio_files:
                raise ValueError("No valid audio files found for training")
            
            # Analyze voice characteristics from uploaded audio
            logger.info("Analyzing voice characteristics from uploaded audio...")
            voice_characteristics = self.voice_analyzer.analyze_voice_characteristics(audio_files)
            job['voice_characteristics'] = voice_characteristics
            self._save_jobs()  # Save characteristics
            
            # Generate transcriptions for DiffSinger training
            logger.info("Generating transcriptions for audio files...")
            transcriptions = []
            for i, audio_file in enumerate(audio_files):
                try:
                    logger.info(f"Transcribing audio file {i+1}/{len(audio_files)}: {audio_file}")
                    transcription = self.transcription_service.transcribe_audio(audio_file)
                    
                    # Create DiffSinger-compatible transcription file
                    transcription_file = self.transcription_service.create_diffsinger_transcription(
                        audio_file, transcription
                    )
                    
                    transcription['transcription_file'] = transcription_file
                    transcription['audio_file'] = audio_file
                    transcriptions.append(transcription)
                    
                    logger.info(f"Transcription complete: {transcription['text'][:50]}...")
                    
                except Exception as e:
                    logger.error(f"Failed to transcribe {audio_file}: {e}")
                    transcriptions.append({
                        'audio_file': audio_file,
                        'text': f"[Transcription failed: {str(e)}]",
                        'error': str(e)
                    })
            
            job['transcriptions'] = transcriptions
            self._save_jobs()  # Save transcriptions
            
            # Start training with cancellation-aware progress callback
            training_start_time = time.time()
            
            def cancellation_aware_progress_callback(progress: int):
                if job['status'] == 'cancelled':
                    raise InterruptedError("Training was cancelled")
                
                # Calculate elapsed time and estimated time remaining
                elapsed_time = time.time() - training_start_time
                if progress > 0:
                    estimated_total_time = elapsed_time * 100 / progress
                    estimated_remaining = estimated_total_time - elapsed_time
                    
                    # Format time remaining
                    if estimated_remaining > 3600:  # More than 1 hour
                        time_remaining = f"{estimated_remaining / 3600:.1f} hours"
                    elif estimated_remaining > 60:  # More than 1 minute
                        time_remaining = f"{estimated_remaining / 60:.1f} minutes"
                    else:
                        time_remaining = f"{estimated_remaining:.0f} seconds"
                    
                    job['estimated_time_remaining'] = time_remaining
                    job['elapsed_time'] = f"{elapsed_time / 60:.1f} minutes"
                
                job['progress'] = progress
                job['last_updated'] = time.time()
                self._save_jobs()  # Persist progress update
            
            # Run DiffSinger training with real neural training
            logger.info(f"Starting real neural training for voice: {voice_name}")
            training_results = self.diffsinger.train_voice(
                voice_name=voice_name,
                audio_files=audio_files,
                config=training_config,
                progress_callback=cancellation_aware_progress_callback
            )
            
            # Create voice model directory in voices folder
            voice_dir = self.voices_dir / voice_id
            voice_dir.mkdir(exist_ok=True)
            
            # Copy training results
            if 'model_path' in training_results:
                model_source = Path(training_results['model_path'])
                if model_source.exists():
                    import shutil
                    shutil.copy2(model_source, voice_dir / 'model.ckpt')
            
            if 'config_path' in training_results:
                config_source = Path(training_results['config_path'])
                if config_source.exists():
                    import shutil
                    shutil.copy2(config_source, voice_dir / 'config.yaml')
            
            # Save model info
            model_info = {
                'voice_id': voice_id,
                'voice_name': voice_name,
                'model_path': str(voice_dir / 'model.ckpt'),
                'config_path': str(voice_dir / 'config.yaml'),
                'voice_characteristics': job.get('voice_characteristics', {}),
                'training_config': training_config,
                'training_results': training_results,
                'created_at': time.time()
            }
            
            with open(voice_dir / 'info.json', 'w') as f:
                json.dump(model_info, f, indent=2)
            
            # Add to voice registry
            voice_entry = {
                'id': voice_id,
                'name': voice_name,
                'type': 'custom',
                'trained': True,
                'language': job.get('language', 'en'),
                'model_path': str(voice_dir / 'model.ckpt'),
                'config_path': str(voice_dir / 'config.yaml'),
                'voice_characteristics': job.get('voice_characteristics', {}),
                'created_at': time.strftime('%Y-%m-%dT%H:%M:%SZ')
            }
            
            self.voice_registry.add_voice(voice_entry)
            
            job['status'] = 'completed'
            self._save_jobs()  # Persist completion
            logger.info(f"Training completed for voice: {voice_name} ({voice_id})")
            
        except InterruptedError:
            logger.info(f"Training was cancelled for job {job_id}")
            job['status'] = 'cancelled'
            self._save_jobs()  # Persist cancellation
        except Exception as e:
            logger.error(f"Training failed for job {job_id}: {e}")
            job['status'] = 'failed'
            job['error'] = str(e)
            self._save_jobs()  # Persist failure
