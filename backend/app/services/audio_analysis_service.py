"""
Advanced Audio Analysis Service for Sample Tagging
Uses YAMNet, librosa, and other ML models for automatic sample categorization and tagging
"""

import numpy as np
import librosa
import tensorflow as tf
from typing import Dict, List, Any, Optional, Tuple
import os
import logging
from dataclasses import dataclass
from enum import Enum

# Configure logging
logger = logging.getLogger(__name__)

class TrackType(Enum):
    VOCALS_ONLY = "vocals"
    INSTRUMENTALS_ONLY = "instrumentals"
    VOCALS_AND_INSTRUMENTALS = "vocals_and_instrumentals"
    UNKNOWN = "unknown"

class VibeCategory(Enum):
    ENERGETIC = "energetic"
    CHILL = "chill"
    DARK = "dark"
    BRIGHT = "bright"
    AGGRESSIVE = "aggressive"
    SMOOTH = "smooth"
    DREAMY = "dreamy"
    GROOVY = "groovy"
    ATMOSPHERIC = "atmospheric"
    MINIMAL = "minimal"

@dataclass
class AudioAnalysisResult:
    """Comprehensive audio analysis result"""
    # Basic properties
    duration: float
    tempo: float
    key: Optional[str]
    time_signature: Optional[str]
    
    # Advanced categorization
    track_type: TrackType
    primary_category: str
    secondary_categories: List[str]
    
    # Vibe and mood
    vibe: VibeCategory
    energy_level: float  # 0.0 to 1.0
    valence: float  # 0.0 (negative) to 1.0 (positive)
    danceability: float  # 0.0 to 1.0
    
    # Semantic tags
    instrument_tags: List[str]
    genre_tags: List[str]
    mood_tags: List[str]
    style_tags: List[str]
    
    # Technical analysis
    spectral_centroid_mean: float
    spectral_rolloff_mean: float
    mfcc_features: List[float]
    zero_crossing_rate: float
    
    # YAMNet classifications
    yamnet_top_classes: List[Tuple[str, float]]  # (class_name, confidence)
    
    # Enhanced description
    auto_description: str

class AdvancedAudioAnalyzer:
    """Advanced audio analysis using multiple ML models and signal processing techniques"""
    
    def __init__(self):
        self.yamnet_model = None
        self.yamnet_labels = None
        self._load_models()
    
    def _load_models(self):
        """Load YAMNet and other models"""
        try:
            # Load YAMNet model
            import tensorflow_hub as hub
            self.yamnet_model = hub.load('https://tfhub.dev/google/yamnet/1')
            
            # Load YAMNet class labels
            class_names_path = tf.keras.utils.get_file(
                'yamnet_class_map.csv',
                'https://raw.githubusercontent.com/tensorflow/models/master/research/audioset/yamnet/yamnet_class_map.csv')
            
            with open(class_names_path, 'r') as f:
                lines = f.readlines()
                self.yamnet_labels = [line.strip().split(',')[2] for line in lines[1:]]  # Skip header
            
            logger.info("Successfully loaded YAMNet model and labels")
            
        except Exception as e:
            logger.warning(f"Could not load YAMNet model: {e}. Will use fallback analysis.")
            self.yamnet_model = None
    
    def analyze_audio_file(self, file_path: str, sample_rate: int = 16000) -> AudioAnalysisResult:
        """
        Perform comprehensive analysis of an audio file
        
        Args:
            file_path: Path to the audio file
            sample_rate: Target sample rate for analysis
            
        Returns:
            AudioAnalysisResult with comprehensive metadata
        """
        try:
            # Load audio file
            y, sr = librosa.load(file_path, sr=sample_rate)
            
            # Basic audio properties
            duration = librosa.get_duration(y=y, sr=sr)
            
            # Tempo and beat analysis
            tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
            
            # Key detection using chromagram
            key = self._detect_key(y, sr)
            
            # Advanced feature extraction
            features = self._extract_advanced_features(y, sr)
            
            # YAMNet classification
            yamnet_classes = self._yamnet_classify(y, sr) if self.yamnet_model else []
            
            # Track type detection (vocals vs instrumentals)
            track_type = self._detect_track_type(y, sr, yamnet_classes)
            
            # Category classification
            primary_category, secondary_categories = self._classify_categories(
                features, yamnet_classes, tempo)
            
            # Vibe and mood analysis
            vibe, energy, valence, danceability = self._analyze_vibe_and_mood(
                features, tempo, yamnet_classes)
            
            # Generate semantic tags
            instrument_tags = self._extract_instrument_tags(yamnet_classes)
            genre_tags = self._extract_genre_tags(yamnet_classes, tempo, features)
            mood_tags = self._extract_mood_tags(valence, energy, features)
            style_tags = self._extract_style_tags(features, tempo)
            
            # Generate description
            description = self._generate_description(
                track_type, primary_category, vibe, tempo, key, instrument_tags)
            
            return AudioAnalysisResult(
                duration=duration,
                tempo=float(tempo),
                key=key,
                time_signature=self._estimate_time_signature(beats, sr),
                track_type=track_type,
                primary_category=primary_category,
                secondary_categories=secondary_categories,
                vibe=vibe,
                energy_level=energy,
                valence=valence,
                danceability=danceability,
                instrument_tags=instrument_tags,
                genre_tags=genre_tags,
                mood_tags=mood_tags,
                style_tags=style_tags,
                spectral_centroid_mean=features['spectral_centroid'],
                spectral_rolloff_mean=features['spectral_rolloff'],
                mfcc_features=features['mfcc'],
                zero_crossing_rate=features['zcr'],
                yamnet_top_classes=yamnet_classes[:10],  # Top 10 classes
                auto_description=description
            )
            
        except Exception as e:
            logger.error(f"Error analyzing audio file {file_path}: {e}")
            # Return minimal analysis result
            return self._create_fallback_result(file_path)
    
    def _extract_advanced_features(self, y: np.ndarray, sr: int) -> Dict[str, Any]:
        """Extract comprehensive audio features"""
        features = {}
        
        # Spectral features
        spectral_centroids = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
        features['spectral_centroid'] = float(np.mean(spectral_centroids))
        
        spectral_rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)[0]
        features['spectral_rolloff'] = float(np.mean(spectral_rolloff))
        
        # MFCC features
        mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
        features['mfcc'] = [float(np.mean(mfcc)) for mfcc in mfccs]
        
        # Zero crossing rate
        zcr = librosa.feature.zero_crossing_rate(y)[0]
        features['zcr'] = float(np.mean(zcr))
        
        # Chroma features
        chroma = librosa.feature.chroma_stft(y=y, sr=sr)
        features['chroma'] = [float(np.mean(c)) for c in chroma]
        
        # Tonnetz features
        tonnetz = librosa.feature.tonnetz(y=y, sr=sr)
        features['tonnetz'] = [float(np.mean(t)) for t in tonnetz]
        
        # RMS energy
        rms = librosa.feature.rms(y=y)[0]
        features['rms'] = float(np.mean(rms))
        
        return features
    
    def _yamnet_classify(self, y: np.ndarray, sr: int) -> List[Tuple[str, float]]:
        """Classify audio using YAMNet"""
        if not self.yamnet_model or not self.yamnet_labels:
            return []
        
        try:
            # Ensure audio is the right length and format for YAMNet
            if len(y.shape) > 1:
                y = np.mean(y, axis=0)
            
            # YAMNet expects 16kHz audio
            if sr != 16000:
                y = librosa.resample(y, orig_sr=sr, target_sr=16000)
            
            # Get predictions
            scores, embeddings, spectrogram = self.yamnet_model(y)
            
            # Get mean scores across time
            mean_scores = np.mean(scores, axis=0)
            
            # Get top classes
            top_indices = np.argsort(mean_scores)[::-1]
            
            top_classes = []
            for i in top_indices[:20]:  # Top 20 classes
                class_name = self.yamnet_labels[i]
                confidence = float(mean_scores[i])
                top_classes.append((class_name, confidence))
            
            return top_classes
            
        except Exception as e:
            logger.warning(f"YAMNet classification failed: {e}")
            return []
    
    def _detect_key(self, y: np.ndarray, sr: int) -> Optional[str]:
        """Detect musical key using chromagram analysis"""
        try:
            # Generate chromagram
            chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
            
            # Average across time
            chroma_mean = np.mean(chroma, axis=1)
            
            # Key templates (major and minor)
            major_template = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
            minor_template = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
            
            # Note names
            notes = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
            
            best_correlation = -1
            best_key = None
            
            # Test all keys
            for i in range(12):
                # Major key
                major_corr = np.corrcoef(chroma_mean, np.roll(major_template, i))[0, 1]
                if major_corr > best_correlation:
                    best_correlation = major_corr
                    best_key = f"{notes[i]} major"
                
                # Minor key
                minor_corr = np.corrcoef(chroma_mean, np.roll(minor_template, i))[0, 1]
                if minor_corr > best_correlation:
                    best_correlation = minor_corr
                    best_key = f"{notes[i]} minor"
            
            return best_key if best_correlation > 0.6 else None
            
        except Exception as e:
            logger.warning(f"Key detection failed: {e}")
            return None
    
    def _detect_track_type(self, y: np.ndarray, sr: int, 
                          yamnet_classes: List[Tuple[str, float]]) -> TrackType:
        """Detect if track contains vocals, instrumentals, or both"""
        
        # Check YAMNet classifications for vocal indicators
        vocal_keywords = ['singing', 'speech', 'vocal', 'voice', 'choir', 'humming', 'yodeling']
        instrumental_keywords = ['music', 'musical instrument', 'guitar', 'piano', 'drum', 'bass']
        
        vocal_confidence = 0.0
        instrumental_confidence = 0.0
        
        for class_name, confidence in yamnet_classes:
            class_lower = class_name.lower()
            
            # Check for vocal indicators
            if any(keyword in class_lower for keyword in vocal_keywords):
                vocal_confidence = max(vocal_confidence, confidence)
            
            # Check for instrumental indicators
            if any(keyword in class_lower for keyword in instrumental_keywords):
                instrumental_confidence = max(instrumental_confidence, confidence)
        
        # Determine track type based on confidence levels
        if vocal_confidence > 0.3 and instrumental_confidence > 0.3:
            return TrackType.VOCALS_AND_INSTRUMENTALS
        elif vocal_confidence > 0.3:
            return TrackType.VOCALS_ONLY
        elif instrumental_confidence > 0.3:
            return TrackType.INSTRUMENTALS_ONLY
        else:
            return TrackType.UNKNOWN
    
    def _classify_categories(self, features: Dict[str, Any], 
                           yamnet_classes: List[Tuple[str, float]],
                           tempo: float) -> Tuple[str, List[str]]:
        """Classify sample into primary and secondary categories"""
        
        # Analyze YAMNet classes for category hints
        category_indicators = {
            'drums': ['drum', 'percussion', 'snare', 'kick', 'cymbal', 'hihat'],
            'bass': ['bass', 'double bass', 'electric bass'],
            'guitar': ['guitar', 'electric guitar', 'acoustic guitar'],
            'piano': ['piano', 'electric piano', 'keyboard'],
            'synth': ['synthesizer', 'electronic music'],
            'strings': ['violin', 'cello', 'string', 'orchestra'],
            'brass': ['trumpet', 'trombone', 'horn', 'brass'],
            'woodwinds': ['flute', 'clarinet', 'saxophone', 'oboe'],
            'vocal': ['singing', 'speech', 'voice', 'choir'],
            'fx': ['sound effect', 'echo', 'reverberation']
        }
        
        category_scores = {cat: 0.0 for cat in category_indicators.keys()}
        
        # Score based on YAMNet classifications
        for class_name, confidence in yamnet_classes:
            class_lower = class_name.lower()
            for category, keywords in category_indicators.items():
                if any(keyword in class_lower for keyword in keywords):
                    category_scores[category] = max(category_scores[category], confidence)
        
        # Additional scoring based on audio features
        # High spectral centroid might indicate cymbals or bright instruments
        if features['spectral_centroid'] > 3000:
            category_scores['drums'] += 0.2
            category_scores['synth'] += 0.1
        
        # High zero crossing rate might indicate percussion or noise
        if features['zcr'] > 0.1:
            category_scores['drums'] += 0.2
        
        # Sort categories by score
        sorted_categories = sorted(category_scores.items(), key=lambda x: x[1], reverse=True)
        
        primary_category = sorted_categories[0][0] if sorted_categories[0][1] > 0.2 else 'other'
        secondary_categories = [cat for cat, score in sorted_categories[1:4] if score > 0.15]
        
        return primary_category, secondary_categories
    
    def _analyze_vibe_and_mood(self, features: Dict[str, Any], tempo: float,
                              yamnet_classes: List[Tuple[str, float]]) -> Tuple[VibeCategory, float, float, float]:
        """Analyze vibe, energy, valence, and danceability"""
        
        # Energy calculation based on RMS and spectral features
        energy = min(1.0, features.get('rms', 0.1) * 10 + features.get('spectral_centroid', 1000) / 5000)
        
        # Valence (positivity) based on spectral features and tempo
        valence = 0.5
        if tempo > 120:  # Faster tempo generally more positive
            valence += 0.2
        if features.get('spectral_centroid', 1000) > 2000:  # Brighter sounds more positive
            valence += 0.2
        valence = min(1.0, max(0.0, valence))
        
        # Danceability based on tempo and rhythm consistency
        if 90 <= tempo <= 140:
            danceability = 0.8
        elif 140 < tempo <= 180:
            danceability = 0.9
        else:
            danceability = 0.4
        
        # Determine vibe category
        vibe = VibeCategory.CHILL  # Default
        
        if energy > 0.7 and tempo > 130:
            vibe = VibeCategory.ENERGETIC
        elif energy < 0.3 and tempo < 100:
            vibe = VibeCategory.CHILL
        elif features.get('spectral_centroid', 1000) < 1500:
            vibe = VibeCategory.DARK
        elif features.get('spectral_centroid', 1000) > 3000:
            vibe = VibeCategory.BRIGHT
        elif energy > 0.6 and features.get('zcr', 0) > 0.08:
            vibe = VibeCategory.AGGRESSIVE
        elif 100 <= tempo <= 120 and energy < 0.6:
            vibe = VibeCategory.SMOOTH
        elif valence > 0.7 and energy < 0.5:
            vibe = VibeCategory.DREAMY
        elif 110 <= tempo <= 130 and danceability > 0.7:
            vibe = VibeCategory.GROOVY
        
        return vibe, energy, valence, danceability
    
    def _extract_instrument_tags(self, yamnet_classes: List[Tuple[str, float]]) -> List[str]:
        """Extract instrument-related tags from YAMNet classifications"""
        instrument_tags = []
        
        instrument_map = {
            'guitar': ['guitar', 'electric guitar', 'acoustic guitar'],
            'piano': ['piano', 'electric piano', 'keyboard'],
            'drums': ['drum', 'snare drum', 'bass drum', 'cymbal'],
            'bass': ['bass guitar', 'double bass'],
            'synthesizer': ['synthesizer', 'electronic music'],
            'violin': ['violin', 'fiddle'],
            'saxophone': ['saxophone'],
            'trumpet': ['trumpet'],
            'flute': ['flute']
        }
        
        for class_name, confidence in yamnet_classes:
            if confidence > 0.3:  # Only high-confidence classifications
                class_lower = class_name.lower()
                for instrument, keywords in instrument_map.items():
                    if any(keyword in class_lower for keyword in keywords):
                        if instrument not in instrument_tags:
                            instrument_tags.append(instrument)
        
        return instrument_tags[:5]  # Limit to top 5
    
    def _extract_genre_tags(self, yamnet_classes: List[Tuple[str, float]],
                           tempo: float, features: Dict[str, Any]) -> List[str]:
        """Extract genre-related tags based on analysis"""
        genre_tags = []
        
        # Tempo-based genre hints
        if 60 <= tempo <= 90:
            genre_tags.extend(['ballad', 'ambient', 'downtempo'])
        elif 90 <= tempo <= 120:
            genre_tags.extend(['pop', 'rock', 'indie'])
        elif 120 <= tempo <= 140:
            genre_tags.extend(['dance', 'house', 'electronic'])
        elif tempo > 140:
            genre_tags.extend(['techno', 'drum_and_bass', 'hardcore'])
        
        # YAMNet-based genre hints
        for class_name, confidence in yamnet_classes:
            if confidence > 0.2:
                class_lower = class_name.lower()
                if 'electronic' in class_lower:
                    genre_tags.append('electronic')
                elif 'rock' in class_lower:
                    genre_tags.append('rock')
                elif 'jazz' in class_lower:
                    genre_tags.append('jazz')
                elif 'classical' in class_lower:
                    genre_tags.append('classical')
        
        return list(set(genre_tags))[:4]  # Remove duplicates, limit to 4
    
    def _extract_mood_tags(self, valence: float, energy: float, 
                          features: Dict[str, Any]) -> List[str]:
        """Extract mood-related tags"""
        mood_tags = []
        
        if energy > 0.7:
            mood_tags.extend(['energetic', 'powerful', 'intense'])
        elif energy < 0.3:
            mood_tags.extend(['calm', 'peaceful', 'relaxed'])
        
        if valence > 0.7:
            mood_tags.extend(['happy', 'uplifting', 'positive'])
        elif valence < 0.3:
            mood_tags.extend(['dark', 'melancholic', 'mysterious'])
        
        # Spectral-based mood tags
        if features.get('spectral_centroid', 1000) > 3000:
            mood_tags.append('bright')
        elif features.get('spectral_centroid', 1000) < 1500:
            mood_tags.append('warm')
        
        return list(set(mood_tags))[:4]
    
    def _extract_style_tags(self, features: Dict[str, Any], tempo: float) -> List[str]:
        """Extract style-related tags"""
        style_tags = []
        
        # Zero crossing rate indicates percussiveness
        if features.get('zcr', 0) > 0.1:
            style_tags.append('percussive')
        elif features.get('zcr', 0) < 0.02:
            style_tags.append('smooth')
        
        # Spectral rolloff indicates brightness
        if features.get('spectral_rolloff', 5000) > 8000:
            style_tags.append('crisp')
        elif features.get('spectral_rolloff', 5000) < 3000:
            style_tags.append('mellow')
        
        # Tempo-based style
        if tempo > 140:
            style_tags.append('fast')
        elif tempo < 80:
            style_tags.append('slow')
        
        return style_tags[:3]
    
    def _estimate_time_signature(self, beats: np.ndarray, sr: int) -> Optional[str]:
        """Estimate time signature from beat tracking"""
        try:
            # Simple heuristic: most common music is in 4/4
            # Could be enhanced with more sophisticated analysis
            return "4/4"
        except:
            return None
    
    def _generate_description(self, track_type: TrackType, category: str,
                            vibe: VibeCategory, tempo: float, key: Optional[str],
                            instruments: List[str]) -> str:
        """Generate an automatic description"""
        
        tempo_desc = "slow" if tempo < 90 else "moderate" if tempo < 130 else "fast"
        
        base_desc = f"A {vibe.value} {track_type.value} sample"
        
        if category != 'other':
            base_desc += f" featuring {category}"
        
        if instruments:
            base_desc += f" with {', '.join(instruments[:2])}"
        
        base_desc += f" at a {tempo_desc} tempo ({int(tempo)} BPM)"
        
        if key:
            base_desc += f" in {key}"
        
        return base_desc + "."
    
    def _create_fallback_result(self, file_path: str) -> AudioAnalysisResult:
        """Create a minimal analysis result when full analysis fails"""
        try:
            y, sr = librosa.load(file_path)
            duration = librosa.get_duration(y=y, sr=sr)
            tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        except:
            duration = 0.0
            tempo = 120.0
        
        return AudioAnalysisResult(
            duration=duration,
            tempo=tempo,
            key=None,
            time_signature=None,
            track_type=TrackType.UNKNOWN,
            primary_category='other',
            secondary_categories=[],
            vibe=VibeCategory.CHILL,
            energy_level=0.5,
            valence=0.5,
            danceability=0.5,
            instrument_tags=[],
            genre_tags=[],
            mood_tags=[],
            style_tags=[],
            spectral_centroid_mean=2000.0,
            spectral_rolloff_mean=5000.0,
            mfcc_features=[0.0] * 13,
            zero_crossing_rate=0.05,
            yamnet_top_classes=[],
            auto_description="Audio sample analysis incomplete."
        )

# Global analyzer instance
_analyzer_instance = None

def get_analyzer() -> AdvancedAudioAnalyzer:
    """Get or create the global analyzer instance"""
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = AdvancedAudioAnalyzer()
    return _analyzer_instance

def analyze_sample(file_path: str) -> AudioAnalysisResult:
    """Convenience function to analyze a sample"""
    analyzer = get_analyzer()
    return analyzer.analyze_audio_file(file_path)
