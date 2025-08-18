<template>
  <div class="track-controls">
    <div class="controls-header">
      <div class="header-title">
        <Layers class="header-icon" />
        <h3>{{ $t('tracks.title') }}</h3>
      </div>
      
      <button class="btn btn-primary add-track-btn" @click="addNewTrack">
        <Plus class="icon" />
        {{ $t('tracks.addTrack') }}
      </button>
    </div>

    <div class="tracks-list">
      <div v-if="tracks.length === 0" class="empty-state">
        <Music class="empty-icon" />
        <p>{{ $t('tracks.empty') }}</p>
        <button class="btn btn-ghost" @click="addNewTrack">
          {{ $t('tracks.addFirst') }}
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
                  <div style="display:flex;align-items:center;gap:0.5rem;">
                    <span class="track-instrument">{{ getTrackInstrumentLabel(track) }}</span>
                  </div>
                </div>
                <div v-if="isVocalTrack(track) && selectedTrack === track.id" class="vocal-header-group" style="display:flex;align-items:center;gap:0.5rem;margin-left:8px;">
                  <!-- Header waveform/thumbnail removed: waveform should only appear in clip lane timeline to avoid duplication -->
                  <div v-if="micPermissionDenied" class="mic-warning" title="Microphone access is denied. Enable microphone in your browser settings to record.">
                    <span style="color: #ffb4; font-size:0.8rem; margin-left:6px;">Microphone access denied</span>
                  </div>
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
                  v-if="isVocalTrack(track)"
                  class="btn-icon"
                  :class="{ 'recording': isRecording[track.id] }"
                  @click.stop="toggleTrackRecording(track.id)"
                  :title="isRecording[track.id] ? 'Stop Recording' : (micPermissionDenied ? 'Microphone access denied' : 'Record')"
                  :disabled="micPermissionDenied && !isRecording[track.id]"
                >
                  <Mic class="icon" />
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
            
            <div v-if="selectedTrack === track.id" class="track-controls-section" @click.stop>
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

              <div v-if="isVocalTrack(track)" class="record-control" @click.stop>
                <div class="recording-status-section" v-if="isRecording[track.id] || micPermissionDenied">
                  <div v-if="isRecording[track.id]" class="recording-active">
                    <div class="recording-indicator">
                      <div class="record-led on"></div>
                      <span class="record-timer">Recording: {{ formatElapsed(recordingElapsedMap[track.id]) }}</span>
                    </div>
                  </div>
                  
                  <div v-if="micPermissionDenied" class="permission-warning">
                    <span>Microphone access denied. Enable in browser settings to record.</span>
                  </div>
                </div>
              </div>
            </div>
            
            <div v-if="selectedTrack === track.id" :key="`effects-${track.id}`" class="effects-section" @click.stop>
              <h4>Effects</h4>
              
              <!-- Voice Type Selector for Vocal Tracks -->
              <div v-if="isVocalTrack(track)" class="effect-control voice-type-control">
                <label>Voice Type</label>
                <select
                  :key="`voice-type-${track.id}`"
                  :value="track.vocalStyle || 'natural'"
                  @change="updateTrackVoiceType(track.id, ($event.target as HTMLSelectElement).value)"
                  class="voice-type-selector"
                >
                  <option value="natural">Natural</option>
                  <option value="choir">Choir</option>
                  <option value="robot">Robot</option>
                  <option value="echo">Echo</option>
                  <option value="squirrel">Squirrel</option>
                  <option value="alien">Alien</option>
                  <option value="telephone">Telephone</option>
                </select>
              </div>
              
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
              
              <!-- Extended Vocal Effects (visible for all tracks but optimized for vocals) -->
              <div class="effect-control">
                <label>Pitch Shift</label>
                <input 
                  :key="`pitchShift-${track.id}`"
                  type="range" 
                  min="-12" 
                  max="12" 
                  step="1"
                  :value="track.effects.pitchShift || 0"
                  @input="updateTrackEffect(track.id, 'pitchShift', getInputValue($event))"
                  class="slider"
                />
                <span>{{ (track.effects.pitchShift || 0) > 0 ? '+' : '' }}{{ track.effects.pitchShift || 0 }} semi</span>
              </div>
              
              <div class="effect-control">
                <label>Chorus</label>
                <input 
                  :key="`chorus-${track.id}`"
                  type="range" 
                  min="0" 
                  max="1" 
                  step="0.01"
                  :value="track.effects.chorus || 0"
                  @input="updateTrackEffect(track.id, 'chorus', getInputValue($event))"
                  class="slider"
                />
                <span>{{ Math.round((track.effects.chorus || 0) * 100) }}%</span>
              </div>
              
              <div class="effect-control">
                <label>Filter</label>
                <input 
                  :key="`filter-${track.id}`"
                  type="range" 
                  min="0" 
                  max="1" 
                  step="0.01"
                  :value="track.effects.filter || 0"
                  @input="updateTrackEffect(track.id, 'filter', getInputValue($event))"
                  class="slider"
                />
                <span>{{ Math.round((track.effects.filter || 0) * 100) }}%</span>
              </div>
              
              <div class="effect-control">
                <label>Bit Crush</label>
                <input 
                  :key="`bitcrush-${track.id}`"
                  type="range" 
                  min="0" 
                  max="1" 
                  step="0.01"
                  :value="track.effects.bitcrush || 0"
                  @input="updateTrackEffect(track.id, 'bitcrush', getInputValue($event))"
                  class="slider"
                />
                <span>{{ Math.round((track.effects.bitcrush || 0) * 100) }}%</span>
              </div>
            </div>
          </div>
        </div>
      </template>
    </div>

    <!-- Instrument/Sample Selection Modal -->
    <div v-if="showInstrumentSelector" class="modal-overlay" @click="closeInstrumentSelector">
      <div class="modal-content" @click.stop>
        <div class="modal-header">            <h3>Select Instrument or Sample</h3>
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
            <button
              class="tab-btn"
              :class="{ 'active': activeTab === 'vocals' }"
              @click="() => { activeTab = 'vocals'; selectedInstrumentValue = 'vocals' }"
            >
              <Mic class="icon" />
              Vocals
            </button>
          </div>
          
          <div class="selection-content">
            <!-- Instruments Tab -->
            <div v-if="activeTab === 'instruments'" class="instruments-categories-list">
              <template v-if="instrumentsByCategory.length">
                <div v-for="group in instrumentsByCategory" :key="group.name" class="instrument-category-group" style="margin-bottom: 1.5em;">
                  <div class="category-header" @click="toggleCategory(group.name)">
                    <component :is="getCategoryIcon(group.name)" class="category-icon" />
                    <span class="category-name">{{ group.name }}</span>
                    <span class="instrument-count">({{ group.instruments.length }})</span>
                    <component :is="expandedCategory === group.name ? ChevronDown : ChevronRight" class="chevron-icon" />
                  </div>
                  <transition name="fade">
                    <div v-if="expandedCategory === group.name" class="category-instruments-grid">
                      <div
                        v-for="instrument in group.instruments"
                        :key="instrument.value"
                        class="instrument-card"
                        :class="{ 'selected': selectedInstrumentValue === instrument.value }"
                        @click="selectInstrument(instrument.value)"
                      >
                        <div class="instrument-header">
                          <div class="instrument-icon">
                            <component :is="getInstrumentIcon(instrument.value || instrument.name)" class="icon" />
                          </div>
                          <div class="instrument-info">
                            <h4 class="instrument-name">{{ instrument.name || instrument.display_name }}</h4>
                            <p class="instrument-description">{{ instrument.description }}</p>
                          </div>
                        </div>
                      </div>
                    </div>
                  </transition>
                </div>
              </template>
              <div v-else class="empty-instruments-message" style="padding:2em;text-align:center;color:#888;">
                No instruments found in any category.
              </div>
            </div>
            
            <!-- Samples Tab -->
            <div v-if="activeTab === 'samples'" class="samples-section">
              <div v-if="sampleCategories.length === 0" class="empty-samples-state">
                <FileAudio class="empty-icon" />
                <h4>No samples available</h4>
                <p>Load samples in the Sample Library to use them here</p>
              </div>
              
              <div v-else class="samples-categories-list">
                <div v-for="category in sampleCategories" :key="category.name" class="sample-category-group">
                  <div class="category-header" @click="toggleSampleCategory(category.name)">
                    <component :is="getSampleIcon(category.name)" class="category-icon" />
                    <span class="category-name">{{ category.name }}</span>
                    <span class="sample-count">({{ category.samples.length }})</span>
                    <component :is="expandedSampleCategory === category.name ? ChevronDown : ChevronRight" class="chevron-icon" />
                  </div>
                  
                  <transition name="fade">
                    <div v-if="expandedSampleCategory === category.name" class="category-samples-grid">
                      <div
                        v-for="sample in category.samples"
                        :key="sample.id"
                        class="sample-card"
                        :class="{ 'selected': selectedInstrumentValue === sample.id }"
                        @click="selectSample(sample)"
                      >
                        <div class="sample-header">
                          <div class="sample-icon">
                            <component :is="getSampleIcon(category.name)" class="icon" />
                          </div>

                          <div class="sample-waveform" v-if="sample.waveform && sample.waveform.length">
                            <canvas 
                              :ref="el => setWaveformCanvasRef(el, sample.id)"
                              class="waveform-canvas"
                              :width="120"
                              :height="32"
                            ></canvas>
                          </div>

                          <div class="sample-actions">
                            <button 
                              class="action-btn play-btn"
                              @click.stop="previewSample(sample)"
                              :disabled="isPreviewPlaying && previewingSample !== sample.id"
                            >
                              <Play v-if="!isPreviewPlaying || previewingSample !== sample.id" class="icon" />
                              <Square v-else class="icon" />
                            </button>
                          </div>
                        </div>

                        <div class="sample-info">
                          <h4 class="sample-name" :title="sample.name">{{ sample.name }}</h4>
                          <div class="sample-meta">
                            <span class="duration">{{ formatDuration(sample.duration) }}</span>
                            <span v-if="sample.bpm" class="bpm">{{ sample.bpm }} BPM</span>
                          </div>
                          <div v-if="sample.tags && sample.tags.length" class="sample-tags">
                            <span 
                              v-for="tag in sample.tags.slice(0, 3)" 
                              :key="tag" 
                              class="tag"
                            >
                              {{ tag }}
                            </span>
                            <span v-if="sample.tags.length > 3" class="tag-more">
                              +{{ sample.tags.length - 3 }}
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </transition>
                </div>
              </div>
            </div>
            
            <div v-if="activeTab === 'vocals'" class="vocals-section" style="padding:1rem;">
              <h4>Select vocal processing style</h4>
              <div style="display:flex;gap:0.75rem;margin-top:1rem;flex-wrap:wrap;">
                <div
                  v-for="style in vocalStyles"
                  :key="style"
                  class="instrument-card"
                  :class="{ 'selected': selectedVocalStyle === style }"
                  @click="() => { selectedVocalStyle = style; selectedInstrumentValue = 'vocals' }"
                  style="min-width:160px;"
                >
                  <div class="instrument-header">
                    <div class="instrument-icon"><Mic class="icon" /></div>
                    <div class="instrument-info">
                      <h4 class="instrument-name">{{ style.charAt(0).toUpperCase() + style.slice(1) }}</h4>
                      <p class="instrument-description">{{ getVoiceTypeDescription(style) }}</p>
                    </div>
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
import { useCountdown } from '../composables/useCountdown'
import { useSampleStore } from '../stores/sampleStore'
import { getSampleInstruments, getAllSampleInstruments } from '../utils/api'
import { 
  Layers, Plus, Music, Volume2, VolumeX, Headphones, Trash2,
  Piano, Drum, Guitar, Mic, Zap, X, FileAudio, Play, Square, 
  ChevronDown, ChevronRight
} from 'lucide-vue-next'

const audioStore = useAudioStore()
const { startCountdown } = useCountdown()
const sampleStore = useSampleStore()
const selectedTrack = ref<string | null>(null)
const showInstrumentSelector = ref(false)
const selectedTrackForInstrument = ref<string | null>(null)
const activeTab = ref<'instruments' | 'samples' | 'vocals'>('instruments')
const selectedInstrumentValue = ref<string>('')
const vocalStyles = ['natural', 'choir', 'robot', 'echo', 'squirrel', 'alien', 'telephone']
const selectedVocalStyle = ref<string>('natural')
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

// All sample instruments grouped by category
const allSampleInstruments = ref<{ name: string, instruments: any[] }[]>([])

interface InstrumentOption {
  name: string
  value: string
  description: string
  type: string
  chord_count?: number
  category?: string // Added for grouping
}

// Combined available instruments (sample-based + synthesized)
const availableInstruments = computed((): InstrumentOption[] => {
  const instruments: InstrumentOption[] = []
  
  // Add sample-based instruments from the loaded sample instruments
  for (const instrument of sampleInstruments.value) {
    instruments.push({
      name: instrument.display_name || instrument.name,
      value: instrument.name,
      description: `Sample-based ${instrument.display_name || instrument.name} with ${instrument.chord_count} chords`,
      type: 'sample',
      chord_count: instrument.chord_count,
      category: instrument.category || 'Other' // Assign category if present
    })
  }
  
  // Add synthesized instruments
  const synthInstruments = [
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
    },
    { 
      name: 'Bass', 
      value: 'bass', 
      description: 'Deep bass synthesizer',
      type: 'synth'
    },
    { 
      name: 'Drums', 
      value: 'drums', 
      description: 'Electronic drum machine',
      type: 'synth'
    }
  ]
  
  instruments.push(...synthInstruments)
  
  return instruments
})

// Group instruments by category for display in the selector
const instrumentsByCategory = computed(() => allSampleInstruments.value)

// Load sample instruments on component mount
const loadSampleInstruments = async (category = 'default') => {
  try {
    console.log('Loading sample instruments for category:', category)
    const response = await getSampleInstruments(category)
    console.log('Raw response:', response)
    sampleInstruments.value = response.instruments || []
    console.log('Loaded sample instruments:', sampleInstruments.value)
    console.log('Available instruments now:', availableInstruments.value)
  } catch (error) {
    console.error('Failed to load sample instruments:', error)
    // Fallback to mock sample instruments for testing
    sampleInstruments.value = [
      {
        name: 'guitar',
        display_name: 'Guitar',
        chord_count: 108,
        available_chords: ['C_major', 'D_major', 'E_major']
      },
      {
        name: 'piano',
        display_name: 'Piano',
        chord_count: 108,
        available_chords: ['C_major', 'D_major', 'E_major']
      }
    ]
    console.log('Using fallback sample instruments:', sampleInstruments.value)
  }
}

// Load all sample instruments for the selector
const loadAllSampleInstruments = async () => {
  try {
    const response = await getAllSampleInstruments()
    console.log('All sample instruments response:', response)
    // Convert response.categories (object) to array for easier rendering
    allSampleInstruments.value = Object.entries(response.categories).map(([name, instruments]) => ({ name, instruments: (instruments as any[]).map(inst => ({ ...inst, value: inst.value || inst.name })) }))
  } catch (error) {
    console.error('Failed to load all sample instruments:', error)
    allSampleInstruments.value = []
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

const getCategoryIcon = (category: string) => {
  const iconMap: Record<string, any> = {
    'Drums': Drum,
    'Percussion': Drum,
    'Bass': Guitar,
    'Guitar': Guitar,
    'Piano': Piano,
    'Keys': Piano,
    'Synth': Zap,
    'Strings': Music,
    'Vocals': Mic,
    'Voice': Mic,
    'Other': Music
  }
  // fallback: capitalize and match
  const key = Object.keys(iconMap).find(k => category.toLowerCase().includes(k.toLowerCase()))
  return key ? iconMap[key] : Music
}

const getInstrumentIcon = (instrument: string) => {
  const iconMap: Record<string, any> = {
    'piano': Piano,
    'electric-piano': Piano,
    'drums': Drum,
    'bass': Guitar,
    'electric-guitar': Guitar,
    'acoustic-guitar': Guitar,
    'guitar': Guitar,
    'synth-lead': Zap,
    'synth-pad': Zap,
    'vocals': Mic,
    'voice': Mic,
    'strings': Music
  }
  // fallback: capitalize and match
  const key = Object.keys(iconMap).find(k => instrument.toLowerCase().includes(k.toLowerCase()))
  return key ? iconMap[key] : Music
}

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

const getTrackInstrumentLabel = (track: any): string => {
  const baseName = getInstrumentDisplayName(track.instrument)
  
  // For vocal tracks, append the voice type if available
  if (isVocalTrack(track) && track.vocalStyle) {
    const vocalType = track.vocalStyle.charAt(0).toUpperCase() + track.vocalStyle.slice(1)
    return `${baseName} (${vocalType})`
  }
  
  return baseName
}

const getVoiceTypeDescription = (voiceType: string): string => {
  const descriptions = {
    natural: 'Clean, unprocessed vocal',
    choir: 'Spacious reverb with chorus',
    robot: 'Distorted robotic vocoder',
    echo: 'Heavy delay and reverb',
    squirrel: 'High-pitched chipmunk effect',
    alien: 'Otherworldly sci-fi voice',
    telephone: 'Lo-fi compressed phone sound'
  }
  
  return descriptions[voiceType as keyof typeof descriptions] || 'Voice effect'
}

// Helper to decide whether a track is a vocal track (support 'vocals', 'voice', or category 'vocals')
const isVocalTrack = (track: any): boolean => {
  if (!track) return false
  const inst = (track.instrument || '').toString().toLowerCase()
  if (inst === 'vocals' || inst === 'voice' || inst.includes('vocal')) return true
  if (track.category && track.category.toString().toLowerCase() === 'vocals') return true
  return false
}

// Debug logging utility
function debugLog(...args: any[]) {
  if (process.env.NODE_ENV !== 'production') {
    // eslint-disable-next-line no-console
    console.debug('[TrackControls]', ...args)
  }
}

// Format duration in seconds to MM:SS format
const formatDuration = (duration: number): string => {
  if (!duration || isNaN(duration)) return '0:00'
  const minutes = Math.floor(duration / 60)
  const seconds = Math.floor(duration % 60)
  return `${minutes}:${seconds.toString().padStart(2, '0')}`
}

// Build a downsampled waveform preview from accumulated RMS samples
function buildPreviewWaveform(samples: number[], length: number) {
  if (!samples || samples.length === 0) return []
  const out: number[] = []
  const step = Math.max(1, Math.floor(samples.length / length))
  for (let i = 0; i < samples.length; i += step) {
    // average over the step window
    let sum = 0
    let count = 0
    for (let j = i; j < i + step && j < samples.length; j++) {
      sum += samples[j]
      count++
    }
    out.push(count ? sum / count : 0)
    if (out.length >= length) break
  }
  // if too short, pad with zeros
  while (out.length < length) out.push(0)
  return out
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
    let instrumentCategory: string | undefined
    
    // If it's a sample, use sample name
    for (const category of sampleCategories.value) {
      const sample = category.samples.find((s: any) => s.id === selectedInstrumentValue.value)
      if (sample) instrumentName = sample.name
    }
    
    // Find the category from allSampleInstruments
    for (const category of allSampleInstruments.value) {
      const instrument = category.instruments.find((inst: any) => inst.name === selectedInstrumentValue.value || inst.value === selectedInstrumentValue.value)
      if (instrument) {
        instrumentCategory = category.name.toLowerCase()
        break
      }
    }
    
    let trackId: string | null = null
    if (selectedInstrumentValue.value === 'vocals') {
      trackId = audioStore.addTrack(`New ${instrumentName}`, 'vocals', undefined, 'vocals')
      if (trackId) {
        audioStore.updateTrack(trackId, { vocalStyle: selectedVocalStyle.value })
      }
    } else {
      trackId = audioStore.addTrack(`New ${instrumentName}`, selectedInstrumentValue.value, undefined, instrumentCategory)
    }
    debugLog('Added new track', { trackId, instrument: selectedInstrumentValue.value, category: instrumentCategory })
    if (trackId) {
      selectedTrack.value = trackId
    }
    closeInstrumentSelector()
    return
  }
  // Otherwise, update existing track
  let instrumentCategory: string | undefined
  
  // Find the category from allSampleInstruments
  for (const category of allSampleInstruments.value) {
    const instrument = category.instruments.find((inst: any) => inst.name === selectedInstrumentValue.value || inst.value === selectedInstrumentValue.value)
    if (instrument) {
      instrumentCategory = category.name.toLowerCase()
      break
    }
  }
  
  if (selectedInstrumentValue.value === 'vocals') {
    audioStore.updateTrack(selectedTrackForInstrument.value, { instrument: 'vocals', category: 'vocals', vocalStyle: selectedVocalStyle.value })
  } else {
    audioStore.updateTrack(selectedTrackForInstrument.value, {
      instrument: selectedInstrumentValue.value,
      category: instrumentCategory
    })
  }
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
  console.log('Component mounted, loading sample instruments...')
  loadSampleInstruments()
  loadAllSampleInstruments()
  
  // Initialize waveforms for existing samples
  sampleCategories.value.forEach(cat => {
    cat.samples.forEach(sample => {
      if (sample.waveform && waveformCanvasRefs.value[sample.id]) {
        drawWaveformForSample(sample.id)
      }
    })
  })

  // Non-blocking check for microphone permission; keeps UI in sync if denied
  try {
    const perms = (navigator as any).permissions
    if (perms && typeof perms.query === 'function') {
      perms.query({ name: 'microphone' }).then((res: any) => {
        micPermissionDenied.value = res.state === 'denied'
        res.onchange = () => {
          micPermissionDenied.value = res.state === 'denied'
        }
      }).catch(() => {
        // ignore permission API failures (some browsers may not support it)
      })
    }
  } catch (e) {
    // ignore
  }
})

watch(sampleCategories, (newCats) => {
  newCats.forEach(cat => {
    cat.samples.forEach(sample => {
      if (sample.waveform && waveformCanvasRefs.value[sample.id]) {
        drawWaveformForSample(sample.id)
      }
    })
  })
  
  // Auto-expand first category if none is expanded and categories exist
  if (newCats.length > 0 && !expandedSampleCategory.value) {
    expandedSampleCategory.value = newCats[0].name
  }
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

const updateTrackVoiceType = (trackId: string, voiceType: string) => {
  const track = tracks.value.find(t => t.id === trackId)
  if (track && isVocalTrack(track)) {
    // Apply voice effect preset with all extended effects
    const effectsPreset = getVoiceEffectPreset(voiceType)
    
    // Update both the vocal style and the effects
    audioStore.updateTrack(trackId, { 
      vocalStyle: voiceType,
      effects: {
        reverb: effectsPreset.reverb,
        delay: effectsPreset.delay,
        distortion: effectsPreset.distortion,
        pitchShift: effectsPreset.pitchShift,
        chorus: effectsPreset.chorus,
        filter: effectsPreset.filter,
        bitcrush: effectsPreset.bitcrush
      }
    })
    
    // Also update the effects bus directly to ensure immediate application
    audioStore.updateTrackEffects(trackId, {
      reverb: effectsPreset.reverb,
      delay: effectsPreset.delay,
      distortion: effectsPreset.distortion,
      pitchShift: effectsPreset.pitchShift,
      chorus: effectsPreset.chorus,
      filter: effectsPreset.filter,
      bitcrush: effectsPreset.bitcrush
    })
    
    // Visual feedback - briefly show that effects are being applied
    console.log(`🎤 Applied ${voiceType} voice preset:`, effectsPreset)
    
    // Debug: Check if pitch shift is actually being set
    console.log(`🔊 Voice Effect Debug:`, {
      voiceType,
      pitchShift: effectsPreset.pitchShift,
      pitchShiftCents: effectsPreset.pitchShift * 100,
      allEffects: effectsPreset
    })
  }
}

// Voice effect presets based on GarageBand vocal effects with extended effects
const getVoiceEffectPreset = (voiceType: string) => {
  const presets = {
    natural: {
      reverb: 0.02,      // Very minimal reverb for natural sound
      delay: 0,          // No delay
      distortion: 0,     // No distortion
      pitchShift: 0,     // No pitch change
      chorus: 0,         // No chorus
      filter: 0,         // No filtering
      bitcrush: 0        // No bit crushing
    },
    choir: {
      reverb: 0.45,      // High reverb for spacious choir sound
      delay: 0.18,       // Light delay for chorus effect  
      distortion: 0,     // No distortion
      pitchShift: 0,     // No pitch change
      chorus: 0.4,       // Medium chorus for layered effect
      filter: 0,         // No filtering
      bitcrush: 0        // No bit crushing
    },
    robot: {
      reverb: 0.15,      // Light reverb for space
      delay: 0.08,       // Minimal delay for texture
      distortion: 0.85,  // Very high distortion for robotic sound
      pitchShift: -4,    // Pitch down for deeper robot voice
      chorus: 0.4,       // Medium chorus for thickness
      filter: 0.7,       // Heavy filtering for robotic tone
      bitcrush: 0.8      // Very high bit crushing for digital artifacts
    },
    echo: {
      reverb: 0.35,      // Medium-high reverb
      delay: 0.6,        // High delay for strong echo effect
      distortion: 0,     // No distortion
      pitchShift: 0,     // No pitch change
      chorus: 0.1,       // Light chorus
      filter: 0.1,       // Light filtering for atmosphere
      bitcrush: 0        // No bit crushing
    },
    squirrel: {
      reverb: 0.08,      // Minimal reverb
      delay: 0.15,       // Light delay for texture
      distortion: 0.25,  // Light distortion to enhance high frequencies
      pitchShift: 12,    // Very high pitch shift (+1 octave) for strong chipmunk effect
      chorus: 0.35,      // Medium chorus for fullness
      filter: 0,         // No additional filtering (let high frequencies through)
      bitcrush: 0.1      // Very light bit crushing for character
    },
    alien: {
      reverb: 0.28,      // Medium reverb for otherworldly feel
      delay: 0.25,       // Medium delay with rhythm
      distortion: 0.5,   // Medium-high distortion for alien effect
      pitchShift: -8,    // Much lower pitch for deep alien voice
      chorus: 0.3,       // Medium chorus
      filter: 0.4,       // Medium filtering for alien tone
      bitcrush: 0.3      // Medium bit crushing for sci-fi artifacts
    },
    telephone: {
      reverb: 0,         // No reverb for lo-fi sound
      delay: 0,          // No delay
      distortion: 0.25,  // Light distortion for compressed/filtered sound
      pitchShift: 0,     // No pitch change
      chorus: 0,         // No chorus
      filter: 0.7,       // High filtering for telephone bandwidth
      bitcrush: 0.5      // Medium bit crushing for lo-fi compression
    }
  }
  
  return presets[voiceType as keyof typeof presets] || presets.natural
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

const expandedCategory = ref<string | null>(null)
const expandedSampleCategory = ref<string | null>(null)

const toggleCategory = (name: string) => {
  expandedCategory.value = expandedCategory.value === name ? null : name
}

const toggleSampleCategory = (name: string) => {
  expandedSampleCategory.value = expandedSampleCategory.value === name ? null : name
}

// Recording state for vocal track recording
const isRecording = ref<Record<string, boolean>>({})
// When microphone permission is explicitly denied, we disable record controls and show a hint
const micPermissionDenied = ref(false)
const mediaRecorderMap = new Map<string, MediaRecorder>()
// Keep the raw MediaStream so we can always stop tracks even if MediaRecorder doesn't expose it
const recordingStreamMap = new Map<string, MediaStream>()
const recordingChunksMap = new Map<string, BlobPart[]>()
const recordingStartTimeMap = new Map<string, number>()
// Track the clip id created when starting a recording so we can update it on stop
const recordingClipIdMap = new Map<string, string>()
// For live waveform drawing during recording (we only accumulate samples; waveform renders in timeline clip)
const analyserMap = new Map<string, AnalyserNode>()
const audioContextMap = new Map<string, AudioContext>()
const recordingAnimationFrame = new Map<string, number>()
const recordingSampleBuffer = new Map<string, number[]>()
// Elapsed timer per recording
const recordingElapsedMap = ref<Record<string, number>>({})
const recordingTimerInterval = new Map<string, number>()
// Interval ids used to periodically update the placeholder clip while recording
const recordingPlaceholderUpdateInterval = new Map<string, number>()
// No header thumbnail canvases; waveform thumbnails are rendered in timeline clip

const toggleTrackRecording = async (trackId: string) => {
  if (isRecording.value[trackId]) {
    await stopRecordingForTrack(trackId)
    return
  }

  // If we already know permission is denied, avoid attempting to start and keep UI disabled
  if (micPermissionDenied.value) {
    // Keep this lightweight; UI shows tooltip and disabled state. Log for debugging.
    console.warn('Microphone permission denied; cannot start recording for', trackId)
    return
  }

  await startRecordingForTrack(trackId)
}

const startRecordingForTrack = async (trackId: string) => {
  try {
    // Wait for centralized countdown with beeps
    await startCountdown(4)

  const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
  // store the stream so stop can always terminate tracks
  recordingStreamMap.set(trackId, stream)
    const audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)()
    audioContextMap.set(trackId, audioCtx)
    const source = audioCtx.createMediaStreamSource(stream)
    const analyser = audioCtx.createAnalyser()
    analyser.fftSize = 2048
    source.connect(analyser)
    analyserMap.set(trackId, analyser)

    // start accumulating samples for waveform preview; the timeline will draw the waveform from these samples
    recordingSampleBuffer.set(trackId, [])
    const drawLoop = () => {
      const a = analyserMap.get(trackId)
      if (!a) return
      const bufferLength = a.fftSize
      const dataArray = new Uint8Array(bufferLength)
      a.getByteTimeDomainData(dataArray)
      let rms = 0
      for (let i = 0; i < bufferLength; i++) {
        const v = (dataArray[i] - 128) / 128.0
        rms += v * v
      }
      rms = Math.sqrt(rms / bufferLength)
      // accumulate sample for waveform preview
      const buf = recordingSampleBuffer.get(trackId) || []
      buf.push(rms)
      recordingSampleBuffer.set(trackId, buf)

      const id = requestAnimationFrame(drawLoop)
      recordingAnimationFrame.set(trackId, id)
    }
    drawLoop()

  const recorder = new MediaRecorder(stream)
    mediaRecorderMap.set(trackId, recorder)
    recordingChunksMap.set(trackId, [])
    recordingStartTimeMap.set(trackId, audioStore.currentTime || 0)

    // Create a placeholder clip at the playhead so UI/timeline shows a clip while recording
    try {
      const placeholderClip: any = {
        startTime: recordingStartTimeMap.get(trackId) || 0,
        duration: 0.001,
        type: 'lyrics',
        instrument: 'vocals',
        sampleUrl: '',
        volume: 0.8,
        effects: { reverb: 0, delay: 0, distortion: 0 },
        waveform: []
      }
      const createdId = audioStore.addClip(trackId, placeholderClip)
      if (createdId) {
        recordingClipIdMap.set(trackId, createdId)
        // Periodically update the placeholder clip so the timeline shows a live waveform and growing duration
        const updateInterval = window.setInterval(() => {
          try {
            const clipId = recordingClipIdMap.get(trackId)
            if (!clipId) return
            const samples = recordingSampleBuffer.get(trackId) || []
            const preview = buildPreviewWaveform(samples, 128)
            const elapsed = recordingElapsedMap.value[trackId] || 0
            audioStore.updateClip(trackId, clipId, {
              waveform: preview,
              duration: Math.max(0.001, +(elapsed).toFixed(3))
            })
          } catch (e) {
            // ignore transient update errors
          }
        }, 500)
        recordingPlaceholderUpdateInterval.set(trackId, updateInterval as unknown as number)
      }
    } catch (e) {
      console.warn('Could not create placeholder clip at recording start', e)
    }

    // Start elapsed timer
    recordingElapsedMap.value = { ...recordingElapsedMap.value, [trackId]: 0 }
    const intervalId = window.setInterval(() => {
      const cur = recordingElapsedMap.value[trackId] || 0
      recordingElapsedMap.value = { ...recordingElapsedMap.value, [trackId]: +(cur + 0.1).toFixed(1) }
    }, 100)
    recordingTimerInterval.set(trackId, intervalId)

    recorder.ondataavailable = (e) => {
      if (!recordingChunksMap.has(trackId)) return
      recordingChunksMap.get(trackId)!.push(e.data)
    }

  recorder.onstop = async () => {
      const chunks = recordingChunksMap.get(trackId) || []
      const blob = new Blob(chunks, { type: 'audio/webm' })
      const url = URL.createObjectURL(blob)

      // Measure duration
      const audio = new Audio(url)
      await new Promise<void>((resolve) => {
        audio.onloadedmetadata = () => resolve()
        audio.onerror = () => resolve()
      })
      const duration = isNaN(audio.duration) ? 0 : audio.duration
      const startTime = recordingStartTimeMap.get(trackId) || audioStore.currentTime || 0

      // Build waveform summary from recorded samples
      const waveformSamples = recordingSampleBuffer.get(trackId) || []
      // Update the placeholder clip created at recording start
      const existingClipId = recordingClipIdMap.get(trackId)
      if (existingClipId) {
        audioStore.updateClip(trackId, existingClipId, {
          startTime,
          duration,
          type: 'sample',
          sampleUrl: url,
          sampleDuration: duration,
          waveform: waveformSamples,
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
        })
      } else {
        // Fallback: add clip if placeholder wasn't created
        const clip: any = {
          startTime,
          duration,
          type: 'sample',
          instrument: 'vocals',
          sampleUrl: url,
          sampleDuration: duration,
          volume: 0.8,
          effects: { reverb: 0, delay: 0, distortion: 0 },
          waveform: waveformSamples
        }
        audioStore.addClip(trackId, clip)
      }
      recordingClipIdMap.delete(trackId)

  // cleanup
      recordingChunksMap.delete(trackId)
      recordingStartTimeMap.delete(trackId)
      mediaRecorderMap.delete(trackId)
      // stop analyser animation and audio context
      const afId = recordingAnimationFrame.get(trackId)
      if (afId) cancelAnimationFrame(afId)
      recordingAnimationFrame.delete(trackId)
      const audioCtx = audioContextMap.get(trackId)
      if (audioCtx) {
        try { audioCtx.close() } catch (e) { /* ignore */ }
        audioContextMap.delete(trackId)
      }
      analyserMap.delete(trackId)
  // clear placeholder update interval if present
  const placeholderInterval = recordingPlaceholderUpdateInterval.get(trackId)
  if (placeholderInterval) clearInterval(placeholderInterval)
  recordingPlaceholderUpdateInterval.delete(trackId)
      // stop elapsed timer
      const interval = recordingTimerInterval.get(trackId)
      if (interval) clearInterval(interval)
      recordingTimerInterval.delete(trackId)

      // Thumbnail drawing removed: waveform and thumbnails are rendered in the timeline clip only


// thumbnail helper removed; header canvases removed — waveform rendered in timeline clip
      recordingSampleBuffer.delete(trackId)
      recordingElapsedMap.value = { ...recordingElapsedMap.value, [trackId]: 0 }
      isRecording.value = { ...isRecording.value, [trackId]: false }
    }

    recorder.start()
    isRecording.value = { ...isRecording.value, [trackId]: true }
  } catch (error) {
    console.warn('Failed to start recording:', error)
  }
}

// header canvas helpers removed

function formatElapsed(seconds: number | undefined) {
  if (!seconds || isNaN(seconds)) return '0.0s'
  return `${seconds.toFixed(1)}s`
}

// removed duplicate setThumbnailCanvasRef

// No header canvas refs or assignment helpers — header canvases removed so waveform drawn only in timeline clip

const stopRecordingForTrack = async (trackId: string) => {
  const recorder = mediaRecorderMap.get(trackId)
  const stream = recordingStreamMap.get(trackId)

  // Always try to stop the MediaRecorder if it exists and is active
  try {
    if (recorder && recorder.state !== 'inactive') {
  console.log('[record] stopping recorder for', trackId)
  recorder.stop()
    }
  } catch (e) {
    console.warn('Error stopping MediaRecorder for', trackId, e)
  }

  // Always stop any live MediaStream tracks so microphone is released
  try {
    if (stream) {
      stream.getTracks().forEach(t => t.stop())
    } else {
      // Fallback: some browsers don't expose stream on recorder; attempt to read it
      const maybeStream = (recorder as any)?.stream as MediaStream | undefined
      if (maybeStream) maybeStream.getTracks().forEach(t => t.stop())
    }
  } catch (e) {
    console.warn('Error stopping media tracks for', trackId, e)
  }

  // If recorder was missing or didn't trigger onstop for some reason, perform cleanup to reset UI and free resources.
  // Setup a fallback: if recorder.onstop isn't invoked within 2s, force cleanup
  let onstopTriggered = false
  const origOnstop = recorder ? (recorder as any).onstop : null
  if (recorder) {
    (recorder as any).onstop = async function (ev: any) {
      onstopTriggered = true
      try { if (origOnstop) await origOnstop.call(this, ev) } catch (e) { /* ignore */ }
    }
  }

  const fallbackTimer = window.setTimeout(() => {
    if (!onstopTriggered) {
      console.warn('[record] fallback cleanup triggered for', trackId)
      // run cleanup path below as if recorder was missing
      runForcedCleanup(trackId)
    }
  }, 2000)

  if (!recorder) {
    // Cancel animation frame
    const afId = recordingAnimationFrame.get(trackId)
    if (afId) cancelAnimationFrame(afId)
    recordingAnimationFrame.delete(trackId)

    // Close audio context
    const audioCtx = audioContextMap.get(trackId)
    if (audioCtx) {
      try { audioCtx.close() } catch (e) { /* ignore */ }
      audioContextMap.delete(trackId)
    }
    analyserMap.delete(trackId)

    // Clear placeholder update interval
    const placeholderInterval = recordingPlaceholderUpdateInterval.get(trackId)
    if (placeholderInterval) clearInterval(placeholderInterval)
    recordingPlaceholderUpdateInterval.delete(trackId)

    // Stop elapsed timer
    const interval = recordingTimerInterval.get(trackId)
    if (interval) clearInterval(interval)
    recordingTimerInterval.delete(trackId)

    // Remove any accumulated buffers
    recordingSampleBuffer.delete(trackId)

    // If a placeholder clip exists, remove it (we couldn't finalize a recording)
    const placeholderClipId = recordingClipIdMap.get(trackId)
    if (placeholderClipId) {
      try { audioStore.removeClip(trackId, placeholderClipId) } catch (e) { /* ignore */ }
      recordingClipIdMap.delete(trackId)
    }

    // Clear maps for chunks/startTime/stream
    recordingChunksMap.delete(trackId)
    recordingStartTimeMap.delete(trackId)
    recordingStreamMap.delete(trackId)

    // Ensure UI reflects stopped state
    recordingElapsedMap.value = { ...recordingElapsedMap.value, [trackId]: 0 }
    isRecording.value = { ...isRecording.value, [trackId]: false }
    if (fallbackTimer) clearTimeout(fallbackTimer)
  }

  // helper to force cleanup if onstop never fires
  function runForcedCleanup(trackId: string) {
    try {
      const afId = recordingAnimationFrame.get(trackId)
      if (afId) cancelAnimationFrame(afId)
      recordingAnimationFrame.delete(trackId)

      const audioCtx = audioContextMap.get(trackId)
      if (audioCtx) { try { audioCtx.close() } catch (e) {} audioContextMap.delete(trackId) }
      analyserMap.delete(trackId)

      const placeholderInterval = recordingPlaceholderUpdateInterval.get(trackId)
      if (placeholderInterval) clearInterval(placeholderInterval)
      recordingPlaceholderUpdateInterval.delete(trackId)

      const interval = recordingTimerInterval.get(trackId)
      if (interval) clearInterval(interval)
      recordingTimerInterval.delete(trackId)

      recordingSampleBuffer.delete(trackId)
      const placeholderClipId = recordingClipIdMap.get(trackId)
      if (placeholderClipId) {
        try { audioStore.removeClip(trackId, placeholderClipId) } catch (e) { /* ignore */ }
        recordingClipIdMap.delete(trackId)
      }

      recordingChunksMap.delete(trackId)
      recordingStartTimeMap.delete(trackId)
      recordingStreamMap.delete(trackId)

      recordingElapsedMap.value = { ...recordingElapsedMap.value, [trackId]: 0 }
      isRecording.value = { ...isRecording.value, [trackId]: false }
    } catch (e) {
      console.error('[record] forced cleanup error for', trackId, e)
    }
  }
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
  height: calc(var(--timeline-ruler-height, 72px) + var(--playback-controls-height, 64px));
  box-sizing: border-box;
}

.header-title {
  display: flex;
  align-items: center; 
  gap: 0.75rem;
  margin-bottom: 1.5rem;
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
  overflow: hidden;
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
  overflow: hidden;
  width: 100%;
}

.track-info {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex: 1;
  margin: 0;
  min-width: 0;
  overflow: hidden;
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
  flex-shrink: 0;
  min-width: fit-content;
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

.btn-icon.recording {
  background: var(--error);
  color: white;
  animation: pulse-recording 2s infinite;
}

@keyframes pulse-recording {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}

.btn-icon.delete-btn:hover {
  background: var(--error);
  color: white;
}

.btn-icon .icon {
  width: 14px;
  height: 14px;
}

.btn-danger {
  background: var(--error);
  color: white;
  border: none;
  padding: 8px 12px;
  border-radius: 6px;
  display: inline-flex;
  align-items: center;
}

.record-large {
  font-weight: 600;
}

.record-small {
  width: 22px;
  height: 22px;
  padding: 2px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.vocal-header-group {
  align-items: center;
  gap: 0.5rem;
  display: flex;
}

.mic-warning {
  margin-left: 6px;
  display: flex;
  align-items: center;
}

/* disabled appearance for record buttons */
.btn[disabled],
.btn-icon[disabled] {
  cursor: not-allowed;
  opacity: 0.5;
  filter: grayscale(0.6);
}

.btn[disabled]:hover, .btn-icon[disabled]:hover {
  background: transparent;
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

.voice-type-control {
  border-bottom: 1px solid var(--border);
  padding-bottom: 0.75rem;
  margin-bottom: 0.75rem;
}

.voice-type-selector {
  background: var(--background);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 0.6rem 0.8rem;
  color: var(--text);
  font-size: 0.85rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  flex: 1;
  appearance: none;
  background-image: url("data:image/svg+xml;charset=UTF-8,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3e%3cpolyline points='6,9 12,15 18,9'%3e%3c/polyline%3e%3c/svg%3e");
  background-repeat: no-repeat;
  background-position: right 0.7rem center;
  background-size: 1em;
  padding-right: 2.5rem;
}

.voice-type-selector:hover {
  border-color: var(--primary);
}

.voice-type-selector:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: 0 0 0 2px rgba(var(--primary-rgb, 59, 130, 246), 0.1);
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
  max-width: 900px;
  max-height: 85vh;
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

/* Category Header Styles */
.category-header {
  display: flex;
  align-items: center;
  padding: 1rem 0;
  cursor: pointer;
  border-bottom: 1px solid var(--border);
  transition: all 0.2s ease;
}

.category-header:hover {
  background: var(--background);
}

.category-icon {
  width: 24px;
  height: 24px;
  color: var(--primary);
  margin-right: 0.75rem;
}

.category-name {
  font-weight: 600;
  font-size: 1.1rem;
  flex: 1;
  color: var(--text);
}

.chevron-icon {
  width: 16px;
  height: 16px;
  color: var(--text-secondary);
  transition: transform 0.2s ease;
}

.instruments-categories-list {
  padding: 0.5rem;
}

.instrument-category-group {
  margin-bottom: 1.5rem;
}

.instrument-count {
  font-size: 0.875rem;
  color: var(--text-secondary);
  margin-left: 0.5rem;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.selection-content {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
}

.category-instruments-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 0.75rem;
  margin-top: 1rem;
  padding: 0.5rem 0;
}

.instrument-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 0;
  cursor: pointer;
  transition: all 0.2s ease;
  overflow: hidden;
}

.instrument-card:hover {
  border-color: var(--primary);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.instrument-card.selected {
  border-color: var(--primary);
  box-shadow: 0 0 0 2px var(--primary);
  background: var(--primary);
}

.instrument-card.selected .instrument-name,
.instrument-card.selected .instrument-description {
  color: white;
}

.instrument-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem;
}

.instrument-icon {
  width: 32px;
  height: 32px;
  background: var(--gradient-primary);
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.instrument-icon .icon {
  width: 16px;
  height: 16px;
  color: white;
}

.instrument-info {
  flex: 1;
  min-width: 0;
}

.instrument-name {
  font-size: 0.875rem;
  font-weight: 600;
  margin: 0 0 0.25rem 0;
  color: var(--text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.instrument-description {
  font-size: 0.75rem;
  color: var(--text-secondary);
  margin: 0;
  line-height: 1.3;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Sample Section Styles */
.samples-section {
  padding: 0.5rem;
}

.samples-categories-list {
  padding: 0.5rem 0;
}

.sample-category-group {
  margin-bottom: 1.5rem;
}

.sample-count {
  font-size: 0.875rem;
  color: var(--text-secondary);
  margin-left: 0.5rem;
}

.category-samples-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 0.75rem;
  margin-top: 1rem;
  padding: 0.5rem 0;
}

.empty-samples-state {
  text-align: center;
  padding: 3rem 1rem;
  color: var(--text-secondary);
}

.empty-samples-state .empty-icon {
  width: 48px;
  height: 48px;
  margin-bottom: 1rem;
  opacity: 0.5;
}

.empty-samples-state h4 {
  margin: 0 0 0.5rem 0;
  color: var(--text);
}

.empty-samples-state p {
  margin: 0;
  font-size: 0.875rem;
}

.samples-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 0.75rem;
}

.sample-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
  transition: all 0.2s ease;
}

.sample-card:hover {
  border-color: var(--primary);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.sample-card.selected {
  border-color: var(--primary);
  box-shadow: 0 0 0 2px var(--primary);
}

.sample-header {
  display: flex;
  align-items: center;
  padding: 0.75rem;
  gap: 0.75rem;
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

.sample-icon .icon {
  width: 16px;
  height: 16px;
  color: white;
}

.sample-waveform {
  flex: 1;
  margin: 0 0.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
}

.waveform-canvas {
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.05);
}

.sample-actions {
  display: flex;
  gap: 0.25rem;
}

.action-btn {
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

.action-btn:hover {
  background: var(--border);
  color: var(--text);
}

.action-btn.play-btn:hover {
  background: var(--primary);
  color: white;
}

.action-btn .icon {
  width: 14px;
  height: 14px;
}

.sample-info {
  padding: 0 0.75rem 0.75rem 0.75rem;
}

.sample-name {
  font-size: 0.875rem;
  font-weight: 600;
  margin: 0 0 0.5rem 0;
  color: var(--text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sample-meta {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
  flex-wrap: wrap;
}

.category-badge {
  font-size: 0.75rem;
  font-weight: 500;
  padding: 0.125rem 0.5rem;
  border-radius: 12px;
  text-transform: capitalize;
}

.category-bass {
  background: rgba(34, 197, 94, 0.1);
  color: rgb(34, 197, 94);
}

.category-drums {
  background: rgba(239, 68, 68, 0.1);
  color: rgb(239, 68, 68);
}

.category-melodic {
  background: rgba(59, 130, 246, 0.1);
  color: rgb(59, 130, 246);
}

.category-vocals {
  background: rgba(168, 85, 247, 0.1);
  color: rgb(168, 85, 247);
}

.category-other {
  background: rgba(107, 114, 128, 0.1);
  color: rgb(107, 114, 128);
}

.duration,
.bpm {
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.sample-tags {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  flex-wrap: wrap;
}

.tag {
  font-size: 0.625rem;
  background: var(--border);
  color: var(--text-secondary);
  padding: 0.125rem 0.375rem;
  border-radius: 8px;
  font-weight: 500;
}

.tag-more {
  font-size: 0.625rem;
  color: var(--text-secondary);
  font-weight: 500;
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
/* Recording section styles */
.recording-status-section {
  margin-top: 0.75rem;
  padding: 0.75rem;
  background: var(--surface-secondary, var(--surface));
  border-radius: 6px;
  border: 1px solid var(--border);
}

.recording-active {
  display: flex;
  align-items: center;
  justify-content: center;
}

.recording-indicator {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.85rem;
  color: var(--text);
  font-weight: 500;
}

.record-timer {
  color: var(--error);
}

.permission-warning {
  padding: 0.5rem;
  background: rgba(255, 193, 7, 0.1);
  border: 1px solid rgba(255, 193, 7, 0.3);
  border-radius: 4px;
  font-size: 0.8rem;
  color: var(--warning, #ffc107);
  text-align: center;
}

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

/* If you reference instrument sample paths, include category between instruments and instrument name. */
</style>
