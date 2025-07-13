"""
Custom Voice Audio Generation Module
Handles unique audio generation for custom voices
"""

import os
import tempfile
import logging
import numpy as np
import soundfile as sf
from typing import Dict, Any

try:
    from scipy import signal as scipy_signal
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

logger = logging.getLogger(__name__)


class CustomVoiceGenerator:
    """Handles audio generation for custom voices with unique characteristics"""
    
    def __init__(self):
        self.sample_rate = 22050
    
    def generate_custom_voice_audio(self, text: str, voice_id: str, voice_characteristics: Dict[str, Any]) -> str:
        """Generate audio for custom voices with analyzed characteristics"""
        logger.info(f"Generating custom voice audio for '{voice_id}' with characteristics: {voice_characteristics}")
        
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
        temp_file.close()
        
        # Extract voice characteristics (use analyzed data if available)
        fundamental_freq = voice_characteristics.get('fundamental_freq', 160)
        formant_shift = voice_characteristics.get('formant_shift', 1.0)
        vibrato_rate = voice_characteristics.get('vibrato_rate', 5.0)
        voice_texture = voice_characteristics.get('voice_texture', 0.5)
        voice_warmth = voice_characteristics.get('voice_warmth', 0.8)
        voice_name = voice_characteristics.get('voice_name', voice_id)
        
        # Use MFCC features if available for more realistic timbre
        mfcc_features = voice_characteristics.get('mfcc_mean', [])
        spectral_centroid = voice_characteristics.get('spectral_centroid', 1500)
        voice_energy = voice_characteristics.get('voice_energy', 0.15)
        voice_dynamics = voice_characteristics.get('voice_dynamics', 0.1)
        
        logger.info(f"Voice characteristics: freq={fundamental_freq:.1f}Hz, formant={formant_shift:.2f}, "
                   f"texture={voice_texture:.2f}, warmth={voice_warmth:.2f}")
        
        # Create speech patterns based on analyzed characteristics
        duration = max(1.5, len(text) * 0.12)
        t = np.linspace(0, duration, int(self.sample_rate * duration))
        
        # Create more human-like speech patterns
        words = text.split()
        audio = np.zeros_like(t)
        
        for i, word in enumerate(words):
            start_time = i * duration / len(words)
            end_time = (i + 1) * duration / len(words)
            start_idx = int(start_time * self.sample_rate)
            end_idx = int(end_time * self.sample_rate)
            
            if start_idx >= len(t) or end_idx > len(t):
                continue
                
            word_t = t[start_idx:end_idx]
            
            # Generate more realistic voice signal
            signal = self._generate_realistic_voice_signal(
                word_t, fundamental_freq, formant_shift, vibrato_rate,
                voice_texture, voice_warmth, spectral_centroid, mfcc_features
            )
            
            # Apply natural envelope with voice dynamics
            envelope = self._generate_natural_envelope(len(word_t), voice_dynamics)
            signal *= envelope
            
            # Add realistic pauses between words
            if i < len(words) - 1:
                pause_duration = 0.04 + (voice_dynamics * 0.02)
                pause_start = end_idx - int(pause_duration * self.sample_rate)
                pause_end = min(end_idx + int(pause_duration * self.sample_rate), len(audio))
                if pause_start < len(audio):
                    audio[pause_start:pause_end] *= 0.05
            
            audio[start_idx:end_idx] = signal
        
        # Add realistic voice resonance
        audio = self._add_voice_resonance(audio, fundamental_freq, voice_warmth)
        
        # Apply voice-specific dynamics
        audio = self._apply_voice_dynamics(audio, voice_energy, voice_dynamics)
        
        # Add natural reverb
        audio = self._add_custom_reverb(audio, voice_characteristics)
        
        sf.write(temp_file.name, audio, self.sample_rate)
        logger.info(f"Realistic custom voice audio generated: {temp_file.name}")
        return temp_file.name
    
    def _generate_realistic_voice_signal(self, t: np.ndarray, fundamental_freq: float,
                                        formant_shift: float, vibrato_rate: float,
                                        voice_texture: float, voice_warmth: float,
                                        spectral_centroid: float, mfcc_features: list) -> np.ndarray:
        """Generate more realistic voice signal based on analyzed characteristics"""
        
        # Create natural frequency modulation
        vibrato = 1.0 + 0.02 * np.sin(2 * np.pi * vibrato_rate * t)
        
        # Add natural frequency variation (speech prosody)
        prosody = 1.0 + 0.05 * np.sin(2 * np.pi * 0.5 * t)  # Slower pitch variation
        
        freq = fundamental_freq * vibrato * prosody
        
        # Generate formants based on analyzed characteristics
        formant1 = freq * 2.2 * formant_shift
        formant2 = freq * 3.8 * formant_shift  
        formant3 = freq * 5.5 * formant_shift
        
        # Generate base signal with harmonics
        signal = (
            0.5 * np.sin(2 * np.pi * freq * t) +                      # Fundamental
            0.3 * voice_warmth * np.sin(2 * np.pi * formant1 * t) +   # First formant
            0.2 * voice_warmth * np.sin(2 * np.pi * formant2 * t) +   # Second formant
            0.1 * voice_warmth * np.sin(2 * np.pi * formant3 * t) +   # Third formant
            0.05 * np.sin(2 * np.pi * freq * 2 * t) +                 # Second harmonic
            0.03 * np.sin(2 * np.pi * freq * 3 * t)                   # Third harmonic
        )
        
        # Add voice texture (breathiness, roughness)
        if voice_texture > 0.1:
            noise_level = voice_texture * 0.15
            texture_noise = np.random.normal(0, noise_level, len(t))
            # Apply texture more to consonant-like areas
            texture_mask = np.sin(t * 25) > 0.5
            signal[texture_mask] += texture_noise[texture_mask]
        
        # Add subtle spectral coloring based on MFCC features
        if mfcc_features and len(mfcc_features) >= 3:
            # Use first few MFCC coefficients to add spectral character
            spectral_color = (
                0.05 * mfcc_features[1] * np.sin(2 * np.pi * freq * 1.5 * t) +
                0.03 * mfcc_features[2] * np.sin(2 * np.pi * freq * 2.5 * t)
            )
            signal += spectral_color
        
        # Add natural breath noise
        breath_intensity = 0.01 + voice_texture * 0.02
        breath_noise = np.random.normal(0, breath_intensity, len(t))
        
        # Filter breath noise to make it more natural
        if SCIPY_AVAILABLE:
            b, a = scipy_signal.butter(2, 0.1, btype='low')
            try:
                breath_noise = scipy_signal.filtfilt(b, a, breath_noise)
            except:
                pass  # Fallback if filtering fails
        
        signal += breath_noise
        
        return signal
    
    def _generate_natural_envelope(self, length: int, voice_dynamics: float) -> np.ndarray:
        """Generate natural envelope based on voice dynamics"""
        t = np.linspace(0, 1, length)
        
        # Base envelope shape
        attack_time = 0.05 + voice_dynamics * 0.05
        decay_time = 0.1 + voice_dynamics * 0.1
        sustain_level = 0.7 + voice_dynamics * 0.2
        release_time = 0.2 + voice_dynamics * 0.1
        
        envelope = np.ones_like(t)
        
        # Attack
        attack_mask = t < attack_time
        envelope[attack_mask] = t[attack_mask] / attack_time
        
        # Decay
        decay_mask = (t >= attack_time) & (t < attack_time + decay_time)
        if np.any(decay_mask):
            decay_t = (t[decay_mask] - attack_time) / decay_time
            envelope[decay_mask] = 1.0 - (1.0 - sustain_level) * decay_t
        
        # Sustain
        sustain_mask = (t >= attack_time + decay_time) & (t < 1.0 - release_time)
        envelope[sustain_mask] = sustain_level
        
        # Release
        release_mask = t >= 1.0 - release_time
        if np.any(release_mask):
            release_t = (t[release_mask] - (1.0 - release_time)) / release_time
            envelope[release_mask] = sustain_level * (1.0 - release_t)
        
        # Add natural variation
        if voice_dynamics > 0.1:
            variation = voice_dynamics * 0.1 * np.sin(t * 8)
            envelope *= (1.0 + variation)
        
        return envelope
    
    def _add_voice_resonance(self, audio: np.ndarray, fundamental_freq: float, voice_warmth: float) -> np.ndarray:
        """Add natural voice resonance characteristics"""
        # Create resonance frequencies
        resonance1 = fundamental_freq * 1.5
        resonance2 = fundamental_freq * 2.3
        
        t = np.linspace(0, len(audio) / self.sample_rate, len(audio))
        
        # Add resonance with warmth-dependent strength
        resonance_strength = voice_warmth * 0.08
        resonance = (
            resonance_strength * np.sin(2 * np.pi * resonance1 * t) +
            resonance_strength * 0.5 * np.sin(2 * np.pi * resonance2 * t)
        )
        
        return audio + resonance
    
    def _apply_voice_dynamics(self, audio: np.ndarray, voice_energy: float, voice_dynamics: float) -> np.ndarray:
        """Apply voice-specific energy and dynamics"""
        # Normalize and apply energy level
        if np.max(np.abs(audio)) > 0:
            audio = audio / np.max(np.abs(audio))
        
        # Apply energy scaling
        energy_level = 0.6 + voice_energy * 0.3
        audio *= energy_level
        
        # Apply dynamic range compression/expansion
        if voice_dynamics > 0.15:
            # More dynamic voice - expand range slightly
            audio = np.sign(audio) * np.power(np.abs(audio), 0.9)
        elif voice_dynamics < 0.08:
            # Less dynamic voice - compress range slightly
            audio = np.sign(audio) * np.power(np.abs(audio), 1.1)
        
        return audio
        """Generate the core voice signal with custom characteristics"""
        # Create vowel-like sounds with custom voice formants
        formant1 = base_freq * 2.3 * formant_shift  # First formant
        formant2 = base_freq * 4.2 * formant_shift  # Second formant
        formant3 = base_freq * 6.8 * formant_shift  # Third formant
        
        # Add custom vibrato pattern
        vibrato = 1.0 + 0.03 * np.sin(2 * np.pi * vibrato_rate * t)
        
        # Modulate frequency with custom patterns
        freq_mod = vibrato * (1.0 + 0.12 * np.sin(t * 7))
        
        # Generate custom formant-like audio
        signal = (
            0.45 * np.sin(2 * np.pi * base_freq * freq_mod * t) +
            0.35 * np.sin(2 * np.pi * formant1 * freq_mod * t) +
            0.25 * np.sin(2 * np.pi * formant2 * freq_mod * t) +
            0.15 * np.sin(2 * np.pi * formant3 * freq_mod * t)
        )
        
        # Add custom consonant-like noise (varies by voice characteristics)
        noise_intensity = 0.08 + (hash(voice_name) % 20) / 200  # Range 0.08-0.18
        noise = np.random.normal(0, noise_intensity, len(t))
        consonant_mask = np.sin(t * 18) > 0.6
        signal[consonant_mask] += noise[consonant_mask] * 0.6
        
        return signal
    
    def _generate_custom_envelope(self, length: int, voice_name: str) -> np.ndarray:
        """Generate custom envelope based on voice characteristics"""
        t = np.linspace(0, 1, length)
        
        # Custom envelope frequency based on voice name
        envelope_freq = 5.5 + (hash(voice_name) % 10) / 10  # Range 5.5-6.5
        envelope = 0.5 * (1 + np.sin(t * envelope_freq - np.pi/2))
        
        return envelope
    
    def _add_custom_reverb(self, audio: np.ndarray, voice_characteristics: Dict[str, Any]) -> np.ndarray:
        """Add custom reverb effect based on voice characteristics"""
        voice_name = voice_characteristics.get('voice_name', 'custom')
        
        # Custom reverb parameters based on voice
        delay_samples = int((0.04 + (hash(voice_name) % 20) / 1000) * self.sample_rate)  # 40-60ms delay
        
        if len(audio) <= delay_samples:
            return audio
            
        reverb_audio = audio.copy()
        
        # Add delayed signals with voice-specific characteristics
        reverb_strength = 0.25 + (hash(voice_name) % 15) / 100  # Range 0.25-0.40
        
        for i, delay_mult in enumerate([1, 2, 3], 1):
            delay = delay_samples * delay_mult
            if delay < len(audio):
                reverb_gain = reverb_strength / i  # Decreasing amplitude
                reverb_audio[delay:] += audio[:-delay] * reverb_gain
        
        return reverb_audio
