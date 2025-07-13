"""
Neural Training Module
Handles the neural network training components for DiffSinger
"""

import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
import librosa
import logging
from typing import Dict, List, Any, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


class VoiceModel(nn.Module):
    """Simple neural voice model for voice cloning"""
    
    def __init__(self, mel_bins: int, hidden_size: int, num_layers: int, dropout: float):
        super().__init__()
        self.mel_bins = mel_bins
        self.hidden_size = hidden_size
        
        # Encoder
        self.encoder = nn.Sequential(
            nn.Linear(mel_bins, hidden_size),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size, hidden_size),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size, hidden_size // 2),
            nn.ReLU()
        )
        
        # Decoder
        self.decoder = nn.Sequential(
            nn.Linear(hidden_size // 2, hidden_size),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size, hidden_size),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size, mel_bins),
            nn.Tanh()
        )
        
    def forward(self, x):
        encoded = self.encoder(x)
        decoded = self.decoder(encoded)
        return decoded


class AudioPreprocessor:
    """Handles audio preprocessing for training"""
    
    def __init__(self, sample_rate: int = 22050, hop_size: int = 256, 
                 win_size: int = 1024, mel_bins: int = 80):
        self.sample_rate = sample_rate
        self.hop_size = hop_size
        self.win_size = win_size
        self.mel_bins = mel_bins
    
    def preprocess_audio_files(self, audio_files: List[str]) -> List[Dict[str, Any]]:
        """Preprocess audio files for training"""
        processed_data = []
        
        for audio_file in audio_files:
            try:
                # Load audio
                audio, sr = librosa.load(audio_file, sr=self.sample_rate)
                
                # Extract mel spectrogram
                mel_spec = librosa.feature.melspectrogram(
                    y=audio, 
                    sr=sr, 
                    n_mels=self.mel_bins,
                    hop_length=self.hop_size,
                    win_length=self.win_size,
                    fmax=sr//2
                )
                
                # Convert to log scale
                log_mel = librosa.power_to_db(mel_spec, ref=np.max)
                
                # Normalize
                log_mel = (log_mel - log_mel.mean()) / (log_mel.std() + 1e-8)
                
                processed_data.append({
                    'audio': audio,
                    'mel_spec': log_mel,
                    'file_path': audio_file
                })
                
            except Exception as e:
                logger.warning(f"Failed to process audio file {audio_file}: {e}")
                continue
        
        logger.info(f"Processed {len(processed_data)} audio files")
        return processed_data
    
    def create_training_batches(self, processed_data: List[Dict[str, Any]], 
                               batch_size: int) -> List[Tuple[np.ndarray, np.ndarray]]:
        """Create training batches from processed data"""
        # Collect all mel spectrograms
        all_mels = []
        for data in processed_data:
            mel_spec = data['mel_spec']
            # Split spectrogram into frames
            for i in range(0, mel_spec.shape[1] - 1, 10):  # Step by 10 frames
                if i + 10 < mel_spec.shape[1]:
                    frame = mel_spec[:, i:i+10].flatten()
                    all_mels.append(frame)
        
        if not all_mels:
            return []
        
        # Convert to numpy array
        all_mels = np.array(all_mels)
        
        # Create batches
        batches = []
        num_samples = len(all_mels)
        for i in range(0, num_samples, batch_size):
            batch_end = min(i + batch_size, num_samples)
            batch_inputs = all_mels[i:batch_end]
            batch_targets = batch_inputs.copy()  # Autoencoder targets
            
            batches.append((batch_inputs, batch_targets))
        
        return batches


class NeuralTrainer:
    """Handles neural network training"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.preprocessor = AudioPreprocessor(
            sample_rate=config.get('audio', {}).get('sample_rate', 22050),
            hop_size=config.get('audio', {}).get('hop_size', 256),
            win_size=config.get('audio', {}).get('win_size', 1024),
            mel_bins=config.get('audio', {}).get('mel_bins', 80)
        )
    
    def train_voice_model(self, voice_name: str, audio_files: List[str], 
                         output_dir: Path, progress_callback=None) -> Dict[str, Any]:
        """Train a voice model using neural networks"""
        logger.info(f"Starting neural training for voice: {voice_name}")
        
        # Validate audio files first
        valid_audio_files = self._validate_audio_quality(audio_files)
        if not valid_audio_files:
            raise ValueError("No valid audio files found for training")
        
        if len(valid_audio_files) < len(audio_files):
            logger.warning(f"Using {len(valid_audio_files)} out of {len(audio_files)} audio files")
        
        # Training parameters
        mel_bins = self.config.get('audio', {}).get('mel_bins', 80)
        epochs = self.config.get('training', {}).get('epochs', 100)
        batch_size = self.config.get('training', {}).get('batch_size', 8)
        learning_rate = self.config.get('training', {}).get('learning_rate', 0.0001)
        
        # Preprocess audio data
        logger.info("Preprocessing audio data...")
        if progress_callback:
            progress_callback(10)
        
        processed_data = self.preprocessor.preprocess_audio_files(valid_audio_files)
        
        if not processed_data:
            raise ValueError("No audio data could be processed")
        
        if progress_callback:
            progress_callback(20)
        
        # Create model
        logger.info("Creating voice model...")
        model = VoiceModel(
            mel_bins=mel_bins * 10,  # 10 frames flattened
            hidden_size=self.config.get('model', {}).get('hidden_size', 256),
            num_layers=self.config.get('model', {}).get('num_layers', 4),
            dropout=self.config.get('model', {}).get('dropout', 0.1)
        )
        
        # Setup training
        optimizer = optim.Adam(model.parameters(), lr=learning_rate)
        criterion = nn.MSELoss()
        
        # Create training batches
        training_batches = self.preprocessor.create_training_batches(processed_data, batch_size)
        
        if not training_batches:
            raise ValueError("No training batches could be created")
        
        if progress_callback:
            progress_callback(30)
        
        # Training loop
        logger.info(f"Starting training for {epochs} epochs...")
        training_losses = []
        best_loss = float('inf')
        
        for epoch in range(epochs):
            epoch_loss = 0.0
            num_batches = 0
            
            for batch_inputs, batch_targets in training_batches:
                model.train()
                optimizer.zero_grad()
                
                # Forward pass
                inputs = torch.FloatTensor(batch_inputs)
                targets = torch.FloatTensor(batch_targets)
                
                outputs = model(inputs)
                loss = criterion(outputs, targets)
                
                # Backward pass
                loss.backward()
                optimizer.step()
                
                epoch_loss += loss.item()
                num_batches += 1
            
            avg_loss = epoch_loss / max(num_batches, 1)
            training_losses.append(avg_loss)
            
            # Track best model
            if avg_loss < best_loss:
                best_loss = avg_loss
                # Save best model checkpoint
                best_model_path = output_dir / 'best_model.ckpt'
                torch.save({
                    'model_state_dict': model.state_dict(),
                    'optimizer_state_dict': optimizer.state_dict(),
                    'epoch': epoch,
                    'loss': avg_loss,
                    'config': self.config
                }, best_model_path)
            
            # Update progress
            if progress_callback:
                training_progress = 30 + int((epoch / epochs) * 60)  # 30% to 90%
                progress_callback(training_progress)
            
            if epoch % 10 == 0:
                logger.info(f"Epoch {epoch}/{epochs}, Loss: {avg_loss:.6f}, Best: {best_loss:.6f}")
        
        # Save final model
        if progress_callback:
            progress_callback(95)
        
        model_path = output_dir / 'model.ckpt'
        torch.save({
            'model_state_dict': model.state_dict(),
            'optimizer_state_dict': optimizer.state_dict(),
            'config': self.config,
            'training_losses': training_losses,
            'voice_name': voice_name,
            'sample_rate': self.preprocessor.sample_rate,
            'mel_bins': mel_bins,
            'best_loss': best_loss
        }, model_path)
        
        logger.info(f"Model training completed. Final loss: {training_losses[-1]:.6f}, Best loss: {best_loss:.6f}")
        logger.info(f"Model saved to: {model_path}")
        
        if progress_callback:
            progress_callback(100)
        
        return {
            'model_path': str(model_path),
            'training_losses': training_losses,
            'final_loss': training_losses[-1] if training_losses else 0.0,
            'best_loss': best_loss,
            'epochs_trained': epochs,
            'audio_files_used': len(valid_audio_files)
        }
    
    def _validate_audio_quality(self, audio_files: List[str]) -> List[str]:
        """Validate audio quality and filter out poor quality files"""
        valid_files = []
        
        for audio_file in audio_files:
            try:
                # Load audio for analysis
                audio, sr = librosa.load(audio_file, sr=22050)
                
                # Check duration (minimum 1 second)
                if len(audio) < sr:
                    logger.warning(f"Audio file too short: {audio_file}")
                    continue
                
                # Check for silence
                rms = librosa.feature.rms(y=audio)[0]
                if np.mean(rms) < 0.001:  # Very quiet
                    logger.warning(f"Audio file too quiet: {audio_file}")
                    continue
                
                # Check for clipping
                if np.max(np.abs(audio)) > 0.99:
                    logger.warning(f"Audio file may be clipped: {audio_file}")
                    # Still use it but warn
                
                valid_files.append(audio_file)
                
            except Exception as e:
                logger.warning(f"Failed to validate audio file {audio_file}: {e}")
                continue
        
        logger.info(f"Validated {len(valid_files)} out of {len(audio_files)} audio files")
        return valid_files
