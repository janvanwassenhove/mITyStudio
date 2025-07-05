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
                :class="{ 
                  'selected': selectedInstrumentValue === instrument.value,
                  'sample-based': instrument.type === 'sample',
                  'synth-based': instrument.type === 'synth'
                }"
                @click="selectInstrument(instrument.value)"
              >
                <div class="instrument-icon">
                  <component :is="getTrackIcon(instrument.value)" class="icon" />
                  <!-- Sample indicator badge -->
                  <span v-if="instrument.type === 'sample'" class="sample-badge">
                    {{ instrument.chord_count }} chords
                  </span>
                </div>
                <div class="instrument-info">
                  <h4>{{ instrument.name }}</h4>
                  <p>{{ instrument.description }}</p>
                  <span v-if="instrument.type === 'sample'" class="sample-type-label">Sample-based</span>
                  <span v-else class="synth-type-label">Synthesized</span>
                </div>
              </button>
            </div>
            
            <!-- Samples Tab -->
            <div v-if="activeTab === 'samples'" class="samples-grid">
              <div class="sample-category" v-for="category in sampleCategories" :key="category.name">
                <h4 class="category-title">{{ category.name }}</h4>
                <div class="samples-list">
                  <div
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
                      <!-- Waveform Canvas -->
                      <canvas
                        v-if="sample.waveform && sample.waveform.length"
                        :ref="el => setWaveformCanvasRef(el, sample.id)"
                        class="sample-waveform-canvas"
                        width="120"
                        height="24"
                        style="display: block; margin-top: 4px; background: rgba(255,255,255,0.05); border-radius: 4px;"
                      ></canvas>
                    </div>
                    <button 
                      class="play-sample-btn"
                      @click.stop="previewSample(sample)"
                      :disabled="isPreviewPlaying"
                    >
                      <Play v-if="!isPreviewPlaying || previewingSample !== sample.id" class="icon" />
                      <Square v-else class="icon" />
                    </button>
                  </div>
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
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { useAudioStore } from '../stores/audioStore'
import { useSampleStore } from '../stores/sampleStore'
import { getSampleInstruments } from '../utils/api'
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
const currentPreviewAudio = ref<HTMLAudioElement | null>(null)
const waveformCanvasRefs = ref<Record<string, HTMLCanvasElement | null>>({})
const waveformAnimationFrame = ref<Record<string, number>>({})

// Computed property with safety check
const tracks = computed(() => {
  if (!audioStore.songStructure || !audioStore.songStructure.tracks) {
    return []
  }
  return audioStore.songStructure.tracks
})

// Dynamic instruments loaded from sample library
const sampleInstruments = ref<any[]>([])

interface InstrumentOption {
  name: string
  value: string
  description: string
  type: string
  chord_count?: number
}

const defaultInstruments: InstrumentOption[] = [
  { 
    name: 'Piano', 
    value: 'piano', 
    description: 'Classic acoustic piano sound',
    type: 'synth'
  },
  { 
    name: 'Electric Piano', 
    value: 'electric-piano', 
    description: 'Vintage electric piano with warmth',
    type: 'synth'
  },
  { 
    name: 'Synth Lead', 
    value: 'synth-lead', 
    description: 'Bright synthesizer lead sounds',
    type: 'synth'
  },
  { 
    name: 'Synth Pad', 
    value: 'synth-pad', 
    description: 'Atmospheric pad sounds',
    type: 'synth'
  }
]

// Combined available instruments (sample-based + synthesized)
const availableInstruments = computed((): InstrumentOption[] => {
  console.log('Computing availableInstruments...', {
    sampleInstruments: sampleInstruments.value,
    defaultInstruments: defaultInstruments.length
  })
  
  const combined: InstrumentOption[] = [...defaultInstruments]
  
  // Add sample-based instruments
  sampleInstruments.value.forEach(instrument => {
    console.log('Adding sample instrument:', instrument)
    combined.push({
      name: instrument.display_name,
      value: instrument.name,
      description: `Sample-based ${instrument.display_name.toLowerCase()} with ${instrument.chord_count} chords`,
      type: 'sample',
      chord_count: instrument.chord_count
    })
  })
  
  console.log('Final availableInstruments:', combined)
  return combined
})

// Load sample instruments on component mount
const loadSampleInstruments = async () => {
  try {
    console.log('Loading sample instruments...')
    const response = await getSampleInstruments()
    console.log('Raw response:', response)
    sampleInstruments.value = response.instruments || []
    console.log('Loaded sample instruments:', sampleInstruments.value)
    console.log('Available instruments now:', availableInstruments.value)
  } catch (error) {
    console.error('Failed to load sample instruments:', error)
    // Fallback to empty array - default instruments will still be available
    sampleInstruments.value = []
  }
}

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
    guitar: Guitar,  // Sample-based guitar
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
  const instrument_obj = availableInstruments.value.find((i: InstrumentOption) => i.value === instrument)
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
  // Instead of adding immediately, open the instrument/sample selector dialog
  selectedTrackForInstrument.value = null // No track yet, will create after selection
  selectedInstrumentValue.value = ''
  showInstrumentSelector.value = true
  activeTab.value = 'instruments'
}

// When user applies selection, create the track if not editing an existing one
const applySelection = () => {
  if (!selectedInstrumentValue.value) return
  if (!selectedTrackForInstrument.value) {
    // Create new track
    let instrumentName = getInstrumentDisplayName(selectedInstrumentValue.value)
    // If it's a sample, use sample name
    for (const category of sampleCategories.value) {
      const sample = category.samples.find((s: any) => s.id === selectedInstrumentValue.value)
      if (sample) instrumentName = sample.name
    }
    const trackId = audioStore.addTrack(`New ${instrumentName}`, selectedInstrumentValue.value)
    debugLog('Added new track', { trackId, instrument: selectedInstrumentValue.value })
    if (trackId) {
      selectedTrack.value = trackId
    }
    closeInstrumentSelector()
    return
  }
  // Otherwise, update existing track
  audioStore.updateTrack(selectedTrackForInstrument.value, {
    instrument: selectedInstrumentValue.value
  })
  closeInstrumentSelector()
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
    if (currentPreviewAudio.value) {
      audioStore.unregisterPreviewAudio(currentPreviewAudio.value)
      currentPreviewAudio.value.pause()
      currentPreviewAudio.value = null
    }
    isPreviewPlaying.value = false
    previewingSample.value = null
    return
  }
  try {
    isPreviewPlaying.value = true
    previewingSample.value = sample.id
    await nextTick()
    const canvas = waveformCanvasRefs.value[sample.id]
    if (canvas) drawWaveformForSample(sample.id, 0)
    const audio = new Audio(sample.url)
    audio.volume = 0.5
    
    // Register with audio store for global stop functionality
    audioStore.registerPreviewAudio(audio)
    currentPreviewAudio.value = audio
    
    audio.onended = () => {
      isPreviewPlaying.value = false
      previewingSample.value = null
      audioStore.unregisterPreviewAudio(audio)
      currentPreviewAudio.value = null
      drawWaveformForSample(sample.id, 1)
    }
    audio.onerror = () => {
      isPreviewPlaying.value = false
      previewingSample.value = null
      audioStore.unregisterPreviewAudio(audio)
      currentPreviewAudio.value = null
      drawWaveformForSample(sample.id, 0)
      console.warn('Could not preview sample:', sample.name)
    }
    audio.ontimeupdate = () => {
      if (canvas) drawWaveformForSample(sample.id, audio.currentTime / sample.duration)
    }
    audio.play()
    animateWaveform(sample.id, audio)
  } catch (error) {
    isPreviewPlaying.value = false
    previewingSample.value = null
    if (currentPreviewAudio.value) {
      audioStore.unregisterPreviewAudio(currentPreviewAudio.value)
      currentPreviewAudio.value = null
    }
    drawWaveformForSample(sample.id, 0)
    console.warn('Could not preview sample:', error)
  }
}

function setWaveformCanvasRef(el: any, sampleId: string) {
  // Fix: Handle Vue component instance and direct element
  let element: HTMLCanvasElement | null = null
  
  if (el && el instanceof HTMLCanvasElement) {
    element = el
  } else if (el && el.$el && el.$el instanceof HTMLCanvasElement) {
    element = el.$el
  }
  
  if (element) {
    waveformCanvasRefs.value[sampleId] = element
    drawWaveformForSample(sampleId)
  } else if (!el) {
    // If unmounted, clean up
    waveformCanvasRefs.value[sampleId] = null
  }
}

function drawWaveformForSample(sampleId: string, progress = 0) {
  const sample = sampleCategories.value.flatMap(cat => cat.samples).find(s => s.id === sampleId)
  const canvas = waveformCanvasRefs.value[sampleId]
  if (!sample || !canvas || !sample.waveform) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  ctx.clearRect(0, 0, canvas.width, canvas.height)
  ctx.strokeStyle = '#fff'
  ctx.lineWidth = 1
  const { width, height } = canvas
  const waveform = sample.waveform
  ctx.beginPath()
  for (let i = 0; i < waveform.length; i++) {
    const x = (i / (waveform.length - 1)) * width
    const y = height / 2 - waveform[i] * (height / 2)
    if (i === 0) ctx.moveTo(x, y)
    else ctx.lineTo(x, y)
  }
  ctx.stroke()
  // Draw playback progress if previewing
  if (isPreviewPlaying.value && previewingSample.value === sampleId && sample.duration) {
    const playedWidth = width * progress
    ctx.fillStyle = 'rgba(158,127,255,0.3)'
    ctx.fillRect(0, 0, playedWidth, height)
  }
}

function animateWaveform(sampleId: string, audio: HTMLAudioElement) {
  const sample = sampleCategories.value.flatMap(cat => cat.samples).find(s => s.id === sampleId)
  if (!sample || !audio) return
  const animate = () => {
    if (!audio.paused && !audio.ended) {
      const progress = audio.currentTime / sample.duration
      drawWaveformForSample(sampleId, progress)
      waveformAnimationFrame.value[sampleId] = requestAnimationFrame(animate)
    } else {
      drawWaveformForSample(sampleId, 1)
      cancelAnimationFrame(waveformAnimationFrame.value[sampleId])
    }
  }
  animate()
}

onMounted(() => {
  // Load sample instruments from backend
  loadSampleInstruments()
  
  // Initialize waveforms for existing samples
  sampleCategories.value.forEach(cat => {
    cat.samples.forEach(sample => {
      if (sample.waveform && waveformCanvasRefs.value[sample.id]) {
        drawWaveformForSample(sample.id)
      }
    })
  })
})

watch(sampleCategories, (newCats) => {
  newCats.forEach(cat => {
    cat.samples.forEach(sample => {
      if (sample.waveform && waveformCanvasRefs.value[sample.id]) {
        drawWaveformForSample(sample.id)
      }
    })
  })
})

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
  max-width: 110px;
  width: 110px;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
  overflow: hidden;
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
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.track-name-input:focus {
  background: var(--background);
  outline: 1px solid var(--primary);
}

.track-instrument {
  font-size: 0.75rem;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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
  border: 2px solid var(--border);
  border-radius: 8px;
  padding: 1rem;
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  gap: 1rem;
  text-align: left;
  position: relative;
  min-height: 80px;
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

.instrument-card.selected .instrument-info h4,
.instrument-card.selected .instrument-info p,
.instrument-card.selected .sample-type-label,
.instrument-card.selected .synth-type-label {
  color: white;
}

.instrument-card.sample-based {
  border: 2px solid rgba(34, 197, 94, 0.3);
  background: linear-gradient(135deg, rgba(34, 197, 94, 0.1), rgba(34, 197, 94, 0.05));
}

.instrument-card.sample-based:hover {
  border-color: rgba(34, 197, 94, 0.5);
  background: linear-gradient(135deg, rgba(34, 197, 94, 0.15), rgba(34, 197, 94, 0.08));
}

.instrument-card.sample-based.selected {
  border-color: rgb(34, 197, 94);
  background: linear-gradient(135deg, rgba(34, 197, 94, 0.8), rgba(34, 197, 94, 0.6));
}

.instrument-card.synth-based {
  border: 2px solid rgba(168, 85, 247, 0.3);
  background: linear-gradient(135deg, rgba(168, 85, 247, 0.1), rgba(168, 85, 247, 0.05));
}

.instrument-card.synth-based:hover {
  border-color: rgba(168, 85, 247, 0.5);
  background: linear-gradient(135deg, rgba(168, 85, 247, 0.15), rgba(168, 85, 247, 0.08));
}

.instrument-card.synth-based.selected {
  border-color: rgb(168, 85, 247);
  background: linear-gradient(135deg, rgba(168, 85, 247, 0.8), rgba(168, 85, 247, 0.6));
}

.instrument-icon {
  position: relative;
  width: 48px;
  height: 48px;
  background: var(--surface);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all 0.2s ease;
}

.instrument-icon .icon {
  width: 24px;
  height: 24px;
  color: var(--text-secondary);
  transition: all 0.2s ease;
}

.instrument-card:hover .instrument-icon {
  background: var(--border);
}

.instrument-card.sample-based:hover .instrument-icon {
  background: rgba(34, 197, 94, 0.1);
}

.instrument-card.synth-based:hover .instrument-icon {
  background: rgba(168, 85, 247, 0.1);
}

.instrument-card.selected .instrument-icon {
  background: rgba(255, 255, 255, 0.2);
}

.instrument-card.selected .instrument-icon .icon {
  color: white;
}

.sample-badge {
  position: absolute;
  top: -6px;
  right: -6px;
  background: rgb(34, 197, 94);
  color: white;
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 10px;
  font-weight: 600;
  white-space: nowrap;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.instrument-info {
  flex: 1;
  min-width: 0;
}

.instrument-info h4 {
  font-size: 1rem;
  font-weight: 600;
  margin: 0 0 0.25rem 0;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.instrument-info p {
  font-size: 0.85rem;
  color: var(--text-secondary);
  margin: 0 0 0.5rem 0;
  line-height: 1.3;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.sample-type-label,
.synth-type-label {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  display: inline-block;
  padding: 2px 6px;
  border-radius: 4px;
  transition: all 0.2s ease;
}

.sample-type-label {
  color: rgb(34, 197, 94);
  background: rgba(34, 197, 94, 0.1);
}

.synth-type-label {
  color: rgb(168, 85, 247);
  background: rgba(168, 85, 247, 0.1);
}

.instrument-card.selected .sample-type-label,
.instrument-card.selected .synth-type-label {
  background: rgba(255, 255, 255, 0.2);
  color: white;
}

/* Sample Card Styles */
.samples-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 0.75rem;
}

.sample-card {
  background: var(--background);
  border: 2px solid var(--border);
  border-radius: 8px;
  padding: 0.75rem;
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  text-align: left;
  position: relative;
}

.sample-card:hover {
  border-color: var(--primary);
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
}

.sample-card.selected {
  border-color: var(--primary);
  background: var(--primary);
  color: white;
}

.sample-card.selected .sample-info h5,
.sample-card.selected .sample-info p {
  color: white;
}

.sample-info {
  flex: 1;
  min-width: 0;
}

.sample-info h5 {
  font-size: 0.9rem;
  font-weight: 600;
  margin: 0 0 0.25rem 0;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sample-info p {
  font-size: 0.75rem;
  color: var(--text-secondary);
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.play-sample-btn {
  width: 32px;
  height: 32px;
  border: none;
  background: var(--surface);
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s ease;
  flex-shrink: 0;
}

.play-sample-btn:hover {
  background: var(--primary);
  color: white;
}

.play-sample-btn .icon {
  width: 12px;
  height: 12px;
}

.sample-card.selected .play-sample-btn {
  background: rgba(255, 255, 255, 0.2);
}

.sample-card.selected .play-sample-btn:hover {
  background: rgba(255, 255, 255, 0.3);
}

/* Responsive Design */
@media (max-width: 768px) {
  .modal-content {
    width: 95vw;
    max-height: 90vh;
  }
  
  .instruments-grid {
    grid-template-columns: 1fr;
  }
  
  .samples-grid {
    grid-template-columns: 1fr;
  }
  
  .track-header {
    padding: 0.75rem;
  }
  
  .track-actions {
    gap: 0.5rem;
  }
  
  .sample-card {
    padding: 0.5rem;
    gap: 0.5rem;
  }
  
  .sample-info h5 {
    font-size: 0.8rem;
  }
  
  .sample-info p {
    font-size: 0.7rem;
  }
  
  .play-sample-btn {
    width: 28px;
    height: 28px;
  }
  
  .play-sample-btn .icon {
    width: 10px;
    height: 10px;
  }
}

/* Scrollbar Styling */
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

/* Modal Footer Styles */
.modal-footer {
  padding: 1.5rem;
  border-top: 1px solid var(--border);
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
  background: var(--surface);
  border-radius: 0 0 12px 12px;
}

.modal-footer .btn {
  padding: 0.75rem 1.5rem;
  border-radius: 8px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  border: none;
  font-size: 0.9rem;
  min-width: 80px;
}

.modal-footer .btn-secondary {
  background: var(--background);
  color: var(--text);
  border: 1px solid var(--border);
}

.modal-footer .btn-secondary:hover {
  background: var(--border);
}

.modal-footer .btn-primary {
  background: var(--primary);
  color: white;
}

.modal-footer .btn-primary:hover {
  background: var(--primary-dark, #0056b3);
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(0, 123, 255, 0.3);
}

.modal-footer .btn-primary:disabled {
  background: var(--border);
  color: var(--text-secondary);
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}
</style>
