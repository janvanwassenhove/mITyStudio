<template>
  <div class="chord-panel">
    <div class="panel-header">
      <h3>🎶 Chord Editor</h3>
      <p v-if="!selectedClip">Select a clip in the timeline to edit its chord sequence</p>
      <p v-else>Editing chord sequence for {{ selectedClip.instrument }} clip</p>
    </div>

    <!-- Selected Clip Info -->
    <div v-if="selectedClip" class="clip-info">
      <div class="clip-details">
        <div class="detail-row">
          <label>Instrument:</label>
          <span>{{ selectedClip.instrument }}</span>
        </div>
        <div class="detail-row">
          <label>Duration:</label>
          <span>{{ clipDuration }}s</span>
        </div>
        <div class="detail-row">
          <label>Type:</label>
          <span>{{ selectedClip.type }}</span>
        </div>
      </div>
    </div>

    <!-- Chord Sequence Editor -->
    <div v-if="selectedClip && selectedClip.notes" class="chord-editor">
      <div class="editor-header">
        <h4>Chord Sequence</h4>
        <div class="chord-controls">
          <button @click="addChord" class="btn btn-small btn-primary">
            + Add Chord
          </button>
          <button @click="clearChords" class="btn btn-small btn-warning">
            Clear All
          </button>
        </div>
      </div>

      <div class="chord-list">
        <div 
          v-for="(_note, index) in chordSequence" 
          :key="`chord-${index}`"
          class="chord-item"
          :class="{ 
            'dragging': dragState.isDragging && dragState.dragIndex === index,
            'drag-over': dragState.dragOverIndex === index && dragState.dragIndex !== index
          }"
          draggable="true"
          @dragstart="startDrag(index, $event)"
          @dragend="endDrag"
          @dragover.prevent="handleDragOver(index)"
          @drop.prevent="handleDrop(index)"
          @dragenter.prevent
          @dragleave="handleDragLeave"
        >
          <div class="drag-handle" title="Drag to reorder">
            ⋮⋮
          </div>
          <div class="chord-index">{{ index + 1 }}</div>
          <select 
            v-model="chordSequence[index]"
            @change="updateChordSequence"
            class="chord-select"
          >
            <option value="" disabled>Select chord...</option>
            <optgroup label="Basic Chords">
              <option 
                v-for="chord in availableChords.filter(c => c.category === 'basic')" 
                :key="chord.value"
                :value="chord.value"
                :disabled="!chord.available"
              >
                {{ chord.displayName }}
              </option>
            </optgroup>
            <optgroup label="Seventh Chords">
              <option 
                v-for="chord in availableChords.filter(c => c.category === 'seventh')" 
                :key="chord.value"
                :value="chord.value"
                :disabled="!chord.available"
              >
                {{ chord.displayName }}
              </option>
            </optgroup>
            <optgroup label="Suspended Chords">
              <option 
                v-for="chord in availableChords.filter(c => c.category === 'suspended')" 
                :key="chord.value"
                :value="chord.value"
                :disabled="!chord.available"
              >
                {{ chord.displayName }}
              </option>
            </optgroup>
            <optgroup label="Altered Chords">
              <option 
                v-for="chord in availableChords.filter(c => c.category === 'altered')" 
                :key="chord.value"
                :value="chord.value"
                :disabled="!chord.available"
              >
                {{ chord.displayName }}
              </option>
            </optgroup>
          </select>
          <button 
            @click="removeChord(index)" 
            class="btn btn-small btn-danger"
            title="Remove chord"
          >
            ×
          </button>
        </div>
      </div>
    </div>

    <!-- Sample Duration Editor -->
    <div v-if="selectedClip" class="sample-duration-editor">
      <div class="editor-section">
        <h4>Clip Duration</h4>
        <p class="section-description">
          Total duration of the clip
        </p>
        
        <div class="duration-control">
          <label for="clipDuration">Clip duration:</label>
          <div class="duration-input-group">
            <input 
              id="clipDuration"
              type="range"
              v-model.number="clipDuration"
              @input="updateClipDuration"
              class="duration-slider"
              min="1"
              max="30"
              step="0.5"
            />
            <span class="duration-value">{{ clipDuration }}s</span>
          </div>
        </div>
      </div>

      <div class="section-separator"></div>

      <div class="editor-section">
        <h4>Sample Duration</h4>
        <p class="section-description">
          How long each chord plays before moving to the next
        </p>
        
        <div class="duration-control">
          <label for="sampleDuration">Duration per chord:</label>
          <div class="duration-input-group">
            <input 
              id="sampleDuration"
              type="range"
              v-model.number="sampleDuration"
              @input="updateSampleDuration"
              class="duration-slider"
              min="0.1"
              max="5"
              step="0.1"
            />
            <span class="duration-value">{{ sampleDuration }}s</span>
          </div>
        </div>

        <div class="duration-info">
          <div class="info-row">
            <span>Total clip duration:</span>
            <span>{{ clipDuration }}s</span>
          </div>
          <div class="info-row">
            <span>Loops per clip:</span>
            <span>{{ Math.ceil(clipDuration / sampleDuration) }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Empty State -->
    <div v-if="!selectedClip" class="empty-state">
      <div class="empty-icon">🎼</div>
      <h4>No Clip Selected</h4>
      <p>Select a clip in the timeline editor to edit its chord sequence and sample duration.</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { useAudioStore } from '../stores/audioStore'

const audioStore = useAudioStore()

// State for chord editing
const chordSequence = ref<string[]>([])
const sampleDuration = ref(1)
const clipDuration = ref(4)

// Drag and drop state
const dragState = ref({
  isDragging: false,
  dragIndex: -1,
  dragOverIndex: -1
})

// Get selected clip from audio store
const selectedClip = computed(() => audioStore.getSelectedClip)

// Get available chords for the selected instrument
const availableChords = computed(() => {
  if (!selectedClip.value || !selectedClip.value.instrument) {
    return []
  }

  // Define all possible chord types and root notes
  const rootNotes = [
    { value: 'C', display: 'C' },
    { value: 'Cs', display: 'C#' },
    { value: 'D', display: 'D' },
    { value: 'Ds', display: 'D#' },
    { value: 'E', display: 'E' },
    { value: 'F', display: 'F' },
    { value: 'Fs', display: 'F#' },
    { value: 'G', display: 'G' },
    { value: 'Gs', display: 'G#' },
    { value: 'A', display: 'A' },
    { value: 'As', display: 'A#' },
    { value: 'B', display: 'B' }
  ]
  
  const chordTypes = [
    { value: 'major', display: 'maj', category: 'basic' },
    { value: 'minor', display: 'min', category: 'basic' },
    { value: 'dom7', display: 'dom7', category: 'seventh' },
    { value: 'maj7', display: 'maj7', category: 'seventh' },
    { value: 'min7', display: 'min7', category: 'seventh' },
    { value: 'sus2', display: 'sus2', category: 'suspended' },
    { value: 'sus4', display: 'sus4', category: 'suspended' },
    { value: 'augmented', display: 'aug', category: 'altered' },
    { value: 'diminished', display: 'dim', category: 'altered' }
  ]
  
  const chords = []
  
  // Group chords by category for better organization
  const categories = ['basic', 'seventh', 'suspended', 'altered']
  
  for (const category of categories) {
    const categoryTypes = chordTypes.filter(t => t.category === category)
    
    for (const type of categoryTypes) {
      for (const root of rootNotes) {
        const chordValue = `${root.value}_${type.value}`
        const displayName = `${root.display} ${type.display}`
        
        chords.push({
          value: chordValue,
          displayName,
          category,
          available: true // Assume available - could add actual file checking
        })
      }
    }
  }
  
  return chords
})

// Watch for clip selection changes
watch(
  [selectedClip, availableChords],
  ([newClip, newChords], [oldClip]) => {
    console.log('Clip or chords changed:', { 
      newClip: newClip?.id, 
      oldClip: oldClip?.id,
      newClipNotes: newClip?.notes,
      instrument: newClip?.instrument,
      chordsAvailable: newChords.length
    })
    
    if (newClip) {
      // Load chord sequence from clip notes
      const clipNotes = newClip.notes || []
      console.log('Loading chord sequence from clip:', clipNotes)
      chordSequence.value = [...clipNotes]
      
      // Load sample duration - clamp to slider range
      const clipSampleDuration = newClip.sampleDuration || 1
      
      // Clamp the duration to the slider's min/max range
      const clampedSampleDuration = Math.max(0.5, Math.min(4, clipSampleDuration))
      
      sampleDuration.value = clampedSampleDuration
      
      // Load clip duration - clamp to slider range
      const clipTotalDuration = newClip.duration || 4
      
      // Clamp the duration to the slider's min/max range
      const clampedClipDuration = Math.max(1, Math.min(30, clipTotalDuration))
      
      clipDuration.value = clampedClipDuration
      
      console.log('Loaded chord sequence:', chordSequence.value)
      
      // Validate chords if available
      if (newChords.length > 0 && chordSequence.value.length > 0) {
        const availableValues = newChords.map(c => c.value)
        const hasInvalidChords = chordSequence.value.some(chord => !availableValues.includes(chord))
        
        if (hasInvalidChords) {
          console.log('Found invalid chords, replacing with valid ones')
          chordSequence.value = chordSequence.value.map(chord => {
            if (availableValues.includes(chord)) {
              return chord
            }
            console.warn(`✗ Chord "${chord}" not available, defaulting to first available chord`)
            return newChords[0]?.value || 'C_major'
          })
          console.log('Final validated chord sequence:', chordSequence.value)
        }
      }
    } else {
      chordSequence.value = []
      sampleDuration.value = 1
      clipDuration.value = 4
    }
  },
  { immediate: true }
)

// Add a new chord to the sequence
const addChord = () => {
  // Get the first available chord or default to C_major
  const defaultChord = availableChords.value.length > 0 ? availableChords.value[0].value : 'C_major'
  chordSequence.value.push(defaultChord)
  updateChordSequence()
}

// Remove a chord from the sequence
const removeChord = (index: number) => {
  chordSequence.value.splice(index, 1)
  updateChordSequence()
}

// Clear all chords
const clearChords = () => {
  chordSequence.value = []
  updateChordSequence()
}

// Update the chord sequence in the audio store
const updateChordSequence = () => {
  if (!selectedClip.value) return
  
  // Find the track and clip
  for (const track of audioStore.songStructure.tracks) {
    const clip = track.clips.find(c => c.id === selectedClip.value!.id)
    if (clip) {
      // Update the clip with new notes
      audioStore.updateClip(track.id, clip.id, {
        notes: [...chordSequence.value]
      })
      break
    }
  }
}

// Update the sample duration
const updateSampleDuration = () => {
  if (!selectedClip.value) return
  
  // Find the track and clip
  for (const track of audioStore.songStructure.tracks) {
    const clip = track.clips.find(c => c.id === selectedClip.value!.id)
    if (clip) {
      // Update the clip with new sample duration
      audioStore.updateClip(track.id, clip.id, {
        sampleDuration: sampleDuration.value
      })
      break
    }
  }
}

// Update the clip duration
const updateClipDuration = () => {
  if (!selectedClip.value) return
  
  // Find the track and clip
  for (const track of audioStore.songStructure.tracks) {
    const clip = track.clips.find(c => c.id === selectedClip.value!.id)
    if (clip) {
      // Update the clip with new duration
      audioStore.updateClip(track.id, clip.id, {
        duration: clipDuration.value
      })
      break
    }
  }
}

// Drag and drop functions
const startDrag = (index: number, event: DragEvent) => {
  dragState.value.isDragging = true
  dragState.value.dragIndex = index
  
  // Set drag effect
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.setData('text/plain', index.toString())
  }
}

const endDrag = () => {
  dragState.value.isDragging = false
  dragState.value.dragIndex = -1
  dragState.value.dragOverIndex = -1
}

const handleDragOver = (index: number) => {
  if (dragState.value.isDragging && dragState.value.dragIndex !== index) {
    dragState.value.dragOverIndex = index
  }
}

const handleDragLeave = () => {
  dragState.value.dragOverIndex = -1
}

const handleDrop = (targetIndex: number) => {
  const sourceIndex = dragState.value.dragIndex
  
  if (sourceIndex !== -1 && sourceIndex !== targetIndex) {
    // Create a new array with the reordered items
    const newSequence = [...chordSequence.value]
    const draggedItem = newSequence.splice(sourceIndex, 1)[0]
    newSequence.splice(targetIndex, 0, draggedItem)
    
    // Update the sequence
    chordSequence.value = newSequence
    updateChordSequence()
  }
  
  // Reset drag state
  endDrag()
}
</script>

<style scoped>
.chord-panel {
  background: var(--surface);
  padding: 1.5rem;
  border: 1px solid var(--border);
  margin-bottom: 1rem;
  height: 100%;
  overflow-y: auto;
}

.panel-header {
  margin-bottom: 1.5rem;
  text-align: center;
}

.panel-header h3 {
  margin: 0 0 0.5rem 0;
  color: var(--text-primary);
  font-size: 1.25rem;
}

.panel-header p {
  margin: 0;
  color: var(--text-secondary);
  font-size: 0.875rem;
}

.clip-info {
  background: var(--background);
  border-radius: 8px;
  padding: 1rem;
  border: 1px solid var(--border);
  margin-bottom: 1.5rem;
}

.clip-details .detail-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.clip-details .detail-row:last-child {
  margin-bottom: 0;
}

.clip-details label {
  font-weight: 500;
  color: var(--text-secondary);
}

.clip-details span {
  color: var(--text-primary);
  font-family: 'Courier New', monospace;
}

.chord-editor {
  margin-bottom: 1.5rem;
}

.editor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.editor-header h4 {
  margin: 0;
  color: var(--text-primary);
  font-size: 1rem;
}

.chord-controls {
  display: flex;
  gap: 0.5rem;
}

.chord-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  position: relative;
}

.chord-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.5rem;
  background: var(--background);
  border-radius: 6px;
  border: 1px solid var(--border);
  cursor: grab;
  transition: all 0.2s ease;
  user-select: none;
}

.chord-item:hover {
  background: var(--surface);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.chord-item.dragging {
  opacity: 0.5;
  cursor: grabbing;
  transform: rotate(2deg);
  z-index: 1000;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
}

.chord-item.drag-over {
  border-color: var(--primary);
  background: var(--primary-alpha);
  transform: translateY(-2px);
}

.chord-item.drag-over::before {
  content: '';
  position: absolute;
  top: -2px;
  left: 0;
  right: 0;
  height: 2px;
  background: var(--primary);
  border-radius: 1px;
  z-index: 10;
}

.chord-item.drag-over::after {
  content: '';
  position: absolute;
  bottom: -2px;
  left: 0;
  right: 0;
  height: 2px;
  background: var(--primary);
  border-radius: 1px;
  z-index: 10;
}

.drag-handle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 1.5rem;
  height: 1.5rem;
  color: var(--text-secondary);
  cursor: grab;
  font-weight: bold;
  font-size: 0.75rem;
  border-radius: 3px;
  transition: all 0.2s ease;
}

.drag-handle:hover {
  background: var(--border);
  color: var(--text);
}

.chord-item.dragging .drag-handle {
  cursor: grabbing;
}

/* Ensure select remains interactive during drag */
.chord-item .chord-select {
  pointer-events: auto;
}

.chord-item.dragging .chord-select {
  pointer-events: none;
}

.chord-index {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  background: var(--primary);
  color: white;
  border-radius: 50%;
  font-size: 0.875rem;
  font-weight: 500;
}

.chord-select {
  flex: 1;
  padding: 0.5rem;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: var(--surface);
  color: var(--text-primary);
  font-family: inherit;
  cursor: pointer;
  appearance: none;
  background-image: url("data:image/svg+xml;charset=US-ASCII,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 4 5'><path fill='%23666' d='M2 0L0 2h4zm0 5L0 3h4z'/></svg>");
  background-repeat: no-repeat;
  background-position: right 0.7rem center;
  background-size: 0.65rem auto;
  padding-right: 2rem;
}

.chord-select:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: 0 0 0 2px var(--primary-alpha);
}

.chord-select option {
  padding: 0.25rem 0.5rem;
  background: var(--surface);
  color: var(--text-primary);
}

.chord-select optgroup {
  font-weight: 600;
  color: var(--text-secondary);
  background: var(--background);
  padding: 0.25rem 0;
}

.chord-select option:disabled {
  color: var(--text-disabled);
  background: var(--background);
}

.sample-duration-editor {
  margin-bottom: 1.5rem;
}

.section-separator {
  height: 1px;
  background: var(--border);
  margin: 1rem 0;
  opacity: 0.5;
}

.editor-section {
  margin-bottom: 1.5rem;
}

.editor-section:last-child {
  margin-bottom: 0;
}

.editor-section h4 {
  margin: 0 0 0.5rem 0;
  color: var(--text-primary);
  font-size: 1rem;
}

.section-description {
  margin: 0 0 1rem 0;
  color: var(--text-secondary);
  font-size: 0.875rem;
}

.duration-control {
  margin-bottom: 1rem;
}

.duration-control label {
  display: block;
  margin-bottom: 0.5rem;
  color: var(--text-secondary);
  font-weight: 500;
}

.duration-input-group {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.duration-input {
  padding: 0.5rem;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: var(--surface);
  color: var(--text-primary);
  width: 80px;
  font-family: 'Courier New', monospace;
}

.duration-slider {
  flex: 1;
  height: 6px;
  border-radius: 3px;
  background: var(--border);
  outline: none;
  appearance: none;
  cursor: pointer;
  margin-right: 1rem;
}

.duration-slider::-webkit-slider-thumb {
  appearance: none;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--primary);
  cursor: pointer;
  border: 2px solid white;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

.duration-slider::-moz-range-thumb {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--primary);
  cursor: pointer;
  border: 2px solid white;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

.duration-slider:hover::-webkit-slider-thumb {
  background: var(--primary-hover);
}

.duration-slider:hover::-moz-range-thumb {
  background: var(--primary-hover);
}

.duration-slider::-webkit-slider-track {
  height: 6px;
  border-radius: 3px;
  background: var(--border);
}

.duration-slider::-moz-range-track {
  height: 6px;
  border-radius: 3px;
  background: var(--border);
  border: none;
}

.duration-value {
  min-width: 3rem;
  text-align: center;
  color: var(--text-primary);
  font-family: 'Courier New', monospace;
  font-size: 0.875rem;
  font-weight: 500;
  background: var(--background);
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  border: 1px solid var(--border);
}

.duration-select {
  padding: 0.5rem;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: var(--surface);
  color: var(--text-primary);
  min-width: 120px;
  font-family: inherit;
  cursor: pointer;
  appearance: none;
  background-image: url("data:image/svg+xml;charset=US-ASCII,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 4 5'><path fill='%23666' d='M2 0L0 2h4zm0 5L0 3h4z'/></svg>");
  background-repeat: no-repeat;
  background-position: right 0.7rem center;
  background-size: 0.65rem auto;
  padding-right: 2rem;
}

.duration-input:focus,
.duration-select:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: 0 0 0 2px var(--primary-alpha);
}

.duration-unit {
  color: var(--text-secondary);
  font-size: 0.875rem;
}

.duration-info {
  background: var(--background);
  border-radius: 6px;
  padding: 0.75rem;
  border: 1px solid var(--border);
}

.info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.25rem;
}

.info-row:last-child {
  margin-bottom: 0;
}

.info-row span:first-child {
  color: var(--text-secondary);
  font-size: 0.875rem;
}

.info-row span:last-child {
  color: var(--text-primary);
  font-family: 'Courier New', monospace;
  font-size: 0.875rem;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 3rem 1rem;
  color: var(--text-secondary);
}

.empty-icon {
  font-size: 3rem;
  margin-bottom: 1rem;
  opacity: 0.5;
}

.empty-state h4 {
  margin: 0 0 0.5rem 0;
  color: var(--text-primary);
  font-size: 1.125rem;
}

.empty-state p {
  margin: 0;
  color: var(--text-secondary);
  font-size: 0.875rem;
  line-height: 1.4;
}

/* Button styles */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.5rem 1rem;
  border: none;
  border-radius: 6px;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  text-decoration: none;
}

.btn-small {
  padding: 0.375rem 0.75rem;
  font-size: 0.8125rem;
}

.btn-primary {
  background: var(--primary);
  color: white;
}

.btn-primary:hover {
  background: var(--primary-hover);
}

.btn-warning {
  background: #f59e0b;
  color: white;
}

.btn-warning:hover {
  background: #d97706;
}

.btn-danger {
  background: #ef4444;
  color: white;
  padding: 0.25rem 0.5rem;
  font-size: 1rem;
  min-width: 2rem;
  height: 2rem;
}

.btn-danger:hover {
  background: #dc2626;
}
</style>
