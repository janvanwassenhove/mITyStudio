<template>
  <div class="playback-controls">
    <div class="transport-controls">
      <button 
        class="btn btn-primary transport-btn"
        @click="togglePlayback"
        :class="{ playing: audioStore.isPlaying }"
      >
        <Play v-if="!audioStore.isPlaying" class="icon" />
        <Pause v-else class="icon" />
        {{ audioStore.isPlaying ? $t('playback.pause') : $t('playback.play') }}
      </button>
      
      <button class="btn btn-secondary transport-btn" @click="audioStore.stop">
        <Square class="icon" />
        {{ $t('playback.stop') }}
      </button>
      
      <button 
        class="btn btn-ghost transport-btn"
        @click="audioStore.toggleLoop"
        :class="{ active: audioStore.isLooping }"
      >
        <RotateCcw class="icon" />
        {{ $t('playback.loop') }}
      </button>
      
      <button 
        class="btn btn-ghost transport-btn"
        @click="audioStore.toggleMetronome"
        :class="{ active: audioStore.metronomeEnabled }"
      >
        <Clock class="icon" />
        {{ $t('playback.metronome') }}
      </button>
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
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useAudioStore } from '../stores/audioStore'
import { 
  Play, 
  Pause, 
  Square, 
  RotateCcw, 
  Clock, 
  Volume2, 
  ZoomIn, 
  ZoomOut 
} from 'lucide-vue-next'

const audioStore = useAudioStore()

const tempo = ref(audioStore.songStructure.tempo)
const masterVolume = ref(audioStore.masterVolume)

watch(() => audioStore.songStructure.tempo, (newTempo) => {
  tempo.value = newTempo
})

watch(() => audioStore.masterVolume, (newVolume) => {
  masterVolume.value = newVolume
})

const togglePlayback = () => {
  if (audioStore.isPlaying) {
    audioStore.pause()
  } else {
    audioStore.play()
  }
}

const updateTempo = () => {
  audioStore.setTempo(tempo.value)
}

const updateMasterVolume = () => {
  audioStore.setMasterVolume(masterVolume.value)
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
}

.transport-btn.playing {
  background: var(--gradient-accent);
  color: white;
}

.transport-btn.active {
  background: var(--primary);
  color: white;
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
}
</style>
