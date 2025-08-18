"""
Voice Service - Refactored
Main coordination service for voice management
"""

import logging
import os
from typing import List, Dict, Optional, Any
from pathlib import Path
from werkzeug.datastructures import FileStorage
from flask import current_app

from .audio_generator import AudioGenerator
from .voice_registry import VoiceRegistry
from .training_manager import TrainingManager

logger = logging.getLogger(__name__)


class VoiceService:
    """Main voice service that coordinates all voice-related functionality"""
    
    def __init__(self, voices_dir=None, training_dir=None, models_dir=None):
        # Initialize directories - use provided paths or Flask config
        try:
            # Try to get from Flask app context
            self.voices_dir = Path(voices_dir or current_app.config.get('VOICES_DIR', 'app/data/voices'))
            self.training_dir = Path(training_dir or current_app.config.get('TRAINING_DIR', 'app/data/training'))
            self.models_dir = Path(models_dir or current_app.config.get('MODELS_DIR', 'app/data/models'))
        except RuntimeError:
            # Fallback for when outside Flask app context
            self.voices_dir = Path(voices_dir or 'backend/app/data/voices')
            self.training_dir = Path(training_dir or 'backend/app/data/training')
            self.models_dir = Path(models_dir or 'backend/app/data/models')
        
        # Create directories if they don't exist
        self.voices_dir.mkdir(parents=True, exist_ok=True)
        self.training_dir.mkdir(parents=True, exist_ok=True)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize components
        self.audio_generator = AudioGenerator()
        self.voice_registry = VoiceRegistry(self.voices_dir)
        self.training_manager = TrainingManager(
            self.training_dir, 
            self.models_dir, 
            self.voices_dir, 
            self.voice_registry
        )
    
    # Voice Registry Methods
    def get_available_voices(self) -> List[Dict[str, Any]]:
        """Get list of available voice profiles"""
        return self.voice_registry.get_available_voices()
    
    def get_voice(self, voice_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific voice by ID"""
        return self.voice_registry.get_voice(voice_id)
    
    def delete_voice(self, voice_id: str) -> bool:
        """Delete a custom voice profile"""
        return self.voice_registry.delete_voice(voice_id)
    
    # Audio Generation Methods
    def test_voice(self, voice_id: str, test_text: str = "mitystudio forever") -> Optional[str]:
        """Generate a test audio sample for a voice"""
        voice = self.voice_registry.get_voice(voice_id)
        
        if not voice:
            return None
        
        # For builtin voices, generate test audio
        if voice.get('type') == 'builtin':
            return self.audio_generator.generate_test_audio(test_text, voice_id)
        
        # For custom voices, use the actual model (fallback to test audio for now)
        return self._synthesize_with_model(voice_id, test_text)
    
    def synthesize_speech(self, text: str, voice_id: str, speed: float = 1.0,
                         pitch: float = 0.0, energy: float = 1.0,
                         notes: list = None, chord_name: str = None,
                         start_time: float = 0.0, duration: float = None) -> Optional[str]:
        """Synthesize speech using a trained voice with optional musical parameters"""
        voice = self.voice_registry.get_voice(voice_id)
        
        if not voice:
            return None
        
        if voice.get('type') == 'builtin':
            return self.audio_generator.generate_musical_audio(text, voice_id, notes, chord_name, duration)
        
        return self._synthesize_with_musical_model(
            voice_id, text, speed, pitch, energy, notes, chord_name, start_time, duration
        )

    def synthesize_multi_voice_clip(self, clip_data: dict) -> Optional[str]:
        """
        Synthesize a multi-voice lyrics clip using the new voices structure
        
        Args:
            clip_data: Dictionary containing the clip data with voices array
            
        Returns:
            Path to the generated audio file, or None if failed
        """
        if 'voices' not in clip_data or not clip_data['voices']:
            logger.warning("No voices array found in clip data")
            return None
            
        try:
            # Generate audio for each voice
            voice_audio_files = []
            
            for voice in clip_data['voices']:
                voice_id = voice.get('voice_id')
                lyrics_fragments = voice.get('lyrics', [])
                
                if not voice_id or not lyrics_fragments:
                    logger.warning(f"Invalid voice data: {voice}")
                    continue
                
                # Generate audio for each lyric fragment in this voice
                fragment_audio_files = []
                
                for fragment in lyrics_fragments:
                    text = fragment.get('text', '')
                    notes = fragment.get('notes', [])
                    start = fragment.get('start', 0.0)
                    duration = fragment.get('duration')
                    durations = fragment.get('durations')
                    
                    if not text:
                        continue
                    
                    # Calculate fragment duration
                    if duration is not None:
                        fragment_duration = duration
                    elif durations is not None:
                        fragment_duration = sum(durations)
                    else:
                        # Estimate duration based on text length
                        fragment_duration = len(text.split()) * 0.5
                    
                    # Synthesize this fragment
                    audio_file = self.synthesize_speech(
                        text=text,
                        voice_id=voice_id,
                        notes=notes,
                        start_time=start,
                        duration=fragment_duration
                    )
                    
                    if audio_file:
                        fragment_audio_files.append({
                            'file': audio_file,
                            'start': start,
                            'duration': fragment_duration
                        })
                
                # Combine fragments for this voice
                if fragment_audio_files:
                    voice_audio = self._combine_voice_fragments(fragment_audio_files, clip_data.get('duration', 10.0))
                    if voice_audio:
                        voice_audio_files.append(voice_audio)
            
            # Mix all voices together
            if voice_audio_files:
                return self._mix_voices(voice_audio_files, clip_data.get('duration', 10.0))
            
            return None
            
        except Exception as e:
            logger.error(f"Error synthesizing multi-voice clip: {e}")
            return None
    
    # Training Methods
    def train_voice_from_recording(self, voice_name: str, audio_file: FileStorage, 
                                 duration: float, sample_rate: int, language: str = 'en') -> str:
        """Train a new voice from a single recording"""
        return self.training_manager.train_voice_from_recording(
            voice_name, audio_file, duration, sample_rate, language
        )

    def train_voice_from_files(self, voice_name: str, audio_files: List[FileStorage],
                             language: str = 'en', epochs: int = 100, 
                             speaker_embedding: bool = True) -> str:
        """Train a new voice from multiple audio files"""
        return self.training_manager.train_voice_from_files(
            voice_name, audio_files, language, epochs, speaker_embedding
        )

    def get_training_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of a training job"""
        return self.training_manager.get_training_status(job_id)

    def cancel_training(self, job_id: str) -> bool:
        """Cancel a training job"""
        return self.training_manager.cancel_training(job_id)
    
    # Private helper methods
    def _synthesize_with_model(self, voice_id: str, text: str, speed: float = 1.0,
                              pitch: float = 0.0, energy: float = 1.0) -> Optional[str]:
        """Synthesize speech with a custom trained model using RVC"""
        voice = self.voice_registry.get_voice(voice_id)
        
        if not voice or not voice.get('model_path'):
            logger.warning(f"No model found for voice {voice_id}, falling back to custom voice simulation")
            return self._generate_custom_voice_audio(text, voice_id, voice)
        
        try:
            # Use RVC service for synthesis with the custom model
            model_path = voice.get('model_path')
            logger.info(f"Using RVC synthesis for custom voice {voice_id} with model: {model_path}")
            
            # Create output file
            import tempfile
            output_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
            output_file.close()
            
            # Use RVC service for synthesis
            from app.services.rvc_service import RVCService
            rvc_service = RVCService()
            
            result_path = rvc_service.synthesize_voice(
                voice_id=voice_id,
                text=text,
                output_path=output_file.name,
                speed=speed,
                pitch=pitch,
                energy=energy
            )
            
            return result_path
            
        except Exception as e:
            logger.error(f"DiffSinger synthesis failed for {voice_id}: {e}")
            # Fallback to custom voice simulation
            return self._generate_custom_voice_audio(text, voice_id, voice)
    
    def _generate_custom_voice_audio(self, text: str, voice_id: str, voice_data: dict = None) -> str:
        """Generate distinctive audio for custom voices based on analyzed voice characteristics"""
        logger.info(f"Generating custom voice audio for {voice_id}")
        
        # Get voice characteristics from voice data or load from file
        voice_characteristics = None
        if voice_data and voice_data.get('voice_characteristics'):
            voice_characteristics = voice_data['voice_characteristics']
        elif voice_data and voice_data.get('model_path'):
            # Try to load characteristics from model info file
            try:
                model_dir = Path(voice_data['model_path']).parent
                info_file = model_dir / 'info.json'
                if info_file.exists():
                    import json
                    with open(info_file, 'r') as f:
                        model_info = json.load(f)
                        voice_characteristics = model_info.get('voice_characteristics', {})
            except Exception as e:
                logger.warning(f"Failed to load voice characteristics for {voice_id}: {e}")
        
        # If no characteristics found, generate based on voice name/id
        if not voice_characteristics:
            logger.info(f"No analyzed characteristics found for {voice_id}, using name-based generation")
            voice_name = voice_data.get('name', voice_id) if voice_data else voice_id
            name_hash = hash(voice_name) % 1000
            
            voice_characteristics = {
                'fundamental_freq': 140 + (name_hash % 100),
                'formant_shift': 0.8 + (name_hash % 50) / 100,
                'vibrato_rate': 4.0 + (name_hash % 40) / 10,
                'voice_texture': 0.3 + (name_hash % 30) / 100,
                'voice_warmth': 0.5 + (name_hash % 40) / 100,
                'voice_name': voice_name
            }
        
        # Generate audio with analyzed characteristics
        return self.audio_generator.generate_custom_voice_audio(text, voice_id, voice_characteristics)
    
    def _synthesize_with_musical_model(self, voice_id: str, text: str, speed: float,
                                     pitch: float, energy: float, notes: list = None,
                                     chord_name: str = None, start_time: float = 0.0,
                                     duration: float = None) -> str:
        """Synthesize with custom voice model using RVC"""
        logger.info(f"🎤 RVC synthesis: voice={voice_id}, text='{text}', notes={notes}, chord={chord_name}")
        
        try:
            # Check if this is an RVC trained voice
            from app.services.rvc_service import RVCService
            rvc_service = RVCService()
            
            # Get list of available RVC voices
            rvc_voices = rvc_service.list_singing_voices()
            logger.info(f"🎤 Available RVC voices: {[v.get('voice_id') for v in rvc_voices]}")
            
            # Check if this voice exists in RVC
            rvc_voice = None
            for voice in rvc_voices:
                if voice.get('voice_id') == voice_id:
                    rvc_voice = voice
                    break
            
            if rvc_voice and rvc_voice.get('status') == 'ready':
                logger.info(f"🎤 Using RVC synthesis for trained voice: {voice_id}")
                
                # Use the proper RVC synthesis method with custom parameters
                import tempfile
                from pathlib import Path
                
                # Create output file
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                    output_path = Path(f.name)
                
                # Prepare parameters
                voice_characteristics = rvc_voice.get('voice_characteristics', {})
                notes_list = notes if isinstance(notes, list) else [notes] if notes else ['C4']
                duration = duration or 4.0
                
                logger.info(f"🎤 Calling RVC generate_singing_audio with syllable-based synthesis...")
                
                # Use the RVC service's main singing generation method
                audio_path = rvc_service.generate_singing_audio(
                    text=text,
                    voice_id=voice_id,
                    notes=notes_list,
                    duration=duration
                )
                
                if audio_path and os.path.exists(audio_path):
                    logger.info(f"🎤 ✅ RVC synthesis successful: {audio_path}")
                    return audio_path
                else:
                    logger.warning(f"🎤 RVC synthesis failed for {voice_id}, falling back to test singing")
                    # Fallback to test singing if custom synthesis fails
                    test_audio = rvc_service.synthesize_test_singing(voice_id)
                    if test_audio and os.path.exists(test_audio):
                        return test_audio
                        
            else:
                logger.info(f"🎤 Voice {voice_id} not found in RVC or not ready, using musical fallback")
                
        except Exception as e:
            logger.error(f"🎤 Error in RVC synthesis for {voice_id}: {e}")
            logger.info("🎤 Falling back to musical audio generation")
        
        # Final fallback to musical audio generation
        logger.info(f"🎤 Using fallback musical audio generation for {voice_id}")
        return self.audio_generator.generate_musical_audio(text, voice_id, notes, chord_name, duration)
    
    def _combine_voice_fragments(self, fragment_audio_files: List[dict], total_duration: float) -> Optional[str]:
        """
        Combine multiple audio fragments for a single voice into one audio file
        
        Args:
            fragment_audio_files: List of dicts with 'file', 'start', 'duration' keys
            total_duration: Total duration of the final audio
            
        Returns:
            Path to combined audio file
        """
        try:
            import numpy as np
            import soundfile as sf
            import tempfile
            import os
            
            # Create output buffer
            sample_rate = 22050
            output_samples = int(total_duration * sample_rate)
            output_audio = np.zeros(output_samples, dtype=np.float32)
            
            # Combine fragments
            for fragment in fragment_audio_files:
                try:
                    # Load fragment audio
                    audio_data, sr = sf.read(fragment['file'])
                    
                    # Resample if needed
                    if sr != sample_rate:
                        # Simple resampling (for production, use librosa.resample)
                        audio_data = np.interp(
                            np.linspace(0, len(audio_data), int(len(audio_data) * sample_rate / sr)),
                            np.arange(len(audio_data)),
                            audio_data
                        )
                    
                    # Calculate position in output
                    start_sample = int(fragment['start'] * sample_rate)
                    end_sample = min(start_sample + len(audio_data), output_samples)
                    audio_length = end_sample - start_sample
                    
                    if audio_length > 0:
                        # Add to output (with basic mixing)
                        output_audio[start_sample:end_sample] += audio_data[:audio_length]
                        
                except Exception as e:
                    logger.warning(f"Error processing fragment {fragment['file']}: {e}")
                    continue
            
            # Normalize to prevent clipping
            max_val = np.max(np.abs(output_audio))
            if max_val > 1.0:
                output_audio = output_audio / max_val * 0.95
            
            # Save combined audio
            output_path = tempfile.mktemp(suffix='.wav')
            sf.write(output_path, output_audio, sample_rate)
            
            # Clean up fragment files
            for fragment in fragment_audio_files:
                try:
                    os.remove(fragment['file'])
                except:
                    pass
            
            return output_path
            
        except Exception as e:
            logger.error(f"Error combining voice fragments: {e}")
            return None

    def _mix_voices(self, voice_audio_files: List[str], total_duration: float) -> Optional[str]:
        """
        Mix multiple voice audio files into a single output
        
        Args:
            voice_audio_files: List of audio file paths
            total_duration: Duration of the final mixed audio
            
        Returns:
            Path to mixed audio file
        """
        try:
            import numpy as np
            import soundfile as sf
            import tempfile
            import os
            
            if not voice_audio_files:
                return None
            
            if len(voice_audio_files) == 1:
                # Only one voice, just return it
                return voice_audio_files[0]
            
            # Create output buffer
            sample_rate = 22050
            output_samples = int(total_duration * sample_rate)
            output_audio = np.zeros(output_samples, dtype=np.float32)
            
            # Mix all voices
            for voice_file in voice_audio_files:
                try:
                    # Load voice audio
                    audio_data, sr = sf.read(voice_file)
                    
                    # Resample if needed
                    if sr != sample_rate:
                        audio_data = np.interp(
                            np.linspace(0, len(audio_data), int(len(audio_data) * sample_rate / sr)),
                            np.arange(len(audio_data)),
                            audio_data
                        )
                    
                    # Add to mix (with length matching)
                    mix_length = min(len(audio_data), output_samples)
                    output_audio[:mix_length] += audio_data[:mix_length]
                    
                except Exception as e:
                    logger.warning(f"Error processing voice file {voice_file}: {e}")
                    continue
            
            # Normalize the final mix
            max_val = np.max(np.abs(output_audio))
            if max_val > 1.0:
                output_audio = output_audio / max_val * 0.95
            
            # Save mixed audio
            output_path = tempfile.mktemp(suffix='.wav')
            sf.write(output_path, output_audio, sample_rate)
            
            # Clean up individual voice files
            for voice_file in voice_audio_files:
                try:
                    os.remove(voice_file)
                except:
                    pass
            
            return output_path
            
        except Exception as e:
            logger.error(f"Error mixing voices: {e}")
            return None
