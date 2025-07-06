<template>
  <div class="playback-controls">
    <div class="transport-controls">
      <button 
        class="btn btn-primary transport-btn"
        @click="togglePlayback"
        :class="{ playing: audioStore.isPlaying }"
        :disabled="audioStore.initializationError !== null"
      >
        <Play v-if="!audioStore.isPlaying" class="icon" />
        <Pause v-else class="icon" />
        {{ audioStore.isPlaying ? $t('playback.pause') : $t('playback.play') }}
      </button>
      
      <button 
        class="btn btn-secondary transport-btn" 
        @click="audioStore.stop"
        :disabled="!audioStore.isInitialized"
      >
        <Square class="icon" />
        {{ $t('playback.stop') }}
      </button>
      
      <button 
        class="btn btn-ghost transport-btn"
        @click="audioStore.toggleLoop"
        :class="{ active: audioStore.isLooping }"
        :disabled="!audioStore.isInitialized"
      >
        <RotateCcw class="icon" />
        {{ $t('playback.loop') }}
      </button>
      
      <button 
        class="btn btn-ghost transport-btn"
        @click="audioStore.toggleMetronome"
        :class="{ active: audioStore.metronomeEnabled }"
        :disabled="!audioStore.isInitialized"
      >
        <Clock class="icon" />
        {{ $t('playback.metronome') }}
      </button>

      <button 
        class="btn btn-accent transport-btn"
        @click="generateSong"
        :disabled="!audioStore.isInitialized || audioStore.totalTracks === 0"
      >
        <Music class="icon" />
        Generate Song
      </button>

      <button 
        class="btn btn-secondary transport-btn"
        @click="generateChordDemo"
        :disabled="!audioStore.isInitialized"
      >
        <Music2 class="icon" />
        Chord Demo
      </button>

      <!-- Manual Initialize Button -->
      <button 
        v-if="!audioStore.isInitialized && !audioStore.initializationError"
        class="btn btn-warning transport-btn"
        @click="handleInitialize"
        :disabled="audioStore.isInitializing"
        :class="{ loading: audioStore.isInitializing }"
      >
        <Volume2 v-if="!audioStore.isInitializing" class="icon" />
        <RefreshCw v-else class="icon spinning" />
        {{ audioStore.isInitializing ? 'Initializing...' : 'Initialize Audio' }}
      </button>

      <!-- Retry Button for Errors -->
      <button 
        v-if="audioStore.initializationError"
        class="btn btn-error transport-btn"
        @click="handleRetry"
        :disabled="audioStore.isInitializing"
      >
        <RefreshCw class="icon" />
        Retry Audio
      </button>

      <!-- Reset Button for Debugging -->
      <button 
        v-if="audioStore.initializationError"
        class="btn btn-ghost transport-btn"
        @click="handleReset"
        title="Reset audio system"
      >
        <RotateCcw class="icon" />
        Reset
      </button>
    </div>
    
    <div class="song-info">
      <div class="info-item">
        <span class="info-label">Key:</span>
        <select 
          v-model="songKey" 
          @change="updateKey"
          class="key-select"
          :disabled="!audioStore.isInitialized"
        >
          <option value="C">C Major</option>
          <option value="G">G Major</option>
          <option value="F">F Major</option>
          <option value="Am">A Minor</option>
          <option value="Em">E Minor</option>
          <option value="Dm">D Minor</option>
        </select>
      </div>
      
      <div class="info-item">
        <span class="info-label">Clips:</span>
        <span class="info-value">{{ totalClips }}</span>
      </div>
    </div>
    
    <div class="tempo-control">
      <label class="control-label">{{ $t('playback.tempo') }}</label>
      <div class="tempo-input-group">
        <input
          type="number"
          v-model.number="tempo"
          @change="updateTempo"
          min="60"
          max="200"
          class="input tempo-input"
          :disabled="!audioStore.isInitialized"
        />
        <span class="tempo-unit">BPM</span>
      </div>
    </div>
    
    <div class="volume-control">
      <label class="control-label">{{ $t('playback.volume') }}</label>
      <div class="volume-slider-group">
        <Volume2 class="volume-icon" />
        <input
          type="range"
          v-model.number="masterVolume"
          @input="updateMasterVolume"
          min="0"
          max="1"
          step="0.01"
          class="volume-slider"
          :disabled="!audioStore.isInitialized"
        />
        <span class="volume-value">{{ Math.round(masterVolume * 100) }}%</span>
      </div>
    </div>
    
    <div class="zoom-control">
      <label class="control-label">Zoom</label>
      <div class="zoom-buttons">
        <button class="btn btn-ghost zoom-btn" @click="zoomOut">
          <ZoomOut class="icon" />
        </button>
        <span class="zoom-value">{{ Math.round(audioStore.zoom * 100) }}%</span>
        <button class="btn btn-ghost zoom-btn" @click="zoomIn">
          <ZoomIn class="icon" />
        </button>
      </div>
    </div>

    <!-- Enhanced Audio Status Indicator -->
    <div class="audio-status">
      <div 
        class="status-indicator"
        :class="{ 
          active: audioStore.isInitialized,
          loading: audioStore.isInitializing,
          error: audioStore.initializationError !== null
        }"
      >
        <div class="status-dot"></div>
        <span class="status-text">
          {{ getStatusText() }}
        </span>
      </div>
      
      <!-- Error Details -->
      <div v-if="audioStore.initializationError" class="error-details">
        <small>{{ audioStore.initializationError }}</small>
      </div>

      <!-- Debug Info -->
      <div v-if="showDebugInfo" class="debug-info">
        <small>
          Context: {{ audioContextState }} | 
          Initialized: {{ audioStore.isInitialized ? 'true' : 'false' }} |
          Initializing: {{ audioStore.isInitializing ? 'true' : 'false' }}
        </small>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed, onMounted, onUnmounted } from 'vue'
import { useAudioStore } from '../stores/audioStore'
import { 
  Play, 
  Pause, 
  Square, 
  RotateCcw, 
  Clock, 
  Volume2, 
  ZoomIn, 
  ZoomOut,
  Music,
  Music2,
  RefreshCw
} from 'lucide-vue-next'
import * as Tone from 'tone'

const audioStore = useAudioStore()

const tempo = ref(audioStore.songStructure.tempo)
const masterVolume = ref(audioStore.masterVolume)
const songKey = ref(audioStore.songStructure.key)
const showDebugInfo = ref(true) // Always show for debugging
const audioContextState = ref('unknown')

let contextCheckInterval: number | null = null

const totalClips = computed(() => {
  return audioStore.songStructure.tracks.reduce((total, track) => total + track.clips.length, 0)
})

const getStatusText = () => {
  if (audioStore.initializationError) {
    return 'Audio Error'
  }
  if (audioStore.isInitializing) {
    return 'Initializing...'
  }
  if (audioStore.isInitialized) {
    return 'Audio Ready'
  }
  return 'Click to Initialize'
}

// Check audio context state periodically
onMounted(() => {
  console.log('🔍 PlaybackControls mounted, starting audio context monitoring')
  
  const checkAudioContext = () => {
    try {
      if (Tone && Tone.context) {
        const state = Tone.context.state
        audioContextState.value = state
        console.log('🎵 Audio context state:', state)
      } else {
        audioContextState.value = 'not-available'
        console.log('⚠️ Tone.js not available')
      }
    } catch (error) {
      audioContextState.value = 'error'
      console.error('❌ Error checking audio context:', error)
    }
  }
  
  // Initial check
  checkAudioContext()
  
  // Set up interval
  contextCheckInterval = setInterval(checkAudioContext, 2000)
  
  console.log('🔍 Debug info enabled, monitoring store state:')
  console.log('- isInitialized:', audioStore.isInitialized)
  console.log('- isInitializing:', audioStore.isInitializing)
  console.log('- initializationError:', audioStore.initializationError)
})

onUnmounted(() => {
  if (contextCheckInterval) {
    clearInterval(contextCheckInterval)
    contextCheckInterval = null
  }
})

watch(() => audioStore.songStructure.tempo, (newTempo) => {
  tempo.value = newTempo
})

watch(() => audioStore.masterVolume, (newVolume) => {
  masterVolume.value = newVolume
})

watch(() => audioStore.songStructure.key, (newKey) => {
  songKey.value = newKey
})

// Watch store state changes for debugging
watch(() => audioStore.isInitialized, (newValue) => {
  console.log('🔍 Store isInitialized changed to:', newValue)
})

watch(() => audioStore.isInitializing, (newValue) => {
  console.log('🔍 Store isInitializing changed to:', newValue)
})

watch(() => audioStore.initializationError, (newValue) => {
  console.log('🔍 Store initializationError changed to:', newValue)
})

const MAX_INIT_RETRIES = 5
const RETRY_DELAY_MS = 800

async function retryInitializeAudio(maxRetries = MAX_INIT_RETRIES) {
  let attempt = 0
  while (attempt < maxRetries && !audioStore.isInitialized) {
    try {
      await audioStore.forceInitialize()
      if (audioStore.isInitialized) {
        console.log('✅ Audio initialized on attempt', attempt + 1)
        return true
      }
    } catch (error) {
      console.warn(`Attempt ${attempt + 1} failed:`, error)
    }
    attempt++
    if (!audioStore.isInitialized) {
      await new Promise(res => setTimeout(res, RETRY_DELAY_MS))
    }
  }
  return audioStore.isInitialized
}

const handleInitialize = async () => {
  console.log('🎵 Initialize button clicked')
  console.log('🔍 Current store state before init:')
  console.log('- isInitialized:', audioStore.isInitialized)
  console.log('- isInitializing:', audioStore.isInitializing)
  console.log('- initializationError:', audioStore.initializationError)

  try {
    const success = await retryInitializeAudio()
    if (success) {
      console.log('✅ Initialize completed')
    } else {
      console.error('❌ Initialize failed after retries')
    }
    console.log('🔍 Store state after init:')
    console.log('- isInitialized:', audioStore.isInitialized)
    console.log('- isInitializing:', audioStore.isInitializing)
    console.log('- initializationError:', audioStore.initializationError)
  } catch (error) {
    console.error('❌ Initialize failed:', error)
  }
}

const handleRetry = async () => {
  console.log('🔄 Retry button clicked')
  try {
    const success = await retryInitializeAudio()
    if (success) {
      console.log('✅ Retry completed')
    } else {
      console.error('❌ Retry failed after retries')
    }
  } catch (error) {
    console.error('❌ Retry failed:', error)
  }
}

const handleReset = () => {
  console.log('🔄 Reset button clicked')
  audioStore.resetAudio()
}

const togglePlayback = async () => {
  if (audioStore.isPlaying) {
    audioStore.pause()
  } else {
    await audioStore.play()
  }
}

const generateSong = () => {
  audioStore.generateAndScheduleSong()
}

const generateChordDemo = async () => {
  // Create a demo track with chord progression if none exists
  if (audioStore.totalTracks === 0) {
    // Add a piano track for demo
    const trackId = audioStore.addTrack('Demo Piano', 'piano')
    if (trackId) {
      // Enable looping for better demo experience
      audioStore.isLooping = true
      // Generate a I-V-vi-IV progression
      await audioStore.generateChordProgression(trackId, 'I-V-vi-IV', 0, 2, 1)
      console.log('Demo chord progression created!')
    }
  } else {
    // Generate chords for the first track
    const firstTrack = audioStore.songStructure.tracks[0]
    if (firstTrack) {
      // Enable looping for better demo experience
      audioStore.isLooping = true
      await audioStore.generateChordProgression(firstTrack.id, 'I-V-vi-IV', 0, 2, 1)
      console.log('Chord progression added to existing track!')
    }
  }
}

const updateTempo = () => {
  audioStore.setTempo(tempo.value)
}

const updateMasterVolume = () => {
  audioStore.setMasterVolume(masterVolume.value)
}

const updateKey = () => {
  audioStore.songStructure.key = songKey.value
  audioStore.updateSongStructure()
  
  // Regenerate notes for all clips with new key
  audioStore.songStructure.tracks.forEach(track => {
    track.clips.forEach(clip => {
      audioStore.updateClip(track.id, clip.id, { instrument: clip.instrument })
    })
  })
}

const zoomIn = () => {
  audioStore.setZoom(audioStore.zoom * 1.2)
}

const zoomOut = () => {
  audioStore.setZoom(audioStore.zoom / 1.2)
}
</script>

<style scoped>
.playback-controls {
  display: flex;
  align-items: center;
  gap: 2rem;
  padding: 1rem 1.5rem;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  flex-wrap: wrap;
}

.transport-controls {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.transport-btn {
  min-width: auto;
  padding: 0.75rem 1rem;
  transition: all 0.2s ease;
}

.transport-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.transport-btn.loading {
  background: var(--warning);
  color: white;
}

.transport-btn.playing {
  background: var(--gradient-accent);
  color: white;
  box-shadow: 0 0 20px rgba(244, 114, 182, 0.3);
}

.transport-btn.active {
  background: var(--primary);
  color: white;
}

.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.song-info {
  display: flex;
  gap: 1rem;
  align-items: center;
}

.info-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.info-label {
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.info-value {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--primary);
}

.key-select {
  padding: 0.25rem 0.5rem;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: var(--background);
  color: var(--text);
  font-size: 0.875rem;
}

.key-select:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.tempo-control,
.volume-control,
.zoom-control {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  min-width: 120px;
}

.control-label {
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.tempo-input-group {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.tempo-input {
  width: 70px;
  padding: 0.5rem;
  text-align: center;
}

.tempo-input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.tempo-unit {
  font-size: 0.8125rem;
  color: var(--text-secondary);
  font-weight: 500;
}

.volume-slider-group {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.volume-icon {
  width: 16px;
  height: 16px;
  color: var(--text-secondary);
  flex-shrink: 0;
}

.volume-slider {
  flex: 1;
  height: 4px;
  background: var(--border);
  border-radius: 2px;
  outline: none;
  cursor: pointer;
  -webkit-appearance: none;
}

.volume-slider:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.volume-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 16px;
  height: 16px;
  background: var(--primary);
  border-radius: 50%;
  cursor: pointer;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

.volume-slider::-moz-range-thumb {
  width: 16px;
  height: 16px;
  background: var(--primary);
  border-radius: 50%;
  cursor: pointer;
  border: none;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

.volume-value {
  font-size: 0.8125rem;
  color: var(--text-secondary);
  font-weight: 500;
  min-width: 35px;
  text-align: right;
}

.zoom-buttons {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.zoom-btn {
  padding: 0.5rem;
  min-width: auto;
}

.zoom-value {
  font-size: 0.8125rem;
  color: var(--text);
  font-weight: 500;
  min-width: 45px;
  text-align: center;
}

.audio-status {
  margin-left: auto;
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  border-radius: 20px;
  background: var(--background);
  border: 1px solid var(--border);
}

.status-indicator.active {
  border-color: var(--success);
  background: rgba(16, 185, 129, 0.1);
}

.status-indicator.loading {
  border-color: var(--warning);
  background: rgba(245, 158, 11, 0.1);
}

.status-indicator.error {
  border-color: var(--error);
  background: rgba(239, 68, 68, 0.1);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--text-secondary);
}

.status-indicator.active .status-dot {
  background: var(--success);
  animation: pulse 2s infinite;
}

.status-indicator.loading .status-dot {
  background: var(--warning);
  animation: pulse 1s infinite;
}

.status-indicator.error .status-dot {
  background: var(--error);
  animation: pulse 1s infinite;
}

.status-text {
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--text-secondary);
}

.status-indicator.active .status-text {
  color: var(--success);
}

.status-indicator.loading .status-text {
  color: var(--warning);
}

.status-indicator.error .status-text {
  color: var(--error);
}

.error-details,
.debug-info {
  margin-top: 0.25rem;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  border: 1px solid;
}

.error-details {
  background: rgba(239, 68, 68, 0.1);
  border-color: var(--error);
}

.error-details small {
  color: var(--error);
  font-size: 0.6875rem;
}

.debug-info {
  background: rgba(158, 127, 255, 0.1);
  border-color: var(--primary);
}

.debug-info small {
  color: var(--primary);
  font-size: 0.6875rem;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.icon {
  width: 16px;
  height: 16px;
}

@media (max-width: 768px) {
  .playback-controls {
    gap: 1rem;
    padding: 1rem;
  }
  
  .tempo-control,
  .volume-control,
  .zoom-control {
    min-width: 100px;
  }
  
  .transport-btn {
    padding: 0.625rem 0.875rem;
    font-size: 0.8125rem;
  }
  
  .song-info {
    gap: 0.75rem;
  }
}
</style>
