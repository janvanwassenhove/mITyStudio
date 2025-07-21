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
                with open(self.jobs_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if not content:
                        logger.warning("Training jobs file is empty, starting fresh")
                        return {}
                    return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Corrupted training jobs file, backing up and starting fresh: {e}")
            # Backup corrupted file
            backup_file = self.jobs_file.with_suffix('.json.corrupted')
            try:
                import shutil
                shutil.copy2(self.jobs_file, backup_file)
                logger.info(f"Corrupted file backed up to: {backup_file}")
            except Exception as backup_error:
                logger.warning(f"Failed to backup corrupted file: {backup_error}")
            return {}
        except Exception as e:
            logger.warning(f"Failed to load training jobs: {e}")
        return {}
    
    def _save_jobs(self):
        """Save training jobs to file with atomic write"""
        try:
            # Create parent directory if it doesn't exist
            self.jobs_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Use atomic write (write to temp file then rename)
            temp_file = self.jobs_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(self.training_jobs, f, indent=2, ensure_ascii=False)
                f.flush()  # Ensure data is written to disk
                import os
                os.fsync(f.fileno())  # Force write to disk
            
            # Atomic rename
            import shutil
            shutil.move(str(temp_file), str(self.jobs_file))
            
        except Exception as e:
            logger.error(f"Failed to save training jobs: {e}")
            # Clean up temp file if it exists
            temp_file = self.jobs_file.with_suffix('.tmp')
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except:
                    pass
    
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
        """Run the actual training process using RVC"""
        job = self.training_jobs.get(job_id)
        if not job:
            return
        
        try:
            job['status'] = 'processing'
            self._save_jobs()  # Persist status change
            job_dir = self.training_dir / job_id
            voice_id = job['voiceId']
            voice_name = job['voiceName']
            
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
                    
                    job['estimated_time_remaining'] = f"{int(estimated_remaining // 60)}m {int(estimated_remaining % 60)}s"
                else:
                    job['estimated_time_remaining'] = "Calculating..."
                
                job['elapsed_time'] = f"{int(elapsed_time // 60)}m {int(elapsed_time % 60)}s"
                job['progress'] = progress
                self._save_jobs()  # Persist progress updates
                
                logger.info(f"Training progress for {job_id}: {progress}% (elapsed: {job['elapsed_time']}, remaining: {job['estimated_time_remaining']})")
            
            # Generate transcriptions for voice metadata
            logger.info("Generating transcriptions for audio files...")
            transcriptions = []
            
            # Update progress for transcription phase
            cancellation_aware_progress_callback(30)  # Starting transcriptions
            
            for i, audio_file in enumerate(audio_files):
                try:
                    logger.info(f"Transcribing audio file {i+1}/{len(audio_files)}: {audio_file}")
                    
                    # Update progress during transcription
                    transcription_progress = 30 + (i / len(audio_files)) * 20  # 30-50% for transcription
                    cancellation_aware_progress_callback(int(transcription_progress))
                    
                    transcription = self.transcription_service.transcribe_audio(audio_file)
                    
                    transcription['audio_file'] = audio_file
                    transcriptions.append(transcription)
                    
                    logger.info(f"Transcription complete: {transcription['text'][:50]}...")
                    
                except Exception as e:
                    logger.warning(f"Failed to transcribe {audio_file}: {e}")
                    # Don't fail the entire training for transcription errors
                    transcriptions.append({
                        'audio_file': audio_file,
                        'text': f"[Audio file for voice training - transcription unavailable]",
                        'error': str(e),
                        'engine': 'fallback'
                    })
                    # Continue with training even if transcription fails
            
            job['transcriptions'] = transcriptions
            self._save_jobs()  # Save transcriptions
            
            # Train RVC model for voice synthesis
            logger.info(f"Training RVC model for voice synthesis: {voice_name}")
            
            # Update progress for training start
            cancellation_aware_progress_callback(60)  # Training started
            
            try:
                from app.services.rvc_service import RVCService
                rvc_service = RVCService()
                
                # Convert audio file paths to Path objects
                wav_file_paths = [Path(audio_file) for audio_file in audio_files]
                
                # Train RVC model with the same audio files
                # Note: clone_singing_voice expects a folder path, so we need to create a temporary folder
                wav_folder = job_dir / "training_audio"
                wav_folder.mkdir(exist_ok=True)
                
                # Update progress for preprocessing
                cancellation_aware_progress_callback(70)  # Preprocessing files
                
                # Copy files to training folder if they're not already there
                for wav_file in wav_file_paths:
                    if wav_file.parent != wav_folder:
                        import shutil
                        shutil.copy2(wav_file, wav_folder / wav_file.name)
                
                # Update progress for training phase
                cancellation_aware_progress_callback(80)  # Starting RVC training
                
                rvc_result = rvc_service.clone_singing_voice(voice_name, str(wav_folder))
                logger.info(f"RVC model trained successfully: {rvc_result.get('status', 'unknown')}")
                
                # Update progress for completion
                cancellation_aware_progress_callback(95)  # Training completed, finalizing
                
                # Update job with RVC info
                job['rvc_model_trained'] = True
                job['rvc_model_path'] = rvc_result.get('model_path', '')
                self._save_jobs()
                
                # Use RVC result as training results
                training_results = rvc_result
                
            except Exception as rvc_error:
                logger.warning(f"RVC training failed for {voice_name}: {rvc_error}")
                job['rvc_model_trained'] = False
                job['rvc_error'] = str(rvc_error)
                self._save_jobs()
                raise rvc_error
            
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
