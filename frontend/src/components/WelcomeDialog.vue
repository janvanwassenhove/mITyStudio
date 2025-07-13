<template>
  <div v-if="showDialog" class="welcome-overlay">
    <div class="welcome-dialog">
      <div class="welcome-header">
        <h2>🎵 Welcome to mITyStudio</h2>
        <p>Your browser-based DAW for music creation</p>
      </div>
      
      <div class="welcome-content">
        <div class="audio-status">
          <div v-if="audioStatus === 'pending'" class="status-item">
            <span class="status-icon">🔊</span>
            <span>Audio system ready to initialize</span>
          </div>
          <div v-else-if="audioStatus === 'initializing'" class="status-item">
            <span class="status-icon loading">⏳</span>
            <span>Initializing audio system...</span>
          </div>
          <div v-else-if="audioStatus === 'success'" class="status-item success">
            <span class="status-icon">✅</span>
            <span>Audio system ready! 🎵 Playing welcome tune...</span>
          </div>
          <div v-else-if="audioStatus === 'error'" class="status-item error">
            <span class="status-icon">❌</span>
            <span>Audio initialization failed. Please try again.</span>
          </div>
        </div>

        <div class="welcome-actions">
          <button 
            v-if="audioStatus === 'pending'" 
            @click="initializeAudio" 
            class="primary-button"
          >
            🚀 Start Music Creation
          </button>
          
          <button 
            v-else-if="audioStatus === 'error'" 
            @click="initializeAudio" 
            class="retry-button"
          >
            🔄 Retry Audio Setup
          </button>
          
          <button 
            v-else-if="audioStatus === 'success'" 
            @click="closeDialog" 
            class="success-button"
          >
            🎶 Let's Create Music!
          </button>
          
          <button 
            v-else-if="audioStatus === 'initializing'" 
            disabled
            class="loading-button"
          >
            ⏳ Initializing Audio...
          </button>
        </div>

        <div v-if="audioStatus === 'error'" class="error-help">
          <p>💡 <strong>Troubleshooting tips:</strong></p>
          <ul>
            <li>Make sure your browser allows audio</li>
            <li>Check that your device is not muted</li>
            <li>Try refreshing the page and clicking again</li>
            <li>Some browsers require multiple clicks to start audio</li>
          </ul>
        </div>

        <div class="welcome-info">
          <p>🎹 Create tracks with samples and synthesizers</p>
          <p>🎵 Seamless audio playback with moving playhead</p>
          <p>🎛️ Professional DAW features in your browser</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useAudioStore } from '../stores/audioStore'

const audioStore = useAudioStore()

// Show dialog if audio is not initialized (manual control for dismissal)
const showDialog = ref(!audioStore.isInitialized)
const audioStatus = ref<'pending' | 'initializing' | 'success' | 'error'>('pending')

// Watch for audio becoming uninitialized (e.g., after page refresh or context loss)
watch(() => audioStore.isInitialized, (isInitialized) => {
  if (isInitialized) {
    audioStatus.value = 'success'
    // Auto-close after showing success
    setTimeout(() => {
      closeDialog()
    }, 1500)
  } else {
    // Audio became uninitialized, show dialog again
    showDialog.value = true
    audioStatus.value = 'pending'
  }
})

// Watch for audio store initialization errors
watch(() => audioStore.initializationError, (error) => {
  if (error && audioStatus.value === 'initializing') {
    audioStatus.value = 'error'
  }
})

// Reset status when audio store error clears (for retry scenarios)
watch(() => audioStore.initializationError, (error) => {
  if (!error && audioStatus.value === 'error') {
    audioStatus.value = 'pending'
  }
})

const initializeAudio = async () => {
  // Prevent multiple simultaneous initialization attempts
  if (audioStatus.value === 'initializing') {
    console.log('🎵 Welcome Dialog: Initialization already in progress, ignoring click')
    return
  }
  
  audioStatus.value = 'initializing'
  
  try {
    // Use the same retry logic as the retry button
    const maxRetries = 5
    const retryDelay = 800
    let attempt = 0
    
    while (attempt < maxRetries && !audioStore.isInitialized) {
      try {
        console.log(`🎵 Welcome Dialog: Audio initialization attempt ${attempt + 1}/${maxRetries}`)
        await audioStore.forceInitialize()
        
        if (audioStore.isInitialized) {
          console.log('✅ Welcome Dialog: Audio initialized successfully')
          audioStatus.value = 'success'
          
          // Play a welcoming tune to celebrate successful initialization
          await playWelcomeTune()
          
          // Auto-close after showing success and playing tune
          setTimeout(() => {
            closeDialog()
          }, 3200) // Extended to allow tune + reverb tail to finish
          return
        }
      } catch (error) {
        console.warn(`Welcome Dialog: Attempt ${attempt + 1} failed:`, error)
      }
      
      attempt++
      if (!audioStore.isInitialized && attempt < maxRetries) {
        await new Promise(resolve => setTimeout(resolve, retryDelay))
      }
    }
    
    // If we get here, all retries failed
    console.error('❌ Welcome Dialog: Audio initialization failed after all retries')
    audioStatus.value = 'error'
    
  } catch (error) {
    console.error('Failed to initialize audio from welcome dialog:', error)
    audioStatus.value = 'error'
  }
}

const closeDialog = () => {
  showDialog.value = false
}

// Play a welcoming tune when audio is successfully initialized
const playWelcomeTune = async () => {
  try {
    console.log('🎵 Playing welcome tune...')
    
    // Import Tone.js dynamically to ensure it's available
    const Tone = (window as any).Tone
    if (!Tone) {
      console.warn('Tone.js not available for welcome tune')
      return
    }

    // Create a warm, professional welcome melody with reverb
    const reverb = new Tone.Reverb({
      decay: 1.5,
      preDelay: 0.01
    }).toDestination()

    const synth = new Tone.PolySynth(Tone.Synth, {
      oscillator: {
        type: "triangle"
      },
      envelope: {
        attack: 0.1,
        decay: 0.3,
        sustain: 0.4,
        release: 0.8
      }
    }).connect(reverb)

    // Set a pleasant volume
    synth.volume.value = -15 // Slightly softer with reverb

    // Beautiful chord progression: C Major -> F Major -> G Major -> C Major (I-IV-V-I)
    const chords = [
      ['C4', 'E4', 'G4'],     // C Major
      ['F4', 'A4', 'C5'],     // F Major  
      ['G4', 'B4', 'D5'],     // G Major
      ['C4', 'E4', 'G4']      // C Major (return home)
    ]

    const now = Tone.now()
    const chordDuration = 0.4  // Each chord plays for 400ms
    const gap = 0.05           // Small gap between chords

    // Schedule the chord progression
    chords.forEach((chord, index) => {
      const time = now + (index * (chordDuration + gap))
      synth.triggerAttackRelease(chord, chordDuration, time)
    })

    // Add a gentle melodic flourish at the end
    const melody = ['C5', 'D5', 'E5', 'G5']
    const melodyStart = now + (chords.length * (chordDuration + gap)) + 0.1
    
    melody.forEach((note, index) => {
      const time = melodyStart + (index * 0.15)
      synth.triggerAttackRelease(note, 0.2, time)
    })

    // Clean up after the tune finishes
    setTimeout(() => {
      synth.dispose()
      reverb.dispose()
      console.log('✅ Welcome tune completed')
    }, 3000) // Extended slightly for reverb tail

  } catch (error) {
    console.warn('Could not play welcome tune:', error)
  }
}

// If audio is already initialized (shouldn't happen on fresh start, but just in case)
if (audioStore.isInitialized) {
  audioStatus.value = 'success'
  setTimeout(() => {
    closeDialog()
  }, 500)
}
</script>

<style scoped>
.welcome-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.8);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10000;
  animation: fadeIn 0.3s ease-out;
}

.welcome-dialog {
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  border-radius: 20px;
  padding: 40px;
  max-width: 500px;
  width: 90%;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
  border: 1px solid rgba(255, 255, 255, 0.1);
  animation: slideUp 0.4s ease-out;
}

.welcome-header {
  text-align: center;
  margin-bottom: 30px;
}

.welcome-header h2 {
  color: #ffffff;
  font-size: 2rem;
  font-weight: 600;
  margin: 0 0 10px 0;
  background: linear-gradient(45deg, #64b5f6, #42a5f5);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.welcome-header p {
  color: #b0bec5;
  font-size: 1.1rem;
  margin: 0;
}

.welcome-content {
  display: flex;
  flex-direction: column;
  gap: 25px;
}

.audio-status {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 12px;
  padding: 20px;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.status-item {
  display: flex;
  align-items: center;
  gap: 12px;
  color: #ffffff;
  font-size: 1rem;
}

.status-item.success {
  color: #4caf50;
}

.status-item.error {
  color: #f44336;
}

.status-icon {
  font-size: 1.2rem;
  width: 24px;
  display: flex;
  justify-content: center;
}

.status-icon.loading {
  animation: spin 1s linear infinite;
}

.welcome-actions {
  display: flex;
  justify-content: center;
}

.primary-button, .retry-button, .success-button, .loading-button {
  padding: 15px 30px;
  border: none;
  border-radius: 12px;
  font-size: 1.1rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
  min-width: 200px;
}

.loading-button {
  background: linear-gradient(45deg, #9e9e9e, #757575);
  color: white;
  cursor: not-allowed;
  opacity: 0.7;
}

.primary-button {
  background: linear-gradient(45deg, #2196f3, #1976d2);
  color: white;
}

.primary-button:hover {
  background: linear-gradient(45deg, #1976d2, #1565c0);
  transform: translateY(-2px);
  box-shadow: 0 8px 25px rgba(33, 150, 243, 0.3);
}

.retry-button {
  background: linear-gradient(45deg, #ff9800, #f57c00);
  color: white;
}

.retry-button:hover {
  background: linear-gradient(45deg, #f57c00, #ef6c00);
  transform: translateY(-2px);
  box-shadow: 0 8px 25px rgba(255, 152, 0, 0.3);
}

.success-button {
  background: linear-gradient(45deg, #4caf50, #388e3c);
  color: white;
}

.success-button:hover {
  background: linear-gradient(45deg, #388e3c, #2e7d32);
  transform: translateY(-2px);
  box-shadow: 0 8px 25px rgba(76, 175, 80, 0.3);
}

.welcome-info {
  text-align: center;
  color: #90a4ae;
  font-size: 0.95rem;
  line-height: 1.6;
}

.welcome-info p {
  margin: 8px 0;
}

.error-help {
  background: rgba(244, 67, 54, 0.1);
  border: 1px solid rgba(244, 67, 54, 0.3);
  border-radius: 8px;
  padding: 15px;
  margin-top: 20px;
}

.error-help p {
  margin: 0 0 10px 0;
  color: #ffcdd2;
}

.error-help ul {
  margin: 0;
  padding-left: 20px;
  color: #ffcdd2;
}

.error-help li {
  margin: 5px 0;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(30px) scale(0.95);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>
