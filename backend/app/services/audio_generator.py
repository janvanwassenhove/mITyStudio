"""
Audio Generation Module
Handles TTS, speech simulation, and musical synthesis
"""

import os
import tempfile
import subprocess
import platform
import logging
from typing import Optional
from pathlib import Path
import numpy as np
import soundfile as sf
from app.services.custom_voice_generator import CustomVoiceGenerator

logger = logging.getLogger(__name__)


class AudioGenerator:
    """Handles audio generation including TTS and musical synthesis"""
    
    def __init__(self):
        self.custom_voice_generator = CustomVoiceGenerator()
    
    def generate_test_audio(self, text: str, voice_id: str) -> str:
        """Generate test audio using TTS, with improved fallback for builtin voices"""
        logger.info(f"Generating test audio for voice '{voice_id}' with text: '{text}'")
        
        try:
            # Try to use system TTS if available
            audio_path = self._generate_tts_audio(text, voice_id)
            logger.info(f"TTS generation successful, audio saved to: {audio_path}")
            return audio_path
        except Exception as e:
            logger.warning(f"TTS generation failed ({e}), using improved speech simulation")
            return self._generate_speech_simulation(text, voice_id)
    
    def generate_musical_audio(self, text: str, voice_id: str, notes: list = None, 
                              chord_name: str = None, duration: float = None) -> str:
        """Generate musical audio with notes - enhanced implementation with pitch modulation"""
        logger.info(f"Generating musical audio for '{text}' with notes: {notes}")
        
        if notes:
            logger.info(f"Musical notes provided: {notes}")
        if chord_name:
            logger.info(f"Chord context: {chord_name}")
            
        # If we have musical notes, generate pitch-modulated audio
        if notes and len(notes) > 0:
            return self._generate_pitch_modulated_audio(text, voice_id, notes, chord_name, duration)
        else:
            # Fallback to regular audio generation
            return self.generate_test_audio(text, voice_id)
    
    def generate_custom_voice_audio(self, text: str, voice_id: str, voice_characteristics: dict) -> str:
        """Generate audio for custom voices with unique characteristics"""
        return self.custom_voice_generator.generate_custom_voice_audio(text, voice_id, voice_characteristics)
    
    def _generate_speech_simulation(self, text: str, voice_id: str) -> str:
        """Generate speech-like audio simulation (not just tones)"""
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
        temp_file.close()
        
        # Create speech-like patterns instead of simple tones
        duration = max(1.0, len(text) * 0.1)  # Duration based on text length
        sample_rate = 22050
        
        # Base frequency for different voice types
        if voice_id == 'female-01' or 'female' in voice_id.lower():
            base_freq = 220  # Higher pitch for female voice
            formant_shift = 1.15  # Higher formants
            vibrato_rate = 6.0  # Slightly faster vibrato
        elif voice_id == 'male-01' or 'male' in voice_id.lower():
            base_freq = 120  # Lower pitch for male voice
            formant_shift = 0.85  # Lower formants
            vibrato_rate = 4.5  # Slower vibrato
        else:  # default voice
            base_freq = 180  # Medium pitch
            formant_shift = 1.0  # Normal formants
            vibrato_rate = 5.0  # Medium vibrato
        
        t = np.linspace(0, duration, int(sample_rate * duration))
        
        # Create speech-like formant patterns
        words = text.split()
        audio = np.zeros_like(t)
        
        for i, word in enumerate(words):
            # Calculate time segment for this word
            start_time = i * duration / len(words)
            end_time = (i + 1) * duration / len(words)
            start_idx = int(start_time * sample_rate)
            end_idx = int(end_time * sample_rate)
            
            if start_idx >= len(t) or end_idx > len(t):
                continue
                
            word_t = t[start_idx:end_idx]
            
            # Create vowel-like sounds with voice-specific formants
            formant1 = base_freq * 2.5 * formant_shift  # First formant
            formant2 = base_freq * 4.5 * formant_shift  # Second formant
            
            # Add vibrato for naturalness
            vibrato = 1.0 + 0.02 * np.sin(2 * np.pi * vibrato_rate * word_t)
            
            # Modulate frequency based on word characteristics and voice
            freq_mod = vibrato * (1.0 + 0.15 * np.sin(word_t * 8))
            
            # Generate formant-like audio with voice characteristics
            signal = (
                0.4 * np.sin(2 * np.pi * base_freq * freq_mod * word_t) +
                0.3 * np.sin(2 * np.pi * formant1 * freq_mod * word_t) +
                0.2 * np.sin(2 * np.pi * formant2 * freq_mod * word_t)
            )
            
            # Add consonant-like noise bursts (varies by voice)
            noise_intensity = 0.1 if 'female' in voice_id.lower() else 0.15
            noise = np.random.normal(0, noise_intensity, len(word_t))
            consonant_mask = np.sin(word_t * 20) > 0.7
            signal[consonant_mask] = noise[consonant_mask] * 0.5
            
            # Apply envelope to simulate syllables
            envelope = 0.5 * (1 + np.sin(word_t * 6 - np.pi/2))
            signal *= envelope
            
            # Add pause between words
            if i < len(words) - 1:
                pause_start = end_idx - int(0.05 * sample_rate)
                pause_end = min(end_idx + int(0.05 * sample_rate), len(audio))
                if pause_start < len(audio):
                    audio[pause_start:pause_end] *= 0.1
            
            audio[start_idx:end_idx] = signal
        
        # Normalize and apply final envelope
        audio = audio / np.max(np.abs(audio)) * 0.7
        
        sf.write(temp_file.name, audio, sample_rate)
        logger.info(f"Speech simulation generated: {temp_file.name}")
        return temp_file.name
    
    def _generate_tts_audio(self, text: str, voice_id: str) -> str:
        """Generate TTS audio using available TTS engine"""
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
        temp_file.close()
        
        system = platform.system().lower()
        logger.info(f"Attempting TTS on {system} platform for voice: {voice_id}")
        
        try:
            if system == 'windows':
                # Use Windows SAPI
                self._windows_tts(text, temp_file.name, voice_id)
            elif system == 'darwin':  # macOS
                # Use macOS say command
                self._macos_tts(text, temp_file.name, voice_id)
            else:
                # Try espeak for Linux
                self._linux_tts(text, temp_file.name, voice_id)
            
            # Verify the file was created and has content
            if os.path.exists(temp_file.name) and os.path.getsize(temp_file.name) > 1000:  # At least 1KB
                logger.info(f"TTS audio generated successfully: {temp_file.name} ({os.path.getsize(temp_file.name)} bytes)")
                return temp_file.name
            else:
                raise Exception(f"TTS output file not generated or too small: {temp_file.name}")
                
        except Exception as e:
            logger.error(f"TTS generation failed on {system}: {e}")
            # Clean up failed file
            try:
                os.unlink(temp_file.name)
            except:
                pass
            raise
    
    def _windows_tts(self, text: str, output_path: str, voice_id: str):
        """Windows SAPI TTS"""
        # Create a temporary PowerShell script file
        ps_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.ps1', encoding='utf-8')
        
        # Escape quotes in text and path
        safe_text = text.replace('"', '""').replace("'", "''")
        safe_path = output_path.replace('\\', '\\\\')
        
        ps_script = f'''
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer

try {{
    # Set output to WAV file
    $synth.SetOutputToWaveFile("{safe_path}")
    
    # Select appropriate voice based on voice_id
    $voices = $synth.GetInstalledVoices()
    $selectedVoice = $null
    $voiceId = "{voice_id}".ToLower()
    
    # Debug: List all available voices
    Write-Host "Available voices:"
    foreach ($voice in $voices) {{
        Write-Host "  - $($voice.VoiceInfo.Name) (Gender: $($voice.VoiceInfo.Gender))"
    }}
    
    # Voice selection logic
    foreach ($voice in $voices) {{
        $name = $voice.VoiceInfo.Name.ToLower()
        $gender = $voice.VoiceInfo.Gender.ToString().ToLower()
        
        # Match by voice ID patterns
        if ($voiceId -eq "female-01" -and $gender -eq "female") {{
            $synth.SelectVoice($voice.VoiceInfo.Name)
            $selectedVoice = $voice.VoiceInfo.Name
            Write-Host "Selected female voice: $selectedVoice"
            break
        }}
        elseif ($voiceId -eq "male-01" -and $gender -eq "male") {{
            $synth.SelectVoice($voice.VoiceInfo.Name)
            $selectedVoice = $voice.VoiceInfo.Name
            Write-Host "Selected male voice: $selectedVoice"
            break
        }}
        elseif ($voiceId -eq "default") {{
            # Use the first available voice for default
            $synth.SelectVoice($voice.VoiceInfo.Name)
            $selectedVoice = $voice.VoiceInfo.Name
            Write-Host "Selected default voice: $selectedVoice"
            break
        }}
    }}
    
    # Fallback: if no specific voice found, try to match by gender keywords
    if ($selectedVoice -eq $null) {{
        foreach ($voice in $voices) {{
            $name = $voice.VoiceInfo.Name.ToLower()
            $gender = $voice.VoiceInfo.Gender.ToString().ToLower()
            
            if ($voiceId.Contains("female") -and $gender -eq "female") {{
                $synth.SelectVoice($voice.VoiceInfo.Name)
                $selectedVoice = $voice.VoiceInfo.Name
                Write-Host "Fallback female voice: $selectedVoice"
                break
            }}
            elseif ($voiceId.Contains("male") -and $gender -eq "male") {{
                $synth.SelectVoice($voice.VoiceInfo.Name)
                $selectedVoice = $voice.VoiceInfo.Name
                Write-Host "Fallback male voice: $selectedVoice"
                break
            }}
        }}
    }}
    
    # Final fallback: use system default
    if ($selectedVoice -eq $null) {{
        $selectedVoice = "System Default"
        Write-Host "Using system default voice"
    }}
    
    # Speak the text
    $synth.Speak("{safe_text}")
    Write-Host "TTS completed successfully with voice: $selectedVoice"
}}
catch {{
    Write-Error "TTS failed: $($_.Exception.Message)"
    exit 1
}}
finally {{
    $synth.Dispose()
}}
'''
        
        ps_file.write(ps_script)
        ps_file.close()
        
        try:
            # Execute the PowerShell script
            result = subprocess.run([
                'powershell', '-ExecutionPolicy', 'Bypass', '-File', ps_file.name
            ], capture_output=True, text=True, check=True)
            
            logger.info(f"Windows TTS output: {result.stdout}")
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Windows TTS failed: {e.stderr}")
            raise
        finally:
            # Clean up the temporary script file
            try:
                os.unlink(ps_file.name)
            except:
                pass
    
    def _macos_tts(self, text: str, output_path: str, voice_id: str):
        """macOS say command TTS"""
        # Voice selection based on voice_id
        if voice_id == 'female-01' or 'female' in voice_id.lower():
            voice = "Samantha"  # Female voice
        elif voice_id == 'male-01' or 'male' in voice_id.lower():
            voice = "Alex"  # Male voice
        else:  # default voice
            voice = "Daniel"  # Default voice
        
        logger.info(f"macOS TTS: Using voice '{voice}' for voice_id '{voice_id}'")
        
        try:
            # Use say command to generate AIFF first, then convert to WAV
            temp_aiff = tempfile.NamedTemporaryFile(delete=False, suffix='.aiff')
            temp_aiff.close()
            
            # Generate AIFF file
            subprocess.run([
                'say', '-v', voice, '-o', temp_aiff.name, text
            ], check=True)
            
            # Convert AIFF to WAV using ffmpeg or afconvert
            try:
                subprocess.run([
                    'afconvert', temp_aiff.name, output_path, '-f', 'WAVE'
                ], check=True)
            except (subprocess.CalledProcessError, FileNotFoundError):
                # Fallback: try with ffmpeg
                subprocess.run([
                    'ffmpeg', '-i', temp_aiff.name, '-y', output_path
                ], check=True)
                
        except Exception as e:
            logger.error(f"macOS TTS failed: {e}")
            raise
        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_aiff.name)
            except:
                pass
    
    def _linux_tts(self, text: str, output_path: str, voice_id: str):
        """Linux espeak TTS"""
        # Voice parameters based on voice_id
        if voice_id == 'female-01' or 'female' in voice_id.lower():
            voice_params = ['-s', '180', '-p', '60', '-a', '100']  # Faster, higher pitch, normal amplitude
        elif voice_id == 'male-01' or 'male' in voice_id.lower():
            voice_params = ['-s', '160', '-p', '40', '-a', '100']  # Slower, lower pitch, normal amplitude
        else:  # default voice
            voice_params = ['-s', '170', '-p', '50', '-a', '100']  # Medium settings
        
        logger.info(f"Linux TTS: Using voice parameters {voice_params} for voice_id '{voice_id}'")
        
        try:
            # Try espeak-ng first (newer version)
            subprocess.run([
                'espeak-ng', '-w', output_path
            ] + voice_params + [text], check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Fallback to regular espeak
            subprocess.run([
                'espeak', '-w', output_path
            ] + voice_params + [text], check=True)
    
    def _generate_pitch_modulated_audio(self, text: str, voice_id: str, notes: list, 
                                       chord_name: str = None, duration: float = None) -> str:
        """Generate audio with pitch modulation based on musical notes - use RVC for custom voices"""
        logger.info(f"Generating singing for '{text}' with voice {voice_id} and {len(notes)} notes")
        
        # Check if this is a custom voice with RVC model
        if self._is_custom_voice_with_rvc(voice_id):
            logger.info(f"Using RVC service for custom voice {voice_id}")
            return self._generate_rvc_singing(text, voice_id, notes, chord_name, duration)
        else:
            logger.info(f"Using synthetic generation for voice {voice_id}")
            return self._generate_synthetic_singing(text, voice_id, notes, chord_name, duration)
    
    def _is_custom_voice_with_rvc(self, voice_id: str) -> bool:
        """Check if voice_id corresponds to a custom voice with RVC model"""
        try:
            from app.services.rvc_service import RVCService
            rvc_service = RVCService()
            
            # Check if RVC model exists for this voice
            voices = rvc_service.list_singing_voices()
            for voice in voices:
                if voice.get('voice_id') == voice_id or voice.get('name') == voice_id:
                    return True
            
            return False
        except Exception as e:
            logger.warning(f"Could not check RVC availability: {e}")
            return False
    
    def _generate_rvc_singing(self, text: str, voice_id: str, notes: list, 
                             chord_name: str = None, duration: float = None) -> str:
        """Generate singing using RVC service with actual voice samples"""
        try:
            from app.services.rvc_service import RVCService
            
            rvc_service = RVCService()
            
            # Calculate duration based on natural singing pace
            if duration is None:
                syllable_count = len(self._extract_syllables(text))
                duration = max(3.0, syllable_count * 0.6)
            
            logger.info(f"Using RVC service to generate {duration:.1f}s of singing for '{text}'")
            
            # Use RVC service to generate singing
            audio_path = rvc_service.generate_singing_audio(
                text=text,
                voice_id=voice_id,
                notes=notes,
                duration=duration
            )
            
            if audio_path and Path(audio_path).exists():
                logger.info(f"✅ RVC singing generated successfully: {audio_path}")
                return audio_path
            else:
                logger.warning("RVC singing generation failed, falling back to synthetic")
                return self._generate_synthetic_singing(text, voice_id, notes, chord_name, duration)
                
        except Exception as e:
            logger.error(f"RVC singing generation failed: {e}")
            logger.info("Falling back to synthetic singing generation")
            return self._generate_synthetic_singing(text, voice_id, notes, chord_name, duration)
    
    def _generate_synthetic_singing(self, text: str, voice_id: str, notes: list, 
                                   chord_name: str = None, duration: float = None) -> str:
        """Generate synthetic singing audio (original implementation)"""
        logger.info(f"Generating synthetic singing for '{text}' with {len(notes)} notes")
        
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
        temp_file.close()
        
        # Parse notes and convert to frequencies
        note_frequencies = []
        for note in notes:
            freq = self._note_to_frequency(note)
            if freq:
                note_frequencies.append(freq)
        
        if not note_frequencies:
            logger.warning("No valid note frequencies found, falling back to regular generation")
            return self.generate_test_audio(text, voice_id)
        
        # Calculate duration based on natural singing pace
        if duration is None:
            syllable_count = len(self._extract_syllables(text))
            duration = max(3.0, syllable_count * 0.6)  # More time per syllable for singing
        
        sample_rate = 22050
        t = np.linspace(0, duration, int(sample_rate * duration))
        
        # Voice characteristics for natural singing
        if 'male' in voice_id.lower():
            base_freq_adjust = 0.85  # Lower range for male singing
            formant_1_freq = 550   # Male singing formants
            formant_2_freq = 1000
            vibrato_rate = 4.2
            vibrato_depth = 0.018  # Natural vibrato depth
            voice_brightness = 0.7
        elif 'female' in voice_id.lower():
            base_freq_adjust = 1.15  # Higher range for female singing
            formant_1_freq = 650   # Female singing formants
            formant_2_freq = 1200
            vibrato_rate = 5.8
            vibrato_depth = 0.025  # Slightly more vibrato
            voice_brightness = 0.85
        else:
            base_freq_adjust = 1.0  # Neutral voice
            formant_1_freq = 600   # Neutral singing formants
            formant_2_freq = 1100
            vibrato_rate = 5.0
            vibrato_depth = 0.022
            voice_brightness = 0.75
        
        # Generate basic singing with note frequencies
        audio = np.zeros_like(t)
        
        for i, freq in enumerate(note_frequencies):
            # Calculate timing for each note
            note_start = (i / len(note_frequencies)) * duration
            note_end = ((i + 1) / len(note_frequencies)) * duration
            note_mask = (t >= note_start) & (t < note_end)
            
            if np.any(note_mask):
                adjusted_freq = freq * base_freq_adjust
                
                # Generate harmonic singing voice
                fundamental = np.sin(2 * np.pi * adjusted_freq * t[note_mask])
                overtone1 = 0.5 * np.sin(2 * np.pi * adjusted_freq * 2 * t[note_mask])
                overtone2 = 0.25 * np.sin(2 * np.pi * adjusted_freq * 3 * t[note_mask])
                
                # Add vibrato
                vibrato = 1 + vibrato_depth * np.sin(2 * np.pi * vibrato_rate * t[note_mask])
                note_audio = (fundamental + overtone1 + overtone2) * vibrato
                
                # Apply envelope
                envelope_length = len(note_audio)
                envelope = np.ones(envelope_length)
                attack_length = min(envelope_length // 10, envelope_length)
                if attack_length > 0:
                    envelope[:attack_length] = np.linspace(0, 1, attack_length)
                
                note_audio *= envelope
                audio[note_mask] += note_audio
        
        # Normalize and save
        if np.max(np.abs(audio)) > 0:
            audio = audio / np.max(np.abs(audio)) * 0.8
        
        sf.write(temp_file.name, audio, sample_rate)
        logger.info(f"Synthetic singing audio generated: {temp_file.name}")
        return temp_file.name
    
    def _create_musical_phrase(self, note_frequencies: list, syllable_count: int) -> list:
        """Create a musical phrase by extending notes with musical intelligence"""
        if len(note_frequencies) >= syllable_count:
            return note_frequencies[:syllable_count]
        
        extended_notes = note_frequencies.copy()
        
        # Extend with musical patterns
        while len(extended_notes) < syllable_count:
            pattern_length = len(note_frequencies)
            remaining_syllables = syllable_count - len(extended_notes)
            
            if remaining_syllables >= pattern_length:
                # Repeat the entire pattern
                extended_notes.extend(note_frequencies)
            else:
                # Add partial pattern with musical resolution
                partial_pattern = note_frequencies[:remaining_syllables]
                # End on a musically satisfying note (try to end on tonic or fifth)
                if remaining_syllables > 0:
                    partial_pattern[-1] = note_frequencies[0]  # End on tonic
                extended_notes.extend(partial_pattern)
        
        return extended_notes
    
    def _create_singing_pitch_curve(self, t: np.ndarray, target_freq: float, 
                                   all_notes: list, syllable_index: int, total_syllables: int) -> np.ndarray:
        """Create smooth pitch transitions for natural singing"""
        pitch_curve = np.full_like(t, target_freq)
        
        # Add portamento (pitch glide) at the beginning if not the first syllable
        if syllable_index > 0:
            prev_freq = all_notes[syllable_index - 1]
            glide_length = min(len(t) // 3, len(t))
            
            if glide_length > 0:
                # Create natural pitch glide
                glide_t = np.linspace(0, 1, glide_length)
                # Use S-curve for natural pitch transition
                s_curve = 3 * glide_t**2 - 2 * glide_t**3
                pitch_glide = prev_freq + (target_freq - prev_freq) * s_curve
                pitch_curve[:glide_length] = pitch_glide
        
        # Add natural pitch variation within the syllable
        pitch_variation = 1.0 + 0.01 * np.sin(10 * np.pi * np.linspace(0, 1, len(t)))
        pitch_curve *= pitch_variation
        
        return pitch_curve
    
    def _generate_realistic_singing_voice(self, t: np.ndarray, pitch_curve: np.ndarray,
                                         f1: float, f2: float, vibrato_rate: float, 
                                         vibrato_depth: float, voice_id: str, brightness: float) -> np.ndarray:
        """Generate highly realistic singing voice using advanced vocal modeling"""
        
        # Apply natural vibrato with random variations
        vibrato_phase = 2 * np.pi * vibrato_rate * t
        vibrato_randomness = np.random.normal(1.0, 0.05, len(t))
        vibrato = 1.0 + vibrato_depth * np.sin(vibrato_phase) * vibrato_randomness
        
        final_pitch = pitch_curve * vibrato
        
        # Generate vocal source using improved glottal pulse model
        vocal_source = self._generate_advanced_glottal_source(t, final_pitch, voice_id)
        
        # Apply formant filtering with dynamic characteristics
        voice_signal = self._apply_dynamic_formant_filter(vocal_source, f1, f2, voice_id, brightness)
        
        # Add singing-specific vocal textures
        voice_signal = self._add_singing_vocal_texture(voice_signal, t, voice_id)
        
        return voice_signal
    
    def _generate_advanced_glottal_source(self, t: np.ndarray, pitch: np.ndarray, voice_id: str) -> np.ndarray:
        """Generate advanced glottal source with realistic voice characteristics"""
        
        # Voice-specific glottal parameters
        if 'male' in voice_id.lower():
            pulse_asymmetry = 0.6  # More asymmetric pulses
            spectral_tilt = -12    # dB per octave
            jitter = 0.5          # Frequency variation
        elif 'female' in voice_id.lower():
            pulse_asymmetry = 0.7  # Slightly less asymmetric
            spectral_tilt = -10    # Less spectral tilt
            jitter = 0.3          # Less frequency variation
        else:
            pulse_asymmetry = 0.65
            spectral_tilt = -11
            jitter = 0.4
        
        # Add natural jitter (frequency variation)
        jitter_variation = 1.0 + (jitter / 100.0) * np.random.normal(0, 1, len(t))
        pitch_with_jitter = pitch * jitter_variation
        
        # Generate asymmetric pulse train
        voice_signal = np.zeros_like(t)
        
        # Use phase accumulation for accurate pitch tracking
        dt = t[1] - t[0] if len(t) > 1 else 1/22050
        phase = np.cumsum(pitch_with_jitter * dt) * 2 * np.pi
        
        # Generate harmonics with realistic spectral shaping
        for harmonic in range(1, 20):  # Up to 19th harmonic
            # Apply spectral tilt
            amplitude = (1.0 / harmonic) * (10 ** (spectral_tilt * harmonic / 20.0))
            
            # Add harmonic distortion for natural voice
            distortion = 1.0 + 0.1 * np.sin(phase * harmonic * 0.5)
            
            # Generate harmonic with asymmetric pulse shaping
            harmonic_signal = amplitude * np.sin(phase * harmonic) * distortion
            
            # Apply pulse asymmetry
            asymmetry_factor = 1.0 + pulse_asymmetry * np.sin(phase * harmonic)
            harmonic_signal *= asymmetry_factor
            
            voice_signal += harmonic_signal
        
        return voice_signal
    
    def _apply_dynamic_formant_filter(self, signal: np.ndarray, f1: float, f2: float, 
                                     voice_id: str, brightness: float) -> np.ndarray:
        """Apply dynamic formant filtering that changes over time"""
        
        # Singing formants (different from speech)
        if 'male' in voice_id.lower():
            f3 = 2600  # Third formant for male singing
            singer_formant = 2800  # Male singer's formant
        elif 'female' in voice_id.lower():
            f3 = 3100  # Third formant for female singing
            singer_formant = 3200  # Female singer's formant
        else:
            f3 = 2850
            singer_formant = 3000
        
        # Create time-varying formant responses
        t_norm = np.linspace(0, 1, len(signal))
        
        # Dynamic formant movements for natural singing
        f1_dynamic = f1 * (1.0 + 0.1 * np.sin(4 * np.pi * t_norm))
        f2_dynamic = f2 * (1.0 + 0.08 * np.sin(6 * np.pi * t_norm))
        
        # Apply formant resonances using a simplified model
        filtered_signal = signal.copy()
        
        # Simple formant emphasis (approximation of vocal tract resonance)
        formant_weights = np.ones_like(signal)
        
        # Emphasize formant regions
        sample_rate = 22050
        freqs = np.fft.fftfreq(len(signal), 1/sample_rate)
        
        for i, freq in enumerate(freqs[:len(freqs)//2]):
            # Distance from formants
            dist_f1 = abs(freq - f1_dynamic[min(i * len(f1_dynamic) // len(freqs), len(f1_dynamic)-1)])
            dist_f2 = abs(freq - f2_dynamic[min(i * len(f2_dynamic) // len(freqs), len(f2_dynamic)-1)])
            dist_f3 = abs(freq - f3)
            dist_singer = abs(freq - singer_formant)
            
            # Formant resonance (simplified)
            formant_gain = (
                1.0 + 0.5 * np.exp(-(dist_f1/200)**2) +      # F1 resonance
                0.4 * np.exp(-(dist_f2/300)**2) +            # F2 resonance
                0.3 * np.exp(-(dist_f3/400)**2) +            # F3 resonance
                0.4 * brightness * np.exp(-(dist_singer/300)**2)  # Singer's formant
            )
            
            if i < len(formant_weights):
                formant_weights[i] = formant_gain
        
        # Apply simple spectral shaping (approximation)
        filtered_signal *= np.interp(np.arange(len(signal)), 
                                   np.linspace(0, len(signal)-1, len(formant_weights)), 
                                   formant_weights)
        
        return filtered_signal
    
    def _add_singing_vocal_texture(self, signal: np.ndarray, t: np.ndarray, voice_id: str) -> np.ndarray:
        """Add singing-specific vocal textures and characteristics"""
        
        # Voice-specific singing characteristics
        if 'male' in voice_id.lower():
            breathiness = 0.008
            chest_resonance = 0.12
            vibrato_intensity = 0.85
        elif 'female' in voice_id.lower():
            breathiness = 0.012
            chest_resonance = 0.08
            vibrato_intensity = 1.0
        else:
            breathiness = 0.01
            chest_resonance = 0.10
            vibrato_intensity = 0.92
        
        # Add natural breath flow
        breath_pattern = breathiness * np.random.normal(0, 1, len(signal))
        breath_filter = 1.0 + 0.3 * np.sin(8 * np.pi * t)  # Breathing rhythm
        natural_breath = breath_pattern * breath_filter
        
        # Add chest resonance for singing
        chest_freq = 60 + 20 * np.sin(2 * np.pi * 0.5 * t)  # Variable chest resonance
        chest_signal = chest_resonance * np.sin(2 * np.pi * chest_freq * t)
        
        # Add singing vibrato on amplitude
        amp_vibrato = 1.0 + 0.02 * vibrato_intensity * np.sin(2 * np.pi * 5.5 * t)
        
        # Combine all textures
        textured_signal = (signal + natural_breath + chest_signal) * amp_vibrato
        
        return textured_signal
    
    def _generate_singing_syllable_envelope(self, length: int, syllable: str, 
                                          syllable_index: int, total_syllables: int) -> np.ndarray:
        """Generate envelope specifically for singing with musical phrasing"""
        t = np.linspace(0, 1, length)
        
        # Analyze syllable characteristics for singing
        vowels = 'aeiou'
        is_vowel_heavy = sum(1 for c in syllable.lower() if c in vowels) > len(syllable) / 2
        
        # Musical phrasing considerations
        is_phrase_beginning = syllable_index == 0
        is_phrase_ending = syllable_index == total_syllables - 1
        is_sustained_note = is_vowel_heavy and len(syllable) > 2
        
        # Envelope parameters based on musical context
        if is_phrase_beginning:
            attack_time = 0.25  # Slower attack for phrase beginning
            sustain_level = 0.85
        elif is_phrase_ending:
            attack_time = 0.1
            sustain_level = 0.9
            release_time = 0.4  # Longer release for phrase ending
        elif is_sustained_note:
            attack_time = 0.15
            sustain_level = 0.95  # Higher sustain for vowels
            release_time = 0.2
        else:
            attack_time = 0.12
            sustain_level = 0.8
            release_time = 0.25
        
        # Set default release time if not set above
        if 'release_time' not in locals():
            release_time = 0.25
        
        envelope = np.ones_like(t)
        
        # Natural singing attack with breath support
        attack_mask = t < attack_time
        if np.any(attack_mask):
            # Exponential attack with breath onset
            attack_curve = 1 - np.exp(-4 * t[attack_mask] / attack_time)
            envelope[attack_mask] = attack_curve
        
        # Sustained singing with natural variations
        sustain_start = attack_time
        sustain_end = 1.0 - release_time
        sustain_mask = (t >= sustain_start) & (t < sustain_end)
        
        if np.any(sustain_mask):
            sustain_t = (t[sustain_mask] - sustain_start) / (sustain_end - sustain_start)
            
            # Add singing breath support pattern
            breath_support = 1.0 + 0.03 * np.sin(6 * np.pi * sustain_t)
            
            # Add natural singing vibrato on amplitude
            singing_vibrato = 1.0 + 0.015 * np.sin(12 * np.pi * sustain_t)
            
            envelope[sustain_mask] = sustain_level * breath_support * singing_vibrato
        
        # Natural singing release
        release_mask = t >= sustain_end
        if np.any(release_mask):
            release_t = (t[release_mask] - sustain_end) / release_time
            
            if is_phrase_ending:
                # Gradual fade for phrase ending
                release_curve = sustain_level * np.exp(-2 * release_t)
            else:
                # Quick release for continuing phrase
                release_curve = sustain_level * np.exp(-4 * release_t)
            
            envelope[release_mask] = release_curve
        
        return np.clip(envelope, 0, 1)
    
    def _add_singing_ambience(self, audio: np.ndarray, sample_rate: int, voice_id: str) -> np.ndarray:
        """Add natural singing ambience and room characteristics"""
        
        # Add subtle room resonance for singing
        room_tone = np.random.normal(0, 0.002, len(audio))
        
        # Apply singing-appropriate reverb
        reverb_audio = self._add_singing_reverb(audio, sample_rate)
        
        # Add natural vocal tract resonance
        if 'male' in voice_id.lower():
            tract_resonance = 0.05 * np.sin(2 * np.pi * 120 * np.arange(len(audio)) / sample_rate)
        elif 'female' in voice_id.lower():
            tract_resonance = 0.04 * np.sin(2 * np.pi * 180 * np.arange(len(audio)) / sample_rate)
        else:
            tract_resonance = 0.045 * np.sin(2 * np.pi * 150 * np.arange(len(audio)) / sample_rate)
        
        # Combine elements
        natural_audio = reverb_audio + room_tone + tract_resonance
        
        # Apply gentle compression for singing (simple limiting)
        max_amplitude = np.max(np.abs(natural_audio))
        if max_amplitude > 0.9:
            compression_ratio = 0.9 / max_amplitude
            natural_audio *= compression_ratio
        
        return natural_audio
    
    def _add_singing_reverb(self, audio: np.ndarray, sample_rate: int) -> np.ndarray:
        """Add reverb appropriate for singing performance"""
        # Multiple delay lines for richer reverb
        delays = [0.03, 0.06, 0.09, 0.12]  # Different delay times in seconds
        gains = [0.25, 0.18, 0.12, 0.08]   # Decreasing gains
        
        reverb_audio = audio.copy()
        
        for delay_time, gain in zip(delays, gains):
            delay_samples = int(delay_time * sample_rate)
            if delay_samples < len(audio):
                reverb_audio[delay_samples:] += audio[:-delay_samples] * gain
        
        return reverb_audio
    
    def _note_to_frequency(self, note: str) -> Optional[float]:
        """Convert musical note to frequency (e.g., 'C4' -> 261.63)"""
        if not note or len(note) < 2:
            return None
            
        try:
            # Note mapping (C4 = middle C = 261.63 Hz)
            note_map = {
                'C': -9, 'C#': -8, 'DB': -8,
                'D': -7, 'D#': -6, 'EB': -6,
                'E': -5, 
                'F': -4, 'F#': -3, 'GB': -3,
                'G': -2, 'G#': -1, 'AB': -1,
                'A': 0, 'A#': 1, 'BB': 1,
                'B': 2
            }
            
            # Parse note (e.g., 'C4', 'F#3')
            if '#' in note:
                note_name = note[:2]
                octave = int(note[2:])
            elif 'B' in note and len(note) > 2:
                note_name = note[:2]
                octave = int(note[2:])
            else:
                note_name = note[0]
                octave = int(note[1:])
            
            if note_name.upper() not in note_map:
                return None
            
            # Calculate frequency using A4 = 440 Hz as reference
            semitones_from_a4 = note_map[note_name.upper()] + (octave - 4) * 12
            frequency = 440.0 * (2 ** (semitones_from_a4 / 12.0))
            
            return frequency
            
        except (ValueError, IndexError, KeyError) as e:
            logger.warning(f"Could not parse note '{note}': {e}")
            return None
    
    def _generate_vocal_formants(self, t: np.ndarray, fundamental_freq: float, 
                                voice_id: str, formant_shift: float, vibrato_rate: float) -> np.ndarray:
        """Generate vocal-like audio with formants at the specified fundamental frequency"""
        
        # Add subtle vibrato
        vibrato = 1.0 + 0.02 * np.sin(2 * np.pi * vibrato_rate * t)
        freq = fundamental_freq * vibrato
        
        # Generate fundamental and formants
        # Formant frequencies typical for human voice
        formant1 = freq * 2.5 * formant_shift   # First formant
        formant2 = freq * 4.5 * formant_shift   # Second formant
        formant3 = freq * 7.0 * formant_shift   # Third formant
        
        # Generate harmonic series with formant emphasis
        signal = (
            0.5 * np.sin(2 * np.pi * freq * t) +                    # Fundamental
            0.3 * np.sin(2 * np.pi * formant1 * t) +               # First formant
            0.2 * np.sin(2 * np.pi * formant2 * t) +               # Second formant
            0.1 * np.sin(2 * np.pi * formant3 * t) +               # Third formant
            0.05 * np.sin(2 * np.pi * freq * 2 * t) +              # Second harmonic
            0.03 * np.sin(2 * np.pi * freq * 3 * t)                # Third harmonic
        )
        
        # Add breath noise for realism
        breath_noise = np.random.normal(0, 0.02, len(t))
        signal += breath_noise
        
        return signal
    
    def _extract_syllables(self, text: str) -> list:
        """Extract syllables from text using simple vowel-based method"""
        words = text.split()
        syllables = []
        
        for word in words:
            word_lower = word.lower()
            vowels = 'aeiou'
            syllable_positions = []
            
            # Find vowel groups
            in_vowel_group = False
            for i, char in enumerate(word_lower):
                if char in vowels:
                    if not in_vowel_group:
                        syllable_positions.append(i)
                        in_vowel_group = True
                else:
                    in_vowel_group = False
            
            # If no vowels found, treat as single syllable
            if not syllable_positions:
                syllables.append(word)
            else:
                # Create syllables based on vowel positions
                prev_pos = 0
                for i, pos in enumerate(syllable_positions):
                    if i == len(syllable_positions) - 1:
                        syllables.append(word[prev_pos:])
                    else:
                        next_consonant = pos + 1
                        while next_consonant < len(word) and word_lower[next_consonant] in vowels:
                            next_consonant += 1
                        if next_consonant < len(word):
                            split_pos = (next_consonant + syllable_positions[i + 1]) // 2
                        else:
                            split_pos = len(word)
                        syllables.append(word[prev_pos:split_pos])
                        prev_pos = split_pos
        
        return syllables if syllables else [text]
    
    def _generate_natural_singing_voice(self, t: np.ndarray, base_pitch: np.ndarray, 
                                       formant1: float, formant2: float, 
                                       vibrato_rate: float, vibrato_depth: float, voice_id: str) -> np.ndarray:
        """Generate more natural singing voice using vocal tract modeling"""
        
        # Add natural vibrato with some randomness for humanness
        vibrato_phase = 2 * np.pi * vibrato_rate * t
        vibrato_variation = np.random.normal(1.0, 0.02, len(t))  # Slight random variation
        vibrato = 1.0 + vibrato_depth * np.sin(vibrato_phase) * vibrato_variation
        pitch_with_vibrato = base_pitch * vibrato
        
        # Generate a more complex fundamental using pulse train simulation
        voice_signal = self._generate_vocal_pulse_train(t, pitch_with_vibrato, voice_id)
        
        # Apply realistic vocal tract filtering
        voice_signal = self._apply_vocal_tract_filter(voice_signal, formant1, formant2, voice_id)
        
        # Add natural breath and vocal texture
        voice_signal = self._add_vocal_texture(voice_signal, t, voice_id)
        
        return voice_signal
    
    def _generate_vocal_pulse_train(self, t: np.ndarray, pitch: np.ndarray, voice_id: str) -> np.ndarray:
        """Generate a more realistic glottal pulse train for singing"""
        sample_rate = len(t) / (t[-1] - t[0]) if len(t) > 1 else 22050
        
        # Voice-specific pulse characteristics
        if 'male' in voice_id.lower():
            pulse_sharpness = 0.3  # Sharper pulses for male voice
            harmonic_rolloff = 0.8
        elif 'female' in voice_id.lower():
            pulse_sharpness = 0.4  # Softer pulses for female voice
            harmonic_rolloff = 0.85
        else:
            pulse_sharpness = 0.35
            harmonic_rolloff = 0.82
        
        # Generate sawtooth-like waveform with natural variations
        voice_signal = np.zeros_like(t)
        
        # Use phase accumulation for smooth frequency changes
        phase = np.zeros_like(t)
        for i in range(1, len(t)):
            dt = t[i] - t[i-1]
            phase[i] = phase[i-1] + 2 * np.pi * pitch[i] * dt
        
        # Generate harmonics with natural decay
        for harmonic in range(1, 16):  # Up to 15th harmonic
            harmonic_amplitude = (1.0 / harmonic) * (harmonic_rolloff ** (harmonic - 1))
            
            # Add slight random phase for naturalness
            phase_noise = np.random.normal(0, 0.1, len(t))
            harmonic_signal = harmonic_amplitude * np.sin(phase * harmonic + phase_noise)
            
            # Apply pulse shaping
            harmonic_signal *= (1.0 - pulse_sharpness * np.abs(np.sin(phase * harmonic)))
            
            voice_signal += harmonic_signal
        
        return voice_signal
    
    def _apply_vocal_tract_filter(self, signal: np.ndarray, f1: float, f2: float, voice_id: str) -> np.ndarray:
        """Apply simplified vocal tract formant filtering"""
        # Simulate formant filtering using simple resonant filters
        
        # Voice-specific formant adjustments for singing
        if 'male' in voice_id.lower():
            f1_singing = f1 * 0.95  # Slightly lower for male singing
            f2_singing = f2 * 0.92
            f3_singing = 2800  # Third formant
        elif 'female' in voice_id.lower():
            f1_singing = f1 * 1.05  # Slightly higher for female singing
            f2_singing = f2 * 1.08
            f3_singing = 3200  # Third formant
        else:
            f1_singing = f1
            f2_singing = f2
            f3_singing = 3000
        
        # Apply simple formant emphasis using frequency modulation
        dt = 1.0 / 22050  # Assume 22050 Hz sample rate
        t = np.arange(len(signal)) * dt
        
        # Create formant resonances
        formant_response = (
            0.6 * np.exp(-((t * 1000 - f1_singing/1000)**2) / (2 * (200/1000)**2)) +  # F1
            0.4 * np.exp(-((t * 1000 - f2_singing/1000)**2) / (2 * (300/1000)**2)) +  # F2
            0.2 * np.exp(-((t * 1000 - f3_singing/1000)**2) / (2 * (400/1000)**2))    # F3
        )
        
        # Apply formant coloring more naturally
        filtered_signal = signal * (0.7 + 0.3 * np.tile(formant_response[:min(len(formant_response), len(signal))], 
                                                        (len(signal) // len(formant_response) + 1))[:len(signal)])
        
        return filtered_signal
    
    def _add_vocal_texture(self, signal: np.ndarray, t: np.ndarray, voice_id: str) -> np.ndarray:
        """Add natural vocal textures like breathiness and throat resonance"""
        
        # Voice-specific texture parameters
        if 'male' in voice_id.lower():
            breathiness = 0.01
            throat_resonance = 0.15
            vocal_fry_intensity = 0.02
        elif 'female' in voice_id.lower():
            breathiness = 0.015
            throat_resonance = 0.12
            vocal_fry_intensity = 0.01
        else:
            breathiness = 0.012
            throat_resonance = 0.13
            vocal_fry_intensity = 0.015
        
        # Add breath noise (filtered white noise)
        breath_noise = np.random.normal(0, breathiness, len(signal))
        
        # Add throat resonance (low-frequency rumble)
        throat_freq = 80 + np.random.normal(0, 5, len(t))  # Around 80Hz with variation
        throat_signal = throat_resonance * np.sin(2 * np.pi * throat_freq * t)
        
        # Add occasional vocal fry for naturalness (very low frequency modulation)
        if np.random.random() > 0.7:  # 30% chance of vocal fry
            fry_modulation = vocal_fry_intensity * np.sin(2 * np.pi * 50 * t) * np.random.exponential(0.3, len(t))
            signal += fry_modulation
        
        # Combine all elements
        textured_signal = signal + breath_noise + throat_signal
        
        # Apply natural amplitude modulation for singing vibrato on amplitude
        amp_vibrato = 1.0 + 0.03 * np.sin(2 * np.pi * 4.5 * t)  # Slight amplitude vibrato
        textured_signal *= amp_vibrato
        
        return textured_signal
    
    def _generate_natural_syllable_envelope(self, length: int, syllable: str) -> np.ndarray:
        """Generate natural envelope for syllables in singing with phoneme awareness"""
        t = np.linspace(0, 1, length)
        
        # Analyze syllable for phoneme characteristics
        vowels = 'aeiou'
        consonants = 'bcdfghjklmnpqrstvwxyz'
        
        vowel_count = sum(1 for c in syllable.lower() if c in vowels)
        consonant_count = sum(1 for c in syllable.lower() if c in consonants)
        
        # Determine envelope shape based on phoneme content
        if vowel_count > consonant_count:
            # Vowel-dominated syllable: longer sustain, smoother transitions
            attack_time = 0.2
            sustain_level = 0.9
            release_time = 0.25
            vibrato_influence = 1.0
        elif consonant_count > vowel_count:
            # Consonant-dominated syllable: sharper attack, shorter sustain
            attack_time = 0.1
            sustain_level = 0.7
            release_time = 0.35
            vibrato_influence = 0.6
        else:
            # Balanced syllable
            attack_time = 0.15
            sustain_level = 0.8
            release_time = 0.3
            vibrato_influence = 0.8
        
        envelope = np.ones_like(t)
        
        # Natural attack with breath onset
        attack_mask = t < attack_time
        if np.any(attack_mask):
            # Use exponential curve for more natural attack
            attack_curve = 1 - np.exp(-5 * t[attack_mask] / attack_time)
            envelope[attack_mask] = attack_curve
        
        # Sustain phase with natural breathing variation
        sustain_start = attack_time
        sustain_end = 1.0 - release_time
        sustain_mask = (t >= sustain_start) & (t < sustain_end)
        
        if np.any(sustain_mask):
            sustain_t = t[sustain_mask]
            # Add natural breathing patterns and micro-vibrato
            breathing_pattern = 1.0 + 0.02 * np.sin(8 * np.pi * sustain_t) * vibrato_influence
            micro_vibrato = 1.0 + 0.01 * np.sin(25 * np.pi * sustain_t) * vibrato_influence
            
            # Combine natural variations
            natural_variation = breathing_pattern * micro_vibrato
            envelope[sustain_mask] = sustain_level * natural_variation
        
        # Natural release with breath decay
        release_mask = t >= sustain_end
        if np.any(release_mask):
            release_t = (t[release_mask] - sustain_end) / release_time
            # Use exponential decay for natural release
            release_curve = sustain_level * np.exp(-3 * release_t)
            envelope[release_mask] = release_curve
        
        # Add slight random variations for humanness
        random_variation = 1.0 + np.random.normal(0, 0.02, len(t))
        envelope *= np.clip(random_variation, 0.8, 1.2)
        
        return np.clip(envelope, 0, 1)
    
    def _add_natural_ambience(self, audio: np.ndarray, sample_rate: int) -> np.ndarray:
        """Add natural room tone and breath sounds for singing"""
        # Add very subtle room tone
        room_tone = np.random.normal(0, 0.003, len(audio))
        
        # Add simple reverb for natural space
        reverb_audio = self._add_simple_reverb(audio, sample_rate)
        
        # Combine with room tone
        natural_audio = reverb_audio + room_tone
        
        # Apply gentle high-frequency roll-off for warmth
        # Simple high-frequency attenuation
        if len(natural_audio) > 100:
            # Apply a simple moving average to soften high frequencies
            window_size = max(1, sample_rate // 5000)  # Small window for subtle effect
            if window_size > 1:
                kernel = np.ones(window_size) / window_size
                natural_audio = np.convolve(natural_audio, kernel, mode='same')
        
        return natural_audio
    
    def _generate_syllable_envelope(self, length: int) -> np.ndarray:
        """Generate an envelope that shapes the syllable for natural speech patterns"""
        t = np.linspace(0, 1, length)
        
        # Attack-decay-sustain-release envelope
        attack_time = 0.1
        decay_time = 0.2
        sustain_level = 0.7
        release_time = 0.3
        
        envelope = np.ones_like(t)
        
        # Attack phase
        attack_mask = t < attack_time
        envelope[attack_mask] = t[attack_mask] / attack_time
        
        # Decay phase
        decay_mask = (t >= attack_time) & (t < attack_time + decay_time)
        decay_t = (t[decay_mask] - attack_time) / decay_time
        envelope[decay_mask] = 1.0 - (1.0 - sustain_level) * decay_t
        
        # Sustain phase
        sustain_mask = (t >= attack_time + decay_time) & (t < 1.0 - release_time)
        envelope[sustain_mask] = sustain_level
        
        # Release phase
        release_mask = t >= 1.0 - release_time
        release_t = (t[release_mask] - (1.0 - release_time)) / release_time
        envelope[release_mask] = sustain_level * (1.0 - release_t)
        
        return envelope
    
    def _add_simple_reverb(self, audio: np.ndarray, sample_rate: int) -> np.ndarray:
        """Add simple reverb effect to make the audio sound more natural"""
        # Simple delay-based reverb
        delay_samples = int(0.05 * sample_rate)  # 50ms delay
        
        if len(audio) <= delay_samples:
            return audio
            
        reverb_audio = audio.copy()
        
        # Add delayed signals with decreasing amplitude
        for i, delay_mult in enumerate([1, 2, 3], 1):
            delay = delay_samples * delay_mult
            if delay < len(audio):
                reverb_gain = 0.3 / i  # Decreasing amplitude
                reverb_audio[delay:] += audio[:-delay] * reverb_gain
        
        return reverb_audio
    
    def _parse_chord(self, chord_name: str) -> list:
        """Parse chord name and return note intervals for harmonization"""
        if not chord_name:
            return []
        
        # Common chord patterns (semitones from root)
        chord_patterns = {
            'major': [0, 4, 7],
            'minor': [0, 3, 7],
            'major7': [0, 4, 7, 11],
            'minor7': [0, 3, 7, 10],
            'diminished': [0, 3, 6],
            'augmented': [0, 4, 8],
            'sus2': [0, 2, 7],
            'sus4': [0, 5, 7]
        }
        
        try:
            # Extract chord type from name like "C_major", "Fm", "G7"
            chord_lower = chord_name.lower()
            
            if 'major7' in chord_lower or '7' in chord_lower:
                return chord_patterns['major7']
            elif 'minor7' in chord_lower or 'm7' in chord_lower:
                return chord_patterns['minor7']
            elif 'major' in chord_lower or chord_name.isupper():
                return chord_patterns['major']
            elif 'minor' in chord_lower or 'm' in chord_lower:
                return chord_patterns['minor']
            elif 'dim' in chord_lower:
                return chord_patterns['diminished']
            elif 'aug' in chord_lower:
                return chord_patterns['augmented']
            elif 'sus2' in chord_lower:
                return chord_patterns['sus2']
            elif 'sus4' in chord_lower:
                return chord_patterns['sus4']
            else:
                return chord_patterns['major']  # Default to major
                
        except Exception as e:
            logger.warning(f"Could not parse chord '{chord_name}': {e}")
            return chord_patterns['major']
    
    def _add_harmony(self, fundamental_freq: float, chord_intervals: list, 
                     t: np.ndarray, voice_id: str, harmony_level: float = 0.3) -> np.ndarray:
        """Add harmonic voices based on chord intervals"""
        if not chord_intervals:
            return np.zeros_like(t)
        
        harmony_signal = np.zeros_like(t)
        
        for interval in chord_intervals[1:]:  # Skip root (fundamental)
            # Calculate harmony frequency
            harmony_freq = fundamental_freq * (2 ** (interval / 12.0))
            
            # Generate harmony voice with different characteristics
            if 'female' in voice_id.lower():
                formant_shift = 1.3  # Higher for female harmony
                vibrato_rate = 5.8
            else:
                formant_shift = 0.7  # Lower for male harmony
                vibrato_rate = 4.2
            
            # Generate softer harmony voice
            harmony_voice = self._generate_vocal_formants(
                t, harmony_freq, voice_id, formant_shift, vibrato_rate
            )
            
            # Apply harmony envelope (softer than lead)
            harmony_envelope = self._generate_syllable_envelope(len(t)) * harmony_level
            harmony_voice *= harmony_envelope
            
            harmony_signal += harmony_voice
        
        return harmony_signal
