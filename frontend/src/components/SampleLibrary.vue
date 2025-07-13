<template>
  <div class="sample-library">
    <div class="library-header">
      <div class="header-title">
        <FileAudio class="header-icon" />
        <h3>Sample Library</h3>
        <span class="sample-count">{{ totalSamples }} samples</span>
      </div>
      
      <div class="header-actions">
        <button 
          class="btn btn-primary"
          @click="triggerFileInput"
          :disabled="isLoading"
        >
          <Upload class="icon" />
          {{ isLoading ? 'Loading...' : 'Load Samples' }}
        </button>
        
        <button 
          class="btn btn-ghost"
          @click="clearAllSamples"
          :disabled="totalSamples === 0"
        >
          <Trash2 class="icon" />
          Clear All
        </button>
      </div>
    </div>

    <!-- Loading Progress -->
    <div v-if="isLoading" class="loading-section">
      <div class="loading-bar">
        <div 
          class="loading-progress" 
          :style="{ width: `${loadingProgress}%` }"
        ></div>
      </div>
      <p class="loading-text">
        Analyzing samples... {{ Math.round(loadingProgress) }}%
      </p>
    </div>

    <!-- Library Stats -->
    <div v-if="totalSamples > 0" class="library-stats">
      <div class="stat-item">
        <Music class="stat-icon" />
        <span>{{ totalSamples }} Samples</span>
      </div>
      <div class="stat-item">
        <HardDrive class="stat-icon" />
        <span>{{ formatFileSize(totalSize) }}</span>
      </div>
      <div class="stat-item">
        <FolderOpen class="stat-icon" />
        <span>{{ categories.length }} Categories</span>
      </div>
    </div>

    <!-- Search and Filters -->
    <div v-if="totalSamples > 0" class="library-controls">
      <div class="search-section">
        <div class="search-input-wrapper">
          <Search class="search-icon" />
          <input
            v-model="searchQuery"
            type="text"
            placeholder="Search samples..."
            class="search-input"
          />
          <button 
            v-if="searchQuery"
            @click="searchQuery = ''"
            class="clear-search-btn"
          >
            <X class="icon" />
          </button>
        </div>
      </div>

      <div class="filter-section">
        <div class="filter-group">
          <label>Category:</label>
          <select v-model="selectedCategory" class="filter-select">
            <option value="uncategorized">All Categories</option>
            <option v-for="category in categories" :key="category" :value="category">
              {{ getCategoryDisplayName(category) }}
            </option>
          </select>
        </div>

        <div class="filter-group">
          <label>Sort by:</label>
          <select v-model="sortBy" class="filter-select">
            <option value="name">Name</option>
            <option value="date">Date Added</option>
            <option value="duration">Duration</option>
            <option value="size">File Size</option>
          </select>
        </div>

        <button 
          class="sort-order-btn"
          @click="sortOrder = sortOrder === 'asc' ? 'desc' : 'asc'"
          :title="`Sort ${sortOrder === 'asc' ? 'Descending' : 'Ascending'}`"
        >
          <ArrowUpDown class="icon" />
          {{ sortOrder === 'asc' ? '↑' : '↓' }}
        </button>
      </div>
    </div>

    <!-- Sample Grid -->
    <div class="samples-content">
      <div v-if="totalSamples === 0" class="empty-state">
        <FileAudio class="empty-icon" />
        <h4>No samples loaded</h4>
        <p>Load audio files from your computer to get started</p>
        <button class="btn btn-primary" @click="triggerFileInput">
          <Upload class="icon" />
          Load Your First Samples
        </button>
      </div>

      <div v-else-if="filteredSamples.length === 0" class="empty-state">
        <Search class="empty-icon" />
        <h4>No samples found</h4>
        <p>Try adjusting your search or filter criteria</p>
        <button class="btn btn-ghost" @click="clearFilters">
          Clear Filters
        </button>
      </div>

      <div v-else class="samples-grid">
        <div
          v-for="sample in filteredSamples"
          :key="sample.id"
          class="sample-card"
          @click="selectSample(sample)"
          :class="{ 'selected': selectedSample?.id === sample.id }"
        >
          <div class="sample-header">
            <div class="sample-icon">
              <component :is="getCategoryIcon(sample.category)" class="icon" />
            </div>

            <div class="sample-waveform" v-if="sample.waveform" style="flex:1; margin: 0 0.5rem;">
              <canvas 
                :ref="el => waveformCanvases[sample.id] = el as HTMLCanvasElement"
                class="waveform-canvas"
                :width="120"
                :height="32"
              ></canvas>
            </div>

            <div class="sample-actions">
              <button 
                class="action-btn play-btn"
                @click.stop="togglePlaySample(sample)"
                :disabled="isPlayingSample && playingSampleId !== sample.id"
              >
                <Play v-if="!isPlayingSample || playingSampleId !== sample.id" class="icon" />
                <Pause v-else class="icon" />
              </button>
              
              <button 
                class="action-btn"
                @click.stop="showSampleMenu(sample, $event)"
              >
                <MoreVertical class="icon" />
              </button>
            </div>
          </div>

          <div class="sample-info">
            <h4 class="sample-name" :title="sample.name">{{ sample.name }}</h4>
            <div class="sample-meta">
              <span class="category-badge" :class="`category-${sample.category}`">
                {{ getCategoryDisplayName(sample.category) }}
              </span>
              <span class="duration">{{ formatDuration(sample.duration) }}</span>
              <span v-if="sample.bpm" class="bpm">{{ sample.bpm }} BPM</span>
            </div>
            <div class="sample-tags">
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
    </div>

    <!-- Sample Context Menu -->
    <div 
      v-if="contextMenu.show" 
      class="context-menu"
      :style="{ top: contextMenu.y + 'px', left: contextMenu.x + 'px' }"
      @click.stop
    >
      <button class="context-menu-item" @click="addToTrack">
        <Plus class="icon" />
        Add to Track
      </button>
      <button class="context-menu-item" @click="editSample">
        <Edit class="icon" />
        Edit Details
      </button>
      <button class="context-menu-item" @click="duplicateSample">
        <Copy class="icon" />
        Duplicate
      </button>
      <hr class="context-menu-divider" />
      <button class="context-menu-item danger" @click="deleteSample">
        <Trash2 class="icon" />
        Delete
      </button>
    </div>

    <!-- Sample Edit Modal -->
    <div v-if="editModal.show" class="modal-overlay" @click="closeEditModal">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Edit Sample Details</h3>
          <button class="btn-icon" @click="closeEditModal">
            <X class="icon" />
          </button>
        </div>
        
        <div class="modal-body">
          <div class="form-group">
            <label>Name:</label>
            <input 
              v-model="editModal.sample.name"
              type="text"
              class="form-input"
            />
          </div>
          
          <div class="form-group">
            <label>Category:</label>
            <select v-model="editModal.sample.category" class="form-select">
              <option v-for="category in allCategories" :key="category" :value="category">
                {{ getCategoryDisplayName(category) }}
              </option>
            </select>
          </div>
          
          <div class="form-group">
            <label>BPM:</label>
            <input 
              v-model.number="editModal.sample.bpm"
              type="number"
              min="60"
              max="200"
              class="form-input"
            />
          </div>
          
          <div class="form-group">
            <label>Key:</label>
            <select v-model="editModal.sample.key" class="form-select">
              <option value="">Unknown</option>
              <option v-for="key in musicalKeys" :key="key" :value="key">
                {{ key }}
              </option>
            </select>
          </div>
          
          <div class="form-group">
            <label>Tags (comma separated):</label>
            <input 
              v-model="editModal.tagsString"
              type="text"
              class="form-input"
              placeholder="electronic, synth, lead"
            />
          </div>
        </div>
        
        <div class="modal-footer">
          <button class="btn btn-ghost" @click="closeEditModal">
            Cancel
          </button>
          <button class="btn btn-primary" @click="saveEditModal">
            Save Changes
          </button>
        </div>
      </div>
    </div>

    <!-- Hidden file input -->
    <input
      ref="fileInput"
      type="file"
      multiple
      accept="audio/*,.mp3,.wav,.ogg,.m4a,.aac,.flac"
      @change="handleFileSelect"
      style="display: none"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick, watch, toRef } from 'vue'
import { useSampleStore, type LocalSample, type SampleCategory } from '../stores/sampleStore'
import { useAudioStore } from '../stores/audioStore'
import {
  FileAudio, Upload, Trash2, Music, HardDrive, FolderOpen,
  Search, X, ArrowUpDown, Play, Pause, MoreVertical,
  Plus, Edit, Copy, Drum, Guitar, Piano, Mic, Zap
} from 'lucide-vue-next'
import { drawWaveform } from '../utils/waveform'
import { storeToRefs } from 'pinia'

const sampleStore = useSampleStore()
const audioStore = useAudioStore()

// Destructure reactive properties with storeToRefs
const {
  localSamples, isLoading, loadingProgress,
  sortBy, sortOrder, filteredSamples, categories, totalSamples, totalSize
} = storeToRefs(sampleStore)

// Destructure methods directly (they don't need reactivity)
const {
  formatFileSize, formatDuration, loadSamples, removeSample,
  updateSampleCategory, updateSampleTags, clearAllSamples
} = sampleStore

// Fix: Use refs for selectedCategory and searchQuery
const selectedCategory = toRef(sampleStore, 'selectedCategory')
const searchQuery = toRef(sampleStore, 'searchQuery')

// Component state
const fileInput = ref<HTMLInputElement>()
const selectedSample = ref<LocalSample | null>(null)
const isPlayingSample = ref(false)
const playingSampleId = ref<string | null>(null)
const currentAudio = ref<HTMLAudioElement | null>(null)
const waveformCanvases = ref<Record<string, HTMLCanvasElement>>({})

// Context menu
const contextMenu = ref({
  show: false,
  x: 0,
  y: 0,
  sample: null as LocalSample | null
})

// Edit modal
const editModal = ref({
  show: false,
  sample: {} as any,
  tagsString: ''
})

// Animation
const waveformAnimFrame = ref<number | null>(null)
const waveformPlayProgress = ref(0)

// Constants
const allCategories: SampleCategory[] = [
  'drums', 'bass', 'melodic', 'vocals', 'fx', 'loops', 
  'oneshots', 'ambient', 'percussion', 'uncategorized'
]

const musicalKeys = [
  'C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B',
  'Cm', 'C#m', 'Dm', 'D#m', 'Em', 'Fm', 'F#m', 'Gm', 'G#m', 'Am', 'A#m', 'Bm'
]

// Methods
const triggerFileInput = () => {
  fileInput.value?.click()
}

const handleFileSelect = async (event: Event) => {
  const target = event.target as HTMLInputElement
  if (target.files && target.files.length > 0) {
    try {
      await loadSamples(target.files)
      // Reset filters so new samples are visible immediately
      selectedCategory.value = 'uncategorized'
      searchQuery.value = ''
      target.value = '' // Reset input
    } catch (error) {
      console.error('Failed to load samples:', error)
      alert('Failed to load some samples. Please check the console for details.')
    }
  }
}

const selectSample = (sample: LocalSample) => {
  selectedSample.value = selectedSample.value?.id === sample.id ? null : sample
}

const togglePlaySample = async (sample: LocalSample) => {
  if (isPlayingSample.value && playingSampleId.value === sample.id) {
    if (currentAudio.value) {
      audioStore.unregisterPreviewAudio(currentAudio.value)
      currentAudio.value.pause()
      currentAudio.value = null
    }
    isPlayingSample.value = false
    playingSampleId.value = null
    stopWaveformAnimation()
  } else {
    if (currentAudio.value) {
      audioStore.unregisterPreviewAudio(currentAudio.value)
      currentAudio.value.pause()
    }
    try {
      const audio = new Audio(sample.url)
      audio.volume = 0.7
      
      // Register with audio store for global stop functionality
      audioStore.registerPreviewAudio(audio)
      
      audio.onended = () => {
        isPlayingSample.value = false
        playingSampleId.value = null
        audioStore.unregisterPreviewAudio(audio)
        currentAudio.value = null
        stopWaveformAnimation()
      }
      audio.onerror = () => {
        isPlayingSample.value = false
        playingSampleId.value = null
        audioStore.unregisterPreviewAudio(audio)
        currentAudio.value = null
        stopWaveformAnimation()
        console.error('Failed to play sample:', sample.name)
      }
      await audio.play()
      currentAudio.value = audio
      isPlayingSample.value = true
      playingSampleId.value = sample.id
      startWaveformAnimation(sample)
    } catch (error) {
      console.error('Failed to play sample:', error)
    }
  }
}

const showSampleMenu = (sample: LocalSample, event: MouseEvent) => {
  contextMenu.value = {
    show: true,
    x: event.clientX,
    y: event.clientY,
    sample
  }
  
  // Close menu when clicking elsewhere
  const closeMenu = () => {
    contextMenu.value.show = false
    document.removeEventListener('click', closeMenu)
  }
  
  setTimeout(() => {
    document.addEventListener('click', closeMenu)
  }, 0)
}

const addToTrack = () => {
  if (contextMenu.value.sample) {
    // Add sample to selected track or create new track
    const trackId = audioStore.selectedTrackId || audioStore.addTrack(
      contextMenu.value.sample.name,
      'sample',
      contextMenu.value.sample.url
    )
    
    if (trackId) {
      audioStore.addClip(trackId, {
        startTime: 0,
        duration: contextMenu.value.sample.duration,
        type: 'sample',
        instrument: 'sample',
        sampleUrl: contextMenu.value.sample.url,
        volume: 0.8,
        effects: { reverb: 0, delay: 0, distortion: 0 },
        waveform: contextMenu.value.sample.waveform // Pass waveform for timeline visualization
      })
    }
  }
  contextMenu.value.show = false
}

const editSample = () => {
  if (contextMenu.value.sample) {
    editModal.value = {
      show: true,
      sample: { ...contextMenu.value.sample },
      tagsString: contextMenu.value.sample.tags.join(', ')
    }
  }
  contextMenu.value.show = false
}

const duplicateSample = () => {
  if (contextMenu.value.sample) {
    const original = contextMenu.value.sample
    const duplicate: LocalSample = {
      ...original,
      id: `local-${Date.now()}-duplicate`,
      name: `${original.name} (Copy)`,
      createdAt: new Date().toISOString()
    }
    localSamples.value.push(duplicate)
  }
  contextMenu.value.show = false
}

const deleteSample = () => {
  if (contextMenu.value.sample && confirm('Delete this sample?')) {
    removeSample(contextMenu.value.sample.id)
  }
  contextMenu.value.show = false
}

const closeEditModal = () => {
  editModal.value.show = false
}

const saveEditModal = () => {
  const sample = editModal.value.sample
  const originalSample = localSamples.value.find(s => s.id === sample.id)
  
  if (originalSample) {
    originalSample.name = sample.name
    originalSample.bpm = sample.bpm
    originalSample.key = sample.key
    
    updateSampleCategory(sample.id, sample.category)
    updateSampleTags(sample.id, editModal.value.tagsString.split(',').map(t => t.trim()).filter(t => t))
  }
  
  closeEditModal()
}

const clearFilters = () => {
  searchQuery.value = ''
  selectedCategory.value = 'uncategorized'
}

const getCategoryDisplayName = (category: SampleCategory): string => {
  const names: Record<SampleCategory, string> = {
    drums: 'Drums',
    bass: 'Bass',
    melodic: 'Melodic',
    vocals: 'Vocals',
    fx: 'Effects',
    loops: 'Loops',
    oneshots: 'One Shots',
    ambient: 'Ambient',
    percussion: 'Percussion',
    uncategorized: 'Uncategorized'
  }
  return names[category] || category
}

const getCategoryIcon = (category: SampleCategory) => {
  const icons: Record<SampleCategory, any> = {
    drums: Drum,
    bass: Guitar,
    melodic: Piano,
    vocals: Mic,
    fx: Zap,
    loops: Music,
    oneshots: Music,
    ambient: Music,
    percussion: Drum,
    uncategorized: Music
  }
  return icons[category] || Music
}

// Animate waveform highlight on playback
const animateWaveform = (sample: LocalSample) => {
  if (!sample.waveform || !waveformCanvases.value[sample.id]) return
  const canvas = waveformCanvases.value[sample.id]
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  const width = canvas.width
  const height = canvas.height
  // Redraw waveform
  drawWaveform(canvas, sample.waveform)
  // Draw animated highlight if playing
  if (isPlayingSample.value && playingSampleId.value === sample.id && sample.duration) {
    const progress = waveformPlayProgress.value
    const x = progress * width
    ctx.save()
    ctx.globalAlpha = 0.25
    ctx.fillStyle = 'var(--primary)'
    ctx.fillRect(0, 0, x, height)
    ctx.restore()
  }
}

// Animation loop
const startWaveformAnimation = (sample: LocalSample) => {
  const animate = () => {
    if (!isPlayingSample.value || playingSampleId.value !== sample.id || !currentAudio.value) {
      waveformPlayProgress.value = 0
      animateWaveform(sample)
      return
    }
    // Calculate progress (0-1)
    const audio = currentAudio.value
    waveformPlayProgress.value = Math.min(audio.currentTime / (sample.duration || 1), 1)
    animateWaveform(sample)
    waveformAnimFrame.value = requestAnimationFrame(animate)
  }
  waveformAnimFrame.value = requestAnimationFrame(animate)
}

const stopWaveformAnimation = () => {
  if (waveformAnimFrame.value) {
    cancelAnimationFrame(waveformAnimFrame.value)
    waveformAnimFrame.value = null
  }
  waveformPlayProgress.value = 0
}

// Watch for waveform updates
watch(filteredSamples, async () => {
  await nextTick()
  filteredSamples.value.forEach(sample => {
    if (sample.waveform && waveformCanvases.value[sample.id]) {
      drawWaveform(waveformCanvases.value[sample.id], sample.waveform)
      // If playing, animate
      if (isPlayingSample.value && playingSampleId.value === sample.id) {
        startWaveformAnimation(sample)
      }
    }
  })
}, { immediate: true })

// Watch for changes in totalSamples and isLoading to trigger UI update
watch([totalSamples, isLoading], async () => {
  await nextTick()
  filteredSamples.value.forEach(sample => {
    if (sample.waveform && waveformCanvases.value[sample.id]) {
      drawWaveform(waveformCanvases.value[sample.id], sample.waveform)
    }
  })
})

// Close context menu on escape
onMounted(() => {
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      contextMenu.value.show = false
      if (editModal.value.show) {
        closeEditModal()
      }
    }
  })
})
</script>

<style scoped>
.sample-library {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--background);
}

.library-header {
  padding: 1rem;
  border-bottom: 1px solid var(--border);
  background: var(--surface);
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

.sample-count {
  font-size: 0.875rem;
  color: var(--text-secondary);
  background: var(--border);
  padding: 0.25rem 0.5rem;
  border-radius: 12px;
}

.header-actions {
  display: flex;
  gap: 0.5rem;
}

.loading-section {
  padding: 1rem;
  text-align: center;
}

.loading-bar {
  width: 100%;
  height: 4px;
  background: var(--border);
  border-radius: 2px;
  overflow: hidden;
  margin-bottom: 0.5rem;
}

.loading-progress {
  height: 100%;
  background: var(--gradient-primary);
  transition: width 0.3s ease;
}

.loading-text {
  margin: 0;
  color: var(--text-secondary);
  font-size: 0.875rem;
}

.library-stats {
  display: flex;
  gap: 1rem;
  padding: 1rem;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  color: var(--text-secondary);
}

.stat-icon {
  width: 16px;
  height: 16px;
}

.library-controls {
  padding: 1rem;
  border-bottom: 1px solid var(--border);
  background: var(--surface);
}

.search-section {
  margin-bottom: 1rem;
}

.search-input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}

.search-icon {
  position: absolute;
  left: 0.75rem;
  width: 16px;
  height: 16px;
  color: var(--text-secondary);
  pointer-events: none;
}

.search-input {
  width: 100%;
  padding: 0.75rem 0.75rem 0.75rem 2.5rem;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--background);
  color: var(--text);
  font-size: 0.875rem;
}

.search-input:focus {
  outline: none;
  border-color: var(--primary);
}

.clear-search-btn {
  position: absolute;
  right: 0.5rem;
  width: 24px;
  height: 24px;
  border: none;
  background: transparent;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--text-secondary);
}

.clear-search-btn:hover {
  background: var(--border);
  color: var(--text);
}

.filter-section {
  display: flex;
  gap: 1rem;
  align-items: center;
}

.filter-group {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.filter-group label {
  font-size: 0.875rem;
  color: var(--text-secondary);
  white-space: nowrap;
}

.filter-select {
  padding: 0.5rem;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--background);
  color: var(--text);
  font-size: 0.875rem;
}

.sort-order-btn {
  padding: 0.5rem;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--background);
  color: var(--text);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.875rem;
}

.sort-order-btn:hover {
  border-color: var(--primary);
}

.samples-content {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
}

.empty-state {
  text-align: center;
  padding: 3rem 1rem;
  color: var(--text-secondary);
}

.empty-icon {
  width: 64px;
  height: 64px;
  margin-bottom: 1rem;
  opacity: 0.5;
}

.empty-state h4 {
  margin: 0 0 0.5rem 0;
  color: var(--text);
}

.empty-state p {
  margin: 0 0 1.5rem 0;
}

.samples-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1rem;
}

.sample-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 1rem;
  cursor: pointer;
  transition: all 0.2s ease;
}

.sample-card:hover {
  border-color: var(--primary);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.sample-card.selected {
  border-color: var(--primary);
  box-shadow: 0 0 0 1px var(--primary);
}

.sample-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.sample-icon {
  width: 32px;
  height: 32px;
  background: var(--gradient-primary);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.sample-icon .icon {
  width: 16px;
  height: 16px;
  color: white;
}

.sample-waveform {
  margin: 0 0.5rem;
  flex: 1;
}

.sample-actions {
  display: flex;
  gap: 0.25rem;
}

.action-btn {
  width: 32px;
  height: 32px;
  border: none;
  background: var(--border);
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s ease;
  color: var(--text);
}

.action-btn:hover {
  background: var(--primary);
  color: white;
}

.action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.action-btn .icon {
  width: 14px;
  height: 14px;
}

.play-btn.action-btn:hover {
  background: var(--success);
}

.waveform-canvas {
  margin-top: 7px;
  width: 100%;
  height: 32px;
  border-radius: 4px;
  background: var(--backgroundSecondary);
}

.sample-info {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.sample-name {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sample-meta {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.category-badge {
  padding: 0.25rem 0.5rem;
  border-radius: 12px;
  font-size: 0.75rem;
  font-weight: 500;
  text-transform: capitalize;
}

.category-drums { background: #ff6b6b; color: white; }
.category-bass { background: #4ecdc4; color: white; }
.category-melodic { background: #45b7d1; color: white; }
.category-vocals { background: #f9ca24; color: black; }
.category-fx { background: #6c5ce7; color: white; }
.category-loops { background: #a29bfe; color: white; }
.category-oneshots { background: #fd79a8; color: white; }
.category-ambient { background: #00b894; color: white; }
.category-percussion { background: #e17055; color: white; }
.category-uncategorized { background: var(--border); color: var(--text); }

.duration,
.bpm {
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.sample-tags {
  display: flex;
  gap: 0.25rem;
  flex-wrap: wrap;
}

.tag {
  padding: 0.125rem 0.375rem;
  background: var(--border);
  border-radius: 8px;
  font-size: 0.625rem;
  color: var(--text-secondary);
}

.tag-more {
  padding: 0.125rem 0.375rem;
  background: var(--primary);
  color: white;
  border-radius: 8px;
  font-size: 0.625rem;
}

/* Context Menu */
.context-menu {
  position: fixed;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 0.5rem 0;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
  z-index: 1000;
  min-width: 160px;
}

.context-menu-item {
  width: 100%;
  padding: 0.5rem 1rem;
  border: none;
  background: transparent;
  color: var(--text);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  text-align: left;
}

.context-menu-item:hover {
  background: var(--border);
}

.context-menu-item.danger {
  color: var(--error);
}

.context-menu-item.danger:hover {
  background: var(--error);
  color: white;
}

.context-menu-divider {
  margin: 0.5rem 0;
  border: none;
  border-top: 1px solid var(--border);
}

/* Modal */
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
  max-width: 500px;
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
}

.modal-body {
  padding: 1.5rem;
}

.form-group {
  margin-bottom: 1rem;
}

.form-group label {
  display: block;
  margin-bottom: 0.5rem;
  font-size: 0.875rem;
  color: var(--text);
  font-weight: 500;
}

.form-input,
.form-select {
  width: 100%;
  padding: 0.75rem;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--background);
  color: var(--text);
  font-size: 0.875rem;
}

.form-input:focus,
.form-select:focus {
  outline: none;
  border-color: var(--primary);
}

.modal-footer {
  padding: 1.5rem;
  border-top: 1px solid var(--border);
  display: flex;
  gap: 1rem;
  justify-content: flex-end;
}

/* Scrollbar */
.samples-content::-webkit-scrollbar {
  width: 6px;
}

.samples-content::-webkit-scrollbar-track {
  background: transparent;
}

.samples-content::-webkit-scrollbar-thumb {
  background: var(--border);
  border-radius: 3px;
}

.samples-content::-webkit-scrollbar-thumb:hover {
  background: var(--text-secondary);
}

@media (max-width: 768px) {
  .samples-grid {
    grid-template-columns: 1fr;
  }
  
  .filter-section {
    flex-direction: column;
    align-items: stretch;
    gap: 0.75rem;
  }
  
  .filter-group {
    justify-content: space-between;
  }
  
  .header-actions {
    flex-direction: column;
  }
  
  .library-stats {
    flex-direction: column;
    gap: 0.5rem;
  }
}
</style>
