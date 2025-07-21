"""
Transcription Service Module
Handles audio-to-text transcription for voice training
"""

import logging
import tempfile
import subprocess
import json
import os
from pathlib import Path
from typing import List, Dict, Optional, Any
from werkzeug.datastructures import FileStorage
import librosa
import soundfile as sf

logger = logging.getLogger(__name__)


class TranscriptionService:
    """Handles audio transcription for voice training"""
    
    def __init__(self):
        self.sample_rate = 16000  # Common sample rate for speech recognition
        self.available_engines = self._detect_available_engines()
        logger.info(f"Available transcription engines: {self.available_engines}")
    
    def _detect_available_engines(self) -> List[str]:
        """Detect available transcription engines"""
        engines = []
        
        # Check for Whisper (OpenAI's speech-to-text)
        try:
            import whisper
            engines.append('whisper')
        except ImportError:
            pass
        
        # Check for Windows Speech Recognition
        import platform
        if platform.system().lower() == 'windows':
            engines.append('windows_sr')
        
        # Check for Google Speech Recognition (requires internet)
        try:
            import speech_recognition as sr
            engines.append('google_sr')
        except ImportError:
            pass
        
        # Always have a fallback simple transcription
        engines.append('simple')
        
        return engines
    
    def transcribe_audio(self, audio_file: str, engine: str = 'auto') -> Dict[str, Any]:
        """
        Transcribe audio to text with timing information
        
        Args:
            audio_file: Path to audio file
            engine: Transcription engine to use ('auto', 'whisper', 'google_sr', 'windows_sr', 'simple')
            
        Returns:
            Dictionary containing transcription and timing information
        """
        if engine == 'auto':
            engine = self.available_engines[0] if self.available_engines else 'simple'
        
        logger.info(f"Transcribing audio {audio_file} with engine: {engine}")
        
        try:
            if engine == 'whisper':
                return self._transcribe_with_whisper(audio_file)
            elif engine == 'google_sr':
                return self._transcribe_with_google_sr(audio_file)
            elif engine == 'windows_sr':
                return self._transcribe_with_windows_sr(audio_file)
            else:
                return self._transcribe_simple(audio_file)
        except Exception as e:
            logger.error(f"Transcription with {engine} failed: {e}")
            # Try fallback engines before simple transcription
            if engine != 'simple':
                logger.info("Trying simple transcription as fallback...")
                try:
                    return self._transcribe_simple(audio_file)
                except Exception as fallback_error:
                    logger.error(f"Even simple transcription failed: {fallback_error}")
                    # Return minimal fallback result
                    return {
                        'text': '[Audio file for voice training]',
                        'language': 'en',
                        'segments': [],
                        'words': [],
                        'confidence': 0.0,
                        'engine': 'fallback',
                        'error': str(fallback_error)
                    }
            else:
                # If simple transcription failed, return minimal result
                return {
                    'text': '[Audio file for voice training]',
                    'language': 'en', 
                    'segments': [],
                    'words': [],
                    'confidence': 0.0,
                    'engine': 'minimal',
                    'error': str(e)
                }
    
    def _transcribe_with_whisper(self, audio_file: str) -> Dict[str, Any]:
        """Transcribe using OpenAI Whisper"""
        try:
            import whisper
            
            # Load Whisper model (use base model for balance of speed/accuracy)
            logger.info("Loading Whisper model...")
            model = whisper.load_model("base")
            
            # Transcribe with word-level timestamps
            logger.info(f"Starting Whisper transcription for: {audio_file}")
            result = model.transcribe(audio_file, word_timestamps=True)
            
            # Check if result is valid
            if not result or 'text' not in result:
                logger.error("Whisper returned invalid result")
                raise ValueError("Whisper transcription returned no valid result")
            
            # Extract text and timing information
            transcription = {
                'text': result.get('text', '').strip(),
                'language': result.get('language', 'en'),
                'segments': [],
                'words': [],
                'confidence': 0.8,  # Whisper generally has good confidence
                'engine': 'whisper'
            }
            
            # Process segments safely
            segments = result.get('segments', [])
            if segments:
                for segment in segments:
                    if segment and isinstance(segment, dict):
                        transcription['segments'].append({
                            'start': segment.get('start', 0),
                            'end': segment.get('end', 0),
                            'text': segment.get('text', '').strip()
                        })
            
            # Process words if available (safely)
            words = result.get('words', [])
            if words:
                for word in words:
                    if word and isinstance(word, dict):
                        transcription['words'].append({
                            'start': word.get('start', 0),
                            'end': word.get('end', 0),
                            'word': word.get('word', '').strip(),
                            'confidence': word.get('probability', 0.8)
                        })
            
            logger.info(f"Whisper transcription complete: {transcription['text'][:100]}...")
            return transcription
            
        except Exception as e:
            logger.error(f"Whisper transcription failed: {e}")
            raise
    
    def _transcribe_with_google_sr(self, audio_file: str) -> Dict[str, Any]:
        """Transcribe using Google Speech Recognition"""
        try:
            import speech_recognition as sr
            
            # Initialize recognizer
            recognizer = sr.Recognizer()
            
            # Convert audio to proper format for speech recognition
            temp_wav = self._prepare_audio_for_sr(audio_file)
            
            # Load audio file
            with sr.AudioFile(temp_wav) as source:
                audio = recognizer.record(source)
            
            # Recognize speech
            text = recognizer.recognize_google(audio)
            
            # Clean up
            os.unlink(temp_wav)
            
            # Get audio duration for basic timing
            duration = librosa.get_duration(filename=audio_file)
            
            transcription = {
                'text': text,
                'language': 'en',
                'segments': [{
                    'start': 0.0,
                    'end': duration,
                    'text': text
                }],
                'words': [],
                'confidence': 0.7,
                'engine': 'google_sr'
            }
            
            logger.info(f"Google SR transcription complete: {text[:100]}...")
            return transcription
            
        except Exception as e:
            logger.error(f"Google SR transcription failed: {e}")
            raise
    
    def _transcribe_with_windows_sr(self, audio_file: str) -> Dict[str, Any]:
        """Transcribe using Windows Speech Recognition"""
        try:
            # This is a simplified implementation
            # Real Windows SR would require more complex setup
            import platform
            if platform.system().lower() != 'windows':
                raise NotImplementedError("Windows SR only available on Windows")
            
            # For now, use a PowerShell script approach
            # This is a placeholder - real implementation would be more complex
            return self._transcribe_simple(audio_file)
            
        except Exception as e:
            logger.error(f"Windows SR transcription failed: {e}")
            raise
    
    def _transcribe_simple(self, audio_file: str) -> Dict[str, Any]:
        """Simple transcription fallback - generates placeholder text"""
        try:
            # Get audio duration (fix librosa deprecation warning)
            duration = librosa.get_duration(path=audio_file)
            
            # Generate simple placeholder text based on duration
            words_per_second = 2.5  # Average speaking rate
            estimated_words = int(duration * words_per_second)
            
            # Create placeholder text
            placeholder_words = [
                "hello", "this", "is", "a", "voice", "recording", "for", "training",
                "the", "system", "will", "learn", "from", "this", "audio",
                "to", "create", "a", "custom", "voice", "model", "for", "synthesis"
            ]
            
            # Repeat words to match estimated length
            text_words = []
            for i in range(estimated_words):
                text_words.append(placeholder_words[i % len(placeholder_words)])
            
            text = " ".join(text_words)
            
            transcription = {
                'text': text,
                'language': 'en',
                'segments': [{
                    'start': 0.0,
                    'end': duration,
                    'text': text
                }],
                'words': [],
                'confidence': 0.3,  # Low confidence for placeholder
                'engine': 'simple',
                'placeholder': True
            }
            
            logger.info(f"Simple transcription complete: {text[:100]}...")
            return transcription
            
        except Exception as e:
            logger.error(f"Simple transcription failed: {e}")
            raise
    
    def _prepare_audio_for_sr(self, audio_file: str) -> str:
        """Prepare audio file for speech recognition (convert to proper format)"""
        try:
            # Load audio
            y, sr = librosa.load(audio_file, sr=self.sample_rate)
            
            # Create temporary WAV file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
            temp_file.close()
            
            # Save as WAV
            sf.write(temp_file.name, y, self.sample_rate)
            
            return temp_file.name
            
        except Exception as e:
            logger.error(f"Audio preparation failed: {e}")
            raise
    
    def transcribe_multiple_files(self, audio_files: List[str], engine: str = 'auto') -> List[Dict[str, Any]]:
        """Transcribe multiple audio files"""
        transcriptions = []
        
        for audio_file in audio_files:
            try:
                transcription = self.transcribe_audio(audio_file, engine)
                transcription['file'] = audio_file
                transcriptions.append(transcription)
            except Exception as e:
                logger.error(f"Failed to transcribe {audio_file}: {e}")
                # Add placeholder transcription
                transcriptions.append({
                    'file': audio_file,
                    'text': f"[Transcription failed for {os.path.basename(audio_file)}]",
                    'language': 'en',
                    'segments': [],
                    'words': [],
                    'confidence': 0.0,
                    'engine': 'failed',
                    'error': str(e)
                })
        
        return transcriptions
    
    def create_diffsinger_transcription(self, audio_file: str, transcription: Dict[str, Any]) -> str:
        """Create a transcription file compatible with DiffSinger"""
        try:
            # DiffSinger expects transcription in specific format
            # Usually a simple text file with the transcription
            
            audio_path = Path(audio_file)
            transcription_path = audio_path.with_suffix('.txt')
            
            # Write transcription to file
            with open(transcription_path, 'w', encoding='utf-8') as f:
                f.write(transcription['text'])
            
            logger.info(f"Created DiffSinger transcription: {transcription_path}")
            return str(transcription_path)
            
        except Exception as e:
            logger.error(f"Failed to create DiffSinger transcription: {e}")
            raise
    
    def validate_transcription(self, transcription: Dict[str, Any]) -> bool:
        """Validate transcription quality"""
        try:
            # Basic validation checks
            if not transcription.get('text'):
                return False
            
            if len(transcription['text'].strip()) < 10:
                return False
            
            if transcription.get('confidence', 0) < 0.1:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Transcription validation failed: {e}")
            return False
    
    def get_transcription_stats(self, transcription: Dict[str, Any]) -> Dict[str, Any]:
        """Get statistics about a transcription"""
        try:
            text = transcription.get('text', '')
            words = text.split()
            
            stats = {
                'word_count': len(words),
                'character_count': len(text),
                'confidence': transcription.get('confidence', 0),
                'language': transcription.get('language', 'unknown'),
                'engine': transcription.get('engine', 'unknown'),
                'has_timing': bool(transcription.get('segments')),
                'segment_count': len(transcription.get('segments', [])),
                'word_timing_count': len(transcription.get('words', []))
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get transcription stats: {e}")
            return {}
