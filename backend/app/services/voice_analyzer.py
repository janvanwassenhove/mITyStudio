"""
Voice Analysis Module
Extracts voice characteristics from audio files for custom voice generation
"""

import logging
import numpy as np
import librosa
from typing import Dict, Any, List
from pathlib import Path

logger = logging.getLogger(__name__)


class VoiceAnalyzer:
    """Analyzes audio files to extract voice characteristics"""
    
    def __init__(self):
        self.sample_rate = 22050
    
    def analyze_voice_characteristics(self, audio_files: List[str]) -> Dict[str, Any]:
        """Analyze audio files to extract voice characteristics"""
        try:
            all_features = []
            
            for audio_file in audio_files:
                if not Path(audio_file).exists():
                    continue
                    
                features = self._extract_features_from_file(audio_file)
                if features:
                    all_features.append(features)
            
            if not all_features:
                logger.warning("No valid audio features extracted, using default characteristics")
                return self._get_default_characteristics()
            
            # Aggregate features across all files
            characteristics = self._aggregate_features(all_features)
            
            logger.info(f"Extracted voice characteristics: {characteristics}")
            return characteristics
            
        except Exception as e:
            logger.error(f"Failed to analyze voice characteristics: {e}")
            return self._get_default_characteristics()
    
    def _extract_features_from_file(self, audio_file: str) -> Dict[str, float]:
        """Extract voice features from a single audio file"""
        try:
            # Load audio
            y, sr = librosa.load(audio_file, sr=self.sample_rate)
            
            if len(y) < self.sample_rate * 0.5:  # Less than 0.5 seconds
                return None
            
            # Extract fundamental frequency (pitch)
            pitches, magnitudes = librosa.piptrack(y=y, sr=sr, fmin=50, fmax=500)
            pitch_values = []
            
            for t in range(pitches.shape[1]):
                index = magnitudes[:, t].argmax()
                pitch = pitches[index, t]
                if pitch > 0:
                    pitch_values.append(pitch)
            
            if not pitch_values:
                fundamental_freq = 180  # Default
            else:
                fundamental_freq = np.median(pitch_values)
            
            # Extract spectral features
            spectral_centroids = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
            spectral_rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)[0]
            spectral_bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr)[0]
            
            # Extract MFCC features for voice timbre
            mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
            
            # Extract tempo and rhythm
            tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
            
            # Extract formant-like characteristics
            formant_shift = np.mean(spectral_centroids) / 1000.0  # Normalize
            formant_shift = max(0.5, min(2.0, formant_shift))  # Clamp to reasonable range
            
            # Extract voice quality measures
            zero_crossing_rate = np.mean(librosa.feature.zero_crossing_rate(y))
            
            return {
                'fundamental_freq': float(fundamental_freq),
                'formant_shift': float(formant_shift),
                'spectral_centroid': float(np.mean(spectral_centroids)),
                'spectral_rolloff': float(np.mean(spectral_rolloff)),
                'spectral_bandwidth': float(np.mean(spectral_bandwidth)),
                'mfcc_mean': [float(x) for x in np.mean(mfccs, axis=1)],
                'tempo': float(tempo),
                'zero_crossing_rate': float(zero_crossing_rate),
                'voice_energy': float(np.mean(np.abs(y))),
                'voice_dynamics': float(np.std(y))
            }
            
        except Exception as e:
            logger.error(f"Failed to extract features from {audio_file}: {e}")
            return None
    
    def _aggregate_features(self, all_features: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate features from multiple audio files"""
        if not all_features:
            return self._get_default_characteristics()
        
        # Calculate means for scalar values
        characteristics = {}
        scalar_keys = ['fundamental_freq', 'formant_shift', 'spectral_centroid', 
                      'spectral_rolloff', 'spectral_bandwidth', 'tempo', 
                      'zero_crossing_rate', 'voice_energy', 'voice_dynamics']
        
        for key in scalar_keys:
            values = [f[key] for f in all_features if key in f]
            if values:
                characteristics[key] = float(np.mean(values))
        
        # Aggregate MFCC features
        mfcc_features = [f['mfcc_mean'] for f in all_features if 'mfcc_mean' in f]
        if mfcc_features:
            characteristics['mfcc_mean'] = [float(x) for x in np.mean(mfcc_features, axis=0)]
        
        # Derive additional characteristics
        characteristics['vibrato_rate'] = self._calculate_vibrato_rate(characteristics)
        characteristics['voice_texture'] = self._calculate_voice_texture(characteristics)
        characteristics['voice_warmth'] = self._calculate_voice_warmth(characteristics)
        
        return characteristics
    
    def _calculate_vibrato_rate(self, characteristics: Dict[str, Any]) -> float:
        """Calculate vibrato rate based on voice characteristics"""
        base_rate = 5.0
        
        # Adjust based on fundamental frequency
        freq = characteristics.get('fundamental_freq', 180)
        if freq > 200:  # Higher pitch voices tend to have faster vibrato
            base_rate += 1.0
        elif freq < 150:  # Lower pitch voices tend to have slower vibrato
            base_rate -= 1.0
        
        # Adjust based on voice dynamics
        dynamics = characteristics.get('voice_dynamics', 0.1)
        if dynamics > 0.15:  # More dynamic voices
            base_rate += 0.5
        
        return max(3.0, min(8.0, base_rate))
    
    def _calculate_voice_texture(self, characteristics: Dict[str, Any]) -> float:
        """Calculate voice texture/roughness"""
        zero_crossing = characteristics.get('zero_crossing_rate', 0.1)
        spectral_bandwidth = characteristics.get('spectral_bandwidth', 1000)
        
        # Higher zero crossing rate and spectral bandwidth indicate rougher texture
        texture = (zero_crossing * 10) + (spectral_bandwidth / 5000)
        return max(0.1, min(2.0, texture))
    
    def _calculate_voice_warmth(self, characteristics: Dict[str, Any]) -> float:
        """Calculate voice warmth based on spectral characteristics"""
        spectral_centroid = characteristics.get('spectral_centroid', 1000)
        voice_energy = characteristics.get('voice_energy', 0.1)
        
        # Lower spectral centroid and higher energy indicate warmer voice
        warmth = (2000 - spectral_centroid) / 1000 + voice_energy * 2
        return max(0.3, min(1.5, warmth))
    
    def _get_default_characteristics(self) -> Dict[str, Any]:
        """Get default voice characteristics when analysis fails"""
        return {
            'fundamental_freq': 180.0,
            'formant_shift': 1.0,
            'spectral_centroid': 1500.0,
            'spectral_rolloff': 3000.0,
            'spectral_bandwidth': 1200.0,
            'mfcc_mean': [0.0] * 13,
            'tempo': 120.0,
            'zero_crossing_rate': 0.1,
            'voice_energy': 0.15,
            'voice_dynamics': 0.1,
            'vibrato_rate': 5.0,
            'voice_texture': 0.5,
            'voice_warmth': 0.8
        }
