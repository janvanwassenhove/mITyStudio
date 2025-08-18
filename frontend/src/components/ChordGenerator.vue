<template>
  <div class="chord-generator">
    <div class="chord-generator-header">
      <Music class="header-icon" />
      <h3>Chord Generator</h3>
    </div>

    <div v-if="!selectedTrack" class="no-track-selected">
      <p>Select a track to generate chords</p>
    </div>

    <div v-else class="chord-controls">
      <!-- Track Info -->
      <div class="track-info">
        <span class="track-name">{{ selectedTrack.name }}</span>
        <span class="track-instrument">{{ getInstrumentLabel(selectedTrack.instrument) }}</span>
      </div>

      <!-- Key Selection -->
      <div class="control-group">
        <label>Key:</label>
        <select v-model="selectedKey" @change="updateKey" class="key-select">
          <option v-for="key in availableKeys" :key="key" :value="key">
            {{ getKeyLabel(key) }}
          </option>
        </select>
      </div>

      <!-- Chord Duration -->
      <div class="control-group">
        <label>Chord Duration:</label>
        <div class="duration-controls">
          <button 
            v-for="duration in chordDurations" 
            :key="duration.value"
            @click="chordDuration = duration.value"
            :class="{ active: chordDuration === duration.value }"
            class="duration-btn"
          >
            {{ duration.label }}
          </button>
        </div>
      </div>

      <!-- Start Position -->
      <div class="control-group">
        <label>Start Position (bars):</label>
        <input 
          type="number" 
          v-model.number="startPosition" 
          min="0" 
          :max="songDuration"
          class="position-input"
        >
      </div>

      <!-- Progression Type Selection -->
      <div class="control-group">
        <label>Progression Type:</label>
        <div class="progression-selector">
          <div 
            v-for="suggestion in progressionSuggestions" 
            :key="suggestion.type"
            @click="selectedProgression = suggestion.type"
            :class="{ active: selectedProgression === suggestion.type }"
            class="progression-option"
          >
            <div class="progression-name">{{ suggestion.name }}</div>
            <div class="progression-description">{{ suggestion.description }}</div>
          </div>
        </div>
      </div>

      <!-- Number of Repeats -->
      <div class="control-group">
        <label>Repeats:</label>
        <div class="repeat-controls">
          <button @click="decrementRepeats" :disabled="numRepeats <= 1" class="repeat-btn">-</button>
          <span class="repeat-count">{{ numRepeats }}</span>
          <button @click="incrementRepeats" :disabled="numRepeats >= 8" class="repeat-btn">+</button>
        </div>
      </div>

      <!-- Action Buttons -->
      <div class="action-buttons">
        <button 
          @click="generateProgression" 
          :disabled="!selectedProgression || !audioStore.isInitialized"
          class="btn btn-primary"
        >
          <Music class="icon" />
          Generate Progression
        </button>
        
        <button 
          @click="generateRandom" 
          :disabled="!audioStore.isInitialized"
          class="btn btn-accent"
        >
          <Shuffle class="icon" />
          Random Chords
        </button>
        
        <button 
          @click="clearChords" 
          :disabled="!hasClips"
          class="btn btn-warning"
        >
          <Trash class="icon" />
          Clear All
        </button>
        
        <button 
          @click="createVisualizationDemo"
          class="btn btn-secondary"
        >
          <Music class="icon" />
          Visualization Demo
        </button>
      </div>

      <!-- Preview Section -->
      <div v-if="lastGeneratedProgression" class="preview-section">
        <h4>Generated Progression:</h4>
        <div class="chord-sequence">
          <div 
            v-for="(chord, index) in lastGeneratedProgression" 
            :key="index"
            class="chord-preview"
          >
            <span class="chord-root">{{ chord.root }}</span>
            <span class="chord-type">{{ formatChordType(chord.type) }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { Music, Shuffle, Trash } from 'lucide-vue-next'
import { useAudioStore } from '../stores/audioStore'
import type { ChordProgressionType } from '../services/chordService'

const audioStore = useAudioStore()

// Reactive state
const selectedKey = ref('C')
const selectedProgression = ref<ChordProgressionType>('I-V-vi-IV')
const chordDuration = ref(2)
const startPosition = ref(0)
const numRepeats = ref(1)
const lastGeneratedProgression = ref<Array<{ root: string; type: string }>>([])

// Computed properties
const selectedTrack = computed(() => audioStore.selectedTrack)
const songDuration = computed(() => audioStore.songStructure.duration)
const availableKeys = computed(() => audioStore.getAvailableKeys())
const progressionSuggestions = computed(() => audioStore.getChordProgressionSuggestions())

const hasClips = computed(() => {
  return selectedTrack.value ? selectedTrack.value.clips.length > 0 : false
})

// Constants
const chordDurations = [
  { label: '1/2 bar', value: 0.5 },
  { label: '1 bar', value: 1 },
  { label: '2 bars', value: 2 },
  { label: '4 bars', value: 4 }
]

// Watch for key changes in the song
watch(() => audioStore.songStructure.key, (newKey) => {
  selectedKey.value = newKey
})

// Watch for track selection changes
watch(selectedTrack, (newTrack) => {
  if (newTrack) {
    // Auto-select appropriate instrument-based settings
    if (newTrack.instrument === 'piano' || newTrack.instrument === 'electric-piano') {
      chordDuration.value = 2
    } else {
      chordDuration.value = 1
    }
  }
})

onMounted(() => {
  selectedKey.value = audioStore.songStructure.key
})

// Methods
const updateKey = () => {
  audioStore.songStructure.key = selectedKey.value
  audioStore.updateSongStructure()
}

const incrementRepeats = () => {
  if (numRepeats.value < 8) {
    numRepeats.value++
  }
}

const decrementRepeats = () => {
  if (numRepeats.value > 1) {
    numRepeats.value--
  }
}

const generateProgression = () => {
  if (!selectedTrack.value || !selectedProgression.value) {
    return
  }

  const startTimeInSeconds = startPosition.value * (60 / audioStore.songStructure.tempo) * 4
  
  audioStore.generateChordProgression(
    selectedTrack.value.id,
    selectedProgression.value,
    startTimeInSeconds,
    chordDuration.value,
    numRepeats.value
  )

  // Update preview (simplified for display)
  updateProgressionPreview()
}

const generateRandom = () => {
  if (!selectedTrack.value) {
    return
  }

  const startTimeInSeconds = startPosition.value * (60 / audioStore.songStructure.tempo) * 4
  const randomLength = Math.floor(Math.random() * 4) + 3 // 3-6 chords
  
  audioStore.generateRandomChordProgression(
    selectedTrack.value.id,
    startTimeInSeconds,
    chordDuration.value,
    randomLength
  )

  // Update preview
  lastGeneratedProgression.value = [
    { root: 'Random', type: 'Progression' }
  ]
}

const clearChords = () => {
  if (!selectedTrack.value) {
    return
  }

  audioStore.clearTrackClips(selectedTrack.value.id)
  lastGeneratedProgression.value = []
}

const createVisualizationDemo = () => {
  if (!selectedTrack.value) {
    console.warn('No track selected for visualization demo')
    return
  }

  console.log('🎨 Creating chord visualization demo...')
  
  // Clear existing clips first
  audioStore.clearTrackClips(selectedTrack.value.id)
  
  // Create a demo chord progression with different chord types
  const demoChords = [
    { chord: 'C_major', bar: 0, type: 'major' },
    { chord: 'A_minor', bar: 1, type: 'minor' },
    { chord: 'F_maj7', bar: 2, type: 'maj7' },
    { chord: 'G_dom7', bar: 3, type: 'dom7' },
    { chord: 'E_minor', bar: 4, type: 'minor' },
    { chord: 'D_sus4', bar: 5, type: 'sus4' },
    { chord: 'B_diminished', bar: 6, type: 'diminished' },
    { chord: 'C_major', bar: 7, type: 'major' }
  ]
  
  // Get the instrument type for sample path
  const instrument = selectedTrack.value.instrument === 'electric-piano' ? 'piano' : selectedTrack.value.instrument
  const sampleInstrument = ['piano', 'guitar'].includes(instrument) ? instrument : 'piano'
  
  // Add chord clips to demonstrate visualization
  demoChords.forEach(({ chord, bar }) => {
    const sampleUrl = `/samples/${sampleInstrument}/2_0s/wav/${chord}.wav`
    const startTime = bar * 4 // 4 seconds per bar
    const duration = 4 // 1 bar duration
    
    const chordClip = {
      startTime,
      duration,
      type: 'sample' as const,
      instrument: selectedTrack.value!.instrument,
      sampleUrl,
      volume: 0.8,
      effects: {
        reverb: 0,
        delay: 0,
        distortion: 0,
        pitchShift: 0,
        chorus: 0,
        filter: 0,
        bitcrush: 0
      }
    }
    
    audioStore.addClip(selectedTrack.value!.id, chordClip)
  })
  
  // Update the song duration to accommodate all chords
  if (audioStore.songStructure.duration < 32) {
    audioStore.songStructure.duration = 32
    audioStore.updateSongStructure()
  }
  
  // Update preview
  lastGeneratedProgression.value = demoChords.map(({ chord, type }) => {
    const [root] = chord.split('_')
    return { root, type }
  })
  
  console.log('✅ Visualization demo created with 8 different chord types!')
  console.log('🎨 Features demonstrated:')
  console.log('   • Major, minor, 7th, sus4, and diminished chords')
  console.log('   • Color-coded bars for each chord type')
  console.log('   • Bar numbering from 1-8')
  console.log('   • Audio format indicators (WAV)')
  console.log('   • Instrument type display')
}

// Helper functions
const getInstrumentLabel = (instrument: string): string => {
  const labels: { [key: string]: string } = {
    'piano': 'Piano',
    'electric-piano': 'Electric Piano',
    'guitar': 'Guitar',
    'bass': 'Bass',
    'drums': 'Drums',
    'strings': 'Strings',
    'synth': 'Synth'
  }
  return labels[instrument] || instrument
}

const getKeyLabel = (key: string): string => {
  const labels: { [key: string]: string } = {
    'C': 'C Major',
    'G': 'G Major',
    'F': 'F Major',
    'Am': 'A Minor',
    'Em': 'E Minor',
    'Dm': 'D Minor'
  }
  return labels[key] || key
}

const formatChordType = (type: string): string => {
  return type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
}

const updateProgressionPreview = () => {
  // Simple chord progression preview update
  console.log('Updating chord progression preview')
}
</script>

<style scoped>
.chord-generator-header {
  display: flex;
  align-items: center;
  margin-bottom: 1rem;
}

.header-icon {
  margin-right: 0.5rem;
}

.no-track-selected {
  text-align: center;
  color: #888;
}

.track-info {
  margin-bottom: 1rem;
}

.control-group {
  margin-bottom: 1rem;
}

.key-select {
  width: 100%;
  padding: 0.5rem;
  border: 1px solid #ccc;
  border-radius: 4px;
}

.duration-controls {
  display: flex;
  gap: 0.5rem;
}

.duration-btn {
  flex: 1;
  padding: 0.5rem;
  border: 1px solid #007bff;
  border-radius: 4px;
  background-color: #fff;
  color: #007bff;
  cursor: pointer;
}

.duration-btn.active {
  background-color: #007bff;
  color: #fff;
}

.position-input {
  width: 100%;
  padding: 0.5rem;
  border: 1px solid #ccc;
  border-radius: 4px;
}

.progression-selector {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.progression-option {
  flex: 1 1 calc(33.333% - 0.5rem);
  padding: 0.5rem;
  border: 1px solid #007bff;
  border-radius: 4px;
  background-color: #fff;
  color: #007bff;
  cursor: pointer;
}

.progression-option.active {
  background-color: #007bff;
  color: #fff;
}

.repeat-controls {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.repeat-btn {
  padding: 0.5rem;
  border: 1px solid #007bff;
  border-radius: 4px;
  background-color: #fff;
  color: #007bff;
  cursor: pointer;
}

.btn {
  padding: 0.5rem 1rem;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.btn-primary {
  background-color: #007bff;
  color: #fff;
}

.btn-accent {
  background-color: #28a745;
  color: #fff;
}

.btn-warning {
  background-color: #ffc107;
  color: #333;
}

.btn-secondary {
  background-color: #6c757d;
  color: #fff;
}

.icon {
  margin-right: 0.5rem;
}

.preview-section {
  margin-top: 1rem;
}

.chord-sequence {
  display: flex;
  gap: 0.5rem;
}

.chord-preview {
  padding: 0.5rem;
  border: 1px solid #007bff;
  border-radius: 4px;
  background-color: #f8f9fa;
}
</style>
