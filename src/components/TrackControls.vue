<template>
  <div class="track-controls">
    <div class="controls-header">
      <div class="header-title">
        <Layers class="header-icon" />
        <h3>Tracks</h3>
      </div>
      
      <button class="btn btn-primary add-track-btn" @click="addNewTrack">
        <Plus class="icon" />
        Add Track
      </button>
    </div>
    
    <div class="tracks-list">
      <div v-if="tracks.length === 0" class="empty-state">
        <Music class="empty-icon" />
        <p>No tracks yet</p>
        <button class="btn btn-ghost" @click="addNewTrack">
          Add your first track
        </button>
      </div>
      
      <template v-else>
        <div style="display: flex; flex-direction: column;">
          <div
            v-for="track in tracks"
            :key="track.id"
            class="track-item"
            :class="{ selected: selectedTrack === track.id, expanded: selectedTrack === track.id }"
            @click="selectTrack(track.id)"
          >
            <div
              class="track-header"
              :class="{ maximized: selectedTrack === track.id }"
            >
              <div class="track-info">
                <button 
                  class="track-icon-btn"
                  @click.stop="openInstrumentSelector(track.id)"
                  :title="'Change instrument/sample'"
                >
                  <div class="track-icon">
                    <component :is="getTrackIcon(track.instrument)" class="icon" />
                  </div>
                </button>
                <div class="track-details">
                  <input 
                    :key="`input-${track.id}`"
                    v-model="track.name"
                    class="track-name-input"
                    @click.stop
                    @blur="updateTrackName(track.id, getInputValue($event))"
                  />
                  <span class="track-instrument">{{ getInstrumentDisplayName(track.instrument) }}</span>
                </div>
              </div>
              
              <div class="track-actions">
                <button 
                  class="btn-icon"
                  :class="{ 'active': !track.muted }"
                  @click.stop="toggleMute(track.id)"
                  :title="track.muted ? 'Unmute' : 'Mute'"
                >
                  <VolumeX v-if="track.muted" class="icon" />
                  <Volume2 v-else class="icon" />
                </button>
                
                <button 
                  class="btn-icon"
                  :class="{ 'active': track.solo }"
                  @click.stop="toggleSolo(track.id)"
                  title="Solo"
                >
                  <Headphones class="icon" />
                </button>
                
                <button 
                  class="btn-icon delete-btn"
                  @click.stop="deleteTrack(track.id)"
                  title="Delete Track"
                >
                  <Trash2 class="icon" />
                </button>
              </div>
            </div>
            
            <div v-if="selectedTrack === track.id" class="track-controls-section">
              <div class="volume-control">
                <label>Volume</label>
                <input 
                  :key="`volume-${track.id}`"
                  type="range" 
                  min="0" 
                  max="1" 
                  step="0.01"
                  :value="track.volume"
                  @input="updateTrackVolume(track.id, getInputValue($event))"
                  class="slider"
                />
                <span class="volume-value">{{ Math.round(track.volume * 100) }}%</span>
              </div>
              
              <div class="pan-control">
                <label>Pan</label>
                <input 
                  :key="`pan-${track.id}`"
                  type="range" 
                  min="-1" 
                  max="1" 
                  step="0.01"
                  :value="track.pan"
                  @input="updateTrackPan(track.id, getInputValue($event))"
                  class="slider"
                />
                <span class="pan-value">{{ getPanLabel(track.pan) }}</span>
              </div>
            </div>
            
            <div v-if="selectedTrack === track.id" :key="`effects-${track.id}`" class="effects-section">
              <h4>Effects</h4>
              
              <div class="effect-control">
                <label>Reverb</label>
                <input 
                  :key="`reverb-${track.id}`"
                  type="range" 
                  min="0" 
                  max="1" 
                  step="0.01"
                  :value="track.effects.reverb"
                  @input="updateTrackEffect(track.id, 'reverb', getInputValue($event))"
                  class="slider"
                />
                <span>{{ Math.round(track.effects.reverb * 100) }}%</span>
              </div>
              
              <div class="effect-control">
                <label>Delay</label>
                <input 
                  :key="`delay-${track.id}`"
                  type="range" 
                  min="0" 
                  max="1" 
                  step="0.01"
                  :value="track.effects.delay"
                  @input="updateTrackEffect(track.id, 'delay', getInputValue($event))"
                  class="slider"
                />
                <span>{{ Math.round(track.effects.delay * 100) }}%</span>
              </div>
              
              <div class="effect-control">
                <label>Distortion</label>
                <input 
                  :key="`distortion-${track.id}`"
                  type="range" 
                  min="0" 
                  max="1" 
                  step="0.01"
                  :value="track.effects.distortion"
                  @input="updateTrackEffect(track.id, 'distortion', getInputValue($event))"
                  class="slider"
                />
                <span>{{ Math.round(track.effects.distortion * 100) }}%</span>
              </div>
            </div>
          </div>
        </div>
      </template>
    </div>

    <!-- Instrument/Sample Selection Modal -->
    <div v-if="showInstrumentSelector" class="modal-overlay" @click="closeInstrumentSelector">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Select Instrument or Sample</h3>
          <button class="btn-icon close-btn" @click="closeInstrumentSelector">
            <X class="icon" />
          </button>
        </div>
        
        <div class="modal-body">
          <div class="selection-tabs">
            <button 
              class="tab-btn"
              :class="{ 'active': activeTab === 'instruments' }"
              @click="activeTab = 'instruments'"
            >
              <Music class="icon" />
              Instruments
            </button>
            <button 
              class="tab-btn"
              :class="{ 'active': activeTab === 'samples' }"
              @click="activeTab = 'samples'"
            >
              <FileAudio class="icon" />
              Samples
            </button>
          </div>
          
          <div class="selection-content">
            <!-- Instruments Tab -->
            <div v-if="activeTab === 'instruments'" class="instruments-grid">
              <button
                v-for="instrument in availableInstruments"
                :key="instrument.value"
                class="instrument-card"
                :class="{ 'selected': selectedInstrumentValue === instrument.value }"
                @click="selectInstrument(instrument.value)"
              >
                <div class="instrument-icon">
                  <component :is="getTrackIcon(instrument.value)" class="icon" />
                </div>
                <div class="instrument-info">
                  <h4>{{ instrument.name }}</h4>
                  <p>{{ instrument.description }}</p>
                </div>
              </button>
            </div>
            
            <!-- Samples Tab -->
            <div v-if="activeTab === 'samples'" class="samples-grid">
              <div class="sample-category" v-for="category in sampleCategories" :key="category.name">
                <h4 class="category-title">{{ category.name }}</h4>
                <div class="samples-list">
                  <button
                    v-for="sample in category.samples"
                    :key="sample.id"
                    class="sample-card"
                    :class="{ 'selected': selectedInstrumentValue === sample.id }"
                    @click="selectSample(sample)"
                  >
                    <div class="sample-icon">
                      <component :is="getSampleIcon(category.name)" class="icon" />
                    </div>
                    <div class="sample-info">
                      <h5>{{ sample.name }}</h5>
                      <p>{{ sample.duration }}s</p>
                    </div>
                    <button 
                      class="play-sample-btn"
                      @click.stop="previewSample(sample)"
                      :disabled="isPreviewPlaying"
                    >
                      <Play v-if="!isPreviewPlaying || previewingSample !== sample.id" class="icon" />
                      <Square v-else class="icon" />
                    </button>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
        
        <div class="modal-footer">
          <button class="btn btn-ghost" @click="closeInstrumentSelector">
            Cancel
          </button>
          <button 
            class="btn btn-primary" 
            @click="applySelection"
            :disabled="!selectedInstrumentValue"
          >
            Apply
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useAudioStore } from '../stores/audioStore'
import { useSampleStore } from '../stores/sampleStore'
import { 
  Layers, Plus, Music, Volume2, VolumeX, Headphones, Trash2,
  Piano, Drum, Guitar, Mic, Zap, X, FileAudio, Play, Square
} from 'lucide-vue-next'

const audioStore = useAudioStore()
const sampleStore = useSampleStore()
const selectedTrack = ref<string | null>(null)
const showInstrumentSelector = ref(false)
const selectedTrackForInstrument = ref<string | null>(null)
const activeTab = ref<'instruments' | 'samples'>('instruments')
const selectedInstrumentValue = ref<string>('')
const isPreviewPlaying = ref(false)
const previewingSample = ref<string | null>(null)

// Computed property with safety check
const tracks = computed(() => {
  if (!audioStore.songStructure || !audioStore.songStructure.tracks) {
    return []
  }
  return audioStore.songStructure.tracks
})

const availableInstruments = [
  { 
    name: 'Piano', 
    value: 'piano', 
    description: 'Classic acoustic piano sound' 
  },
  { 
    name: 'Electric Piano', 
    value: 'electric-piano', 
    description: 'Vintage electric piano with warmth' 
  },
  { 
    name: 'Drums', 
    value: 'drums', 
    description: 'Full drum kit with multiple sounds' 
  },
  { 
    name: 'Bass', 
    value: 'bass', 
    description: 'Deep bass guitar tones' 
  },
  { 
    name: 'Electric Guitar', 
    value: 'electric-guitar', 
    description: 'Clean and distorted guitar sounds' 
  },
  { 
    name: 'Acoustic Guitar', 
    value: 'acoustic-guitar', 
    description: 'Natural acoustic guitar strumming' 
  },
  { 
    name: 'Synth Lead', 
    value: 'synth-lead', 
    description: 'Bright synthesizer lead sounds' 
  },
  { 
    name: 'Synth Pad', 
    value: 'synth-pad', 
    description: 'Atmospheric pad sounds' 
  },
  { 
    name: 'Vocals', 
    value: 'vocals', 
    description: 'Human voice recording' 
  },
  { 
    name: 'Strings', 
    value: 'strings', 
    description: 'Orchestral string section' 
  }
]

// Dynamically computed sample categories from the sample store
const sampleCategories = computed(() => {
  // Group samples by category
  const grouped: { name: string, samples: any[] }[] = []
  const library = sampleStore.sampleLibrary
  for (const category in library) {
    grouped.push({
      name: category.charAt(0).toUpperCase() + category.slice(1),
      samples: library[category]
    })
  }
  return grouped
})

const getTrackIcon = (instrument: string) => {
  const iconMap: Record<string, any> = {
    piano: Piano,
    'electric-piano': Piano,
    drums: Drum,
    bass: Guitar,
    'electric-guitar': Guitar,
    'acoustic-guitar': Guitar,
    'synth-lead': Zap,
    'synth-pad': Zap,
    vocals: Mic,
    strings: Music
  }
  return iconMap[instrument] || Music
}

const getSampleIcon = (category: string) => {
  const iconMap: Record<string, any> = {
    'Drums': Drum,
    'Bass': Guitar,
    'Melodic': Piano,
    'Vocals': Mic
  }
  return iconMap[category] || Music
}

const getInstrumentDisplayName = (instrument: string) => {
  const instrument_obj = availableInstruments.find(i => i.value === instrument)
  if (instrument_obj) return instrument_obj.name
  
  // Check if it's a sample
  for (const category of sampleCategories.value) {
    const sample = category.samples.find((s: any) => s.id === instrument)
    if (sample) return sample.name
  }
  
  return instrument.charAt(0).toUpperCase() + instrument.slice(1)
}

// Debug logging utility
function debugLog(...args: any[]) {
  if (process.env.NODE_ENV !== 'production') {
    // eslint-disable-next-line no-console
    console.debug('[TrackControls]', ...args)
  }
}

const addNewTrack = () => {
  const instrument = availableInstruments[Math.floor(Math.random() * availableInstruments.length)]
  const trackId = audioStore.addTrack(`New ${instrument.name}`, instrument.value)
  debugLog('Added new track', { trackId, instrument })
  if (trackId) {
    selectedTrack.value = trackId
  }
}

const selectTrack = (trackId: string) => {
  selectedTrack.value = selectedTrack.value === trackId ? null : trackId
}

const openInstrumentSelector = (trackId: string) => {
  selectedTrackForInstrument.value = trackId
  const track = tracks.value.find(t => t.id === trackId)
  if (track) {
    selectedInstrumentValue.value = track.instrument
  }
  showInstrumentSelector.value = true
}

const closeInstrumentSelector = () => {
  showInstrumentSelector.value = false
  selectedTrackForInstrument.value = null
  selectedInstrumentValue.value = ''
  activeTab.value = 'instruments'
}

const selectInstrument = (instrumentValue: string) => {
  selectedInstrumentValue.value = instrumentValue
}

const selectSample = (sample: any) => {
  selectedInstrumentValue.value = sample.id
}

const previewSample = async (sample: any) => {
  if (isPreviewPlaying.value) {
    // Stop current preview
    isPreviewPlaying.value = false
    previewingSample.value = null
    return
  }
  
  try {
    isPreviewPlaying.value = true
    previewingSample.value = sample.id
    
    // Create audio element for preview
    const audio = new Audio(sample.url)
    audio.volume = 0.5
    
    audio.onended = () => {
      isPreviewPlaying.value = false
      previewingSample.value = null
    }
    
    audio.onerror = () => {
      isPreviewPlaying.value = false
      previewingSample.value = null
      console.warn('Could not preview sample:', sample.name)
    }
    
    await audio.play()
  } catch (error) {
    isPreviewPlaying.value = false
    previewingSample.value = null
    console.warn('Could not preview sample:', error)
  }
}

const applySelection = () => {
  if (selectedTrackForInstrument.value && selectedInstrumentValue.value) {
    audioStore.updateTrack(selectedTrackForInstrument.value, {
      instrument: selectedInstrumentValue.value
    })
    closeInstrumentSelector()
  }
}

const updateTrackName = (trackId: string, name: string) => {
  if (name && name.trim()) {
    audioStore.updateTrack(trackId, { name: name.trim() })
  }
}

const updateTrackVolume = (trackId: string, volume: string) => {
  const volumeValue = parseFloat(volume)
  if (!isNaN(volumeValue)) {
    audioStore.updateTrack(trackId, { volume: volumeValue })
  }
}

const updateTrackPan = (trackId: string, pan: string) => {
  const panValue = parseFloat(pan)
  if (!isNaN(panValue)) {
    audioStore.updateTrack(trackId, { pan: panValue })
  }
}

const updateTrackEffect = (trackId: string, effect: string, value: string) => {
  const effectValue = parseFloat(value)
  if (!isNaN(effectValue)) {
    const track = tracks.value.find(t => t.id === trackId)
    if (track && track.effects) {
      const effects = { ...track.effects, [effect]: effectValue }
      audioStore.updateTrack(trackId, { effects })
    }
  }
}

const toggleMute = (trackId: string) => {
  const track = tracks.value.find(t => t.id === trackId)
  if (track) {
    audioStore.updateTrack(trackId, { muted: !track.muted })
  }
}

const toggleSolo = (trackId: string) => {
  const track = tracks.value.find(t => t.id === trackId)
  if (track) {
    audioStore.updateTrack(trackId, { solo: !track.solo })
  }
}

const deleteTrack = (trackId: string) => {
  if (confirm('Delete this track? This action cannot be undone.')) {
    audioStore.removeTrack(trackId)
    if (selectedTrack.value === trackId) {
      selectedTrack.value = null
    }
  }
}

const getPanLabel = (pan: number): string => {
  if (pan < -0.1) return `L${Math.round(Math.abs(pan) * 100)}`
  if (pan > 0.1) return `R${Math.round(pan * 100)}`
  return 'C'
}

// Fix $event.target.value lint errors by type casting and null checks
function getInputValue(event: Event): string {
  const target = event.target as HTMLInputElement | null;
  return target ? target.value : '';
}
</script>

<style scoped>
.track-controls {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--background);
  overflow: hidden;
}

.controls-header {
  padding: 1rem 1rem 0 1rem;
  border-bottom: 1px solid var(--border);
  background: var(--surface);
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  /* Responsive height: aligns with playback controls + timeline ruler */
  height: calc(var(--timeline-ruler-height, 87px) + var(--playback-controls-height, 64px));
  box-sizing: border-box;
}

.header-title {
  display: flex;
  align-items: center; 
  gap: 0.75rem;
  margin-bottom: 1rem;
}

.header-icon {
  width: 20px;
  height: 20px;
  color: var(--primary);
}

.header-title h3 {
  margin: 0;
  font-size: 1.125rem;
  color: var(--text);
}

.add-track-btn {
  width: 100%;
  justify-content: center;
  gap: 0.5rem;
}

.tracks-list {
  flex: 1;
  overflow-y: auto;
  padding: 0.5rem;
  min-height: 0;
}

.empty-state {
  text-align: center;
  padding: 2rem 1rem;
  color: var(--text-secondary);
}

.empty-icon {
  width: 48px;
  height: 48px;
  margin-bottom: 1rem;
  opacity: 0.5;
}

.track-item {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  margin-bottom: 0.5rem;
  cursor: pointer;
  transition: all 0.2s ease;
  /* Ensure track-item height matches the track lane height variable */
  height: var(--track-lane-height, 70px);
  display: flex;
  flex-direction: column;
  justify-content: stretch;
}

.track-item:hover {
  border-color: var(--primary);
}

.track-item.selected {
  border-color: var(--primary);
  box-shadow: 0 0 0 1px var(--primary);
}

.track-item.expanded {
  height: auto;
  min-height: var(--track-lane-height, 104px);
}

.track-header {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  height: 100%;
  min-height: unset;
  padding: 0.75rem 0.875rem 0.5rem 0.875rem;
  box-sizing: border-box;
  margin: 0;
  gap: 0.5rem;
}

.track-info {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex: 1;
  margin: 0;
}

.track-icon-btn {
  background: none;
  border: none;
  padding: 0;
  cursor: pointer;
  border-radius: 6px;
  transition: all 0.2s ease;
}

.track-icon-btn:hover {
  transform: scale(1.05);
}

.track-icon {
  width: 32px;
  height: 32px;
  background: var(--gradient-primary);
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.track-icon .icon {
  width: 16px;
  height: 16px;
  color: white;
}

.track-details {
  flex: 1;
  min-width: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
}

.track-name-input {
  background: transparent;
  border: none;
  color: var(--text);
  font-weight: 500;
  font-size: 0.875rem;
  width: 100%;
  padding: 2px 4px;
  border-radius: 4px;
  margin-bottom: 0;
}

.track-name-input:focus {
  background: var(--background);
  outline: 1px solid var(--primary);
}

.track-instrument {
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.track-actions {
  display: flex;
  gap: 0.25rem;
  align-items: center;
  justify-content: flex-end;
  margin: 0;
}

.btn-icon {
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s ease;
  color: var(--text-secondary);
}

.btn-icon:hover {
  background: var(--border);
  color: var(--text);
}

.btn-icon.active {
  background: var(--primary);
  color: white;
}

.btn-icon.delete-btn:hover {
  background: var(--error);
  color: white;
}

.btn-icon .icon {
  width: 14px;
  height: 14px;
}

.track-controls-section {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 0.5rem;
  border-top: 1px solid var(--border);
}

.effects-section {
  padding: 0.5rem 0 0 0;
  border-top: none;
  background: transparent;
}

.volume-control,
.pan-control {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.volume-control label,
.pan-control label {
  font-size: 0.75rem;
  color: var(--text-secondary);
  min-width: 50px;
}

.slider {
  flex: 1;
  height: 4px;
  background: var(--border);
  border-radius: 2px;
  outline: none;
  cursor: pointer;
}

.slider::-webkit-slider-thumb {
  appearance: none;
  width: 16px;
  height: 16px;
  background: var(--primary);
  border-radius: 50%;
  cursor: pointer;
}

.slider::-moz-range-thumb {
  width: 16px;
  height: 16px;
  background: var(--primary);
  border-radius: 50%;
  border: none;
  cursor: pointer;
}

.volume-value,
.pan-value {
  font-size: 0.75rem;
  color: var(--text-secondary);
  min-width: 35px;
  text-align: right;
}

.effects-section {
  padding: 0.875rem;
  border-top: 1px solid var(--border);
  background: var(--background);
}

.effects-section h4 {
  margin: 0 0 0.75rem 0;
  font-size: 0.875rem;
  color: var(--text);
}

.effect-control {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.5rem;
}

.effect-control label {
  font-size: 0.75rem;
  color: var(--text-secondary);
  min-width: 60px;
}

.effect-control span {
  font-size: 0.75rem;
  color: var(--text-secondary);
  min-width: 35px;
  text-align: right;
}

/* Modal Styles */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.8);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(4px);
}

.modal-content {
  background: var(--surface);
  border-radius: 12px;
  width: 90vw;
  max-width: 800px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--border);
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3);
}

.modal-header {
  padding: 1.5rem;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.modal-header h3 {
  margin: 0;
  color: var(--text);
  font-size: 1.25rem;
}

.close-btn {
  width: 32px;
  height: 32px;
}

.modal-body {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.selection-tabs {
  display: flex;
  border-bottom: 1px solid var(--border);
}

.tab-btn {
  flex: 1;
  padding: 1rem;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  transition: all 0.2s ease;
}

.tab-btn:hover {
  background: var(--border);
  color: var(--text);
}

.tab-btn.active {
  background: var(--primary);
  color: white;
}

.tab-btn .icon {
  width: 16px;
  height: 16px;
}

.selection-content {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
}

.instruments-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1rem;
}

.instrument-card {
  background: var(--background);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 1rem;
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  gap: 1rem;
  text-align: left;
}

.instrument-card:hover {
  border-color: var(--primary);
  transform: translateY(-2px);
}

.instrument-card.selected {
  border-color: var(--primary);
  background: var(--primary);
  color: white;
}

.instrument-icon {
  width: 40px;
  height: 40px;
  background: var(--gradient-primary);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.instrument-card.selected .instrument-icon {
  background: rgba(255, 255, 255, 0.2);
}

.instrument-icon .icon {
  width: 20px;
  height: 20px;
  color: white;
}

.instrument-info h4 {
  margin: 0 0 0.25rem 0;
  font-size: 1rem;
  font-weight: 600;
}

.instrument-info p {
  margin: 0;
  font-size: 0.875rem;
  opacity: 0.8;
}

.samples-grid {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.category-title {
  margin: 0 0 0.75rem 0;
  color: var(--text);
  font-size: 1.125rem;
  font-weight: 600;
}

.samples-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 0.75rem;
}

.sample-card {
  background: var(--background);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 0.875rem;
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  text-align: left;
}

.sample-card:hover {
  border-color: var(--primary);
}

.sample-card.selected {
  border-color: var(--primary);
  background: var(--primary);
  color: white;
}

.sample-icon {
  width: 32px;
  height: 32px;
  background: var(--gradient-primary);
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.sample-card.selected .sample-icon {
  background: rgba(255, 255, 255, 0.2);
}

.sample-icon .icon {
  width: 16px;
  height: 16px;
  color: white;
}

.sample-info {
  flex: 1;
}

.sample-info h5 {
  margin: 0 0 0.25rem 0;
  font-size: 0.875rem;
  font-weight: 500;
}

.sample-info p {
  margin: 0;
  font-size: 0.75rem;
  opacity: 0.7;
}

.play-sample-btn {
  width: 28px;
  height: 28px;
  border: none;
  background: var(--border);
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s ease;
  color: var(--text);
}

.play-sample-btn:hover {
  background: var(--primary);
  color: white;
}

.play-sample-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.play-sample-btn .icon {
  width: 12px;
  height: 12px;
}

.modal-footer {
  padding: 1.5rem;
  border-top: 1px solid var(--border);
  display: flex;
  gap: 1rem;
  justify-content: flex-end;
}

.tracks-list::-webkit-scrollbar,
.selection-content::-webkit-scrollbar {
  width: 5px;
}

.tracks-list::-webkit-scrollbar-track,
.selection-content::-webkit-scrollbar-track {
  background: transparent;
}

.tracks-list::-webkit-scrollbar-thumb,
.selection-content::-webkit-scrollbar-thumb {
  background: var(--border);
  border-radius: 3px;
}

.tracks-list::-webkit-scrollbar-thumb:hover,
.selection-content::-webkit-scrollbar-thumb:hover {
  background: var(--text-secondary);
}

@media (max-width: 768px) {
  .modal-content {
    width: 95vw;
    max-height: 90vh;
  }
  
  .instruments-grid {
    grid-template-columns: 1fr;
  }
  
  .samples-list {
    grid-template-columns: 1fr;
  }
  
  .track-header {
    padding: 0.75rem;
  }
  
  .track-actions {
    gap: 0.125rem;
  }
  
  .btn-icon {
    width: 24px;
    height: 24px;
  }
}
</style>
