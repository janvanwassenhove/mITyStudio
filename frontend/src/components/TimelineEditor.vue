<template>
  <div class="timeline-editor">
    <div class="timeline-header">
      <div class="timeline-ruler">
        <div 
          v-for="beat in timelineBeats" 
          :key="beat"
          class="ruler-mark"
          :class="{ 'bar-line': beat % 4 === 0, 'beat-line': beat % 4 !== 0 }"
          :style="{ left: `${beat * beatWidth}px` }"
        >
          <span v-if="beat % 4 === 0" class="ruler-label">{{ Math.floor(beat / 4) + 1 }}</span>
        </div>
      </div>
    </div>
    
    <div class="timeline-content" ref="timelineContent">
      <div class="timeline-tracks">
        <div 
          v-for="track in audioStore.songStructure.tracks" 
          :key="track.id"
          class="timeline-track"
          :class="{ selected: audioStore.selectedTrackId === track.id }"
        >
          <!-- Removed track-label for alignment with left panel -->
          <div class="track-lane" @click="addClipToTrack(track.id, $event)">
            <div 
              v-for="clip in track.clips" 
              :key="clip.id"
              class="audio-clip"
              :class="{ selected: selectedClipId === clip.id }"
              :style="getClipStyle(clip)"
              @click.stop="selectClip(clip.id)"
              @mousedown="startDragClip(clip.id, $event)"
              @contextmenu.prevent="showContextMenu(clip.id, track.id, $event)"
            >
              <div class="clip-content">
                <!-- Chord Sample Clips -->
                <div v-if="clip.type === 'sample' && clip.sampleUrl && isChordSample(clip)" class="chord-clip">
                  <div class="chord-info">
                    <span class="chord-name">{{ getChordDisplayName(clip) }}</span>
                    <div class="chord-meta">
                      <span class="chord-bar">Bar {{ getClipBarNumber(clip) }}</span>
                      <span class="audio-format">{{ getAudioFormat(clip) }}</span>
                    </div>
                  </div>
                  <div class="chord-visual">
                    <div class="chord-duration-bar" :style="getChordBarStyle(clip)"></div>
                  </div>
                </div>
                
                <!-- Regular Sample Clips with Waveform -->
                <div v-else-if="clip.type === 'sample' && clip.waveform && clip.waveform.length" class="sample-clip">
                  <span class="clip-name">{{ clip.instrument }}</span>
                  <div class="clip-waveform">
                    <canvas
                      :ref="el => setClipWaveformCanvas(el, clip)"
                      class="waveform-canvas"
                      :height="20"
                    ></canvas>
                  </div>
                </div>
                
                <!-- Instrument Clips with Notes -->
                <div v-else-if="clip.notes && clip.notes.length" class="instrument-clip">
                  <span class="clip-name">{{ clip.instrument }}</span>
                  <div class="clip-notes">
                    <span v-for="(note, idx) in clip.notes.slice(0, 6)" :key="idx" class="clip-note">{{ note }}</span>
                    <span v-if="clip.notes.length > 6" class="note-overflow">+{{ clip.notes.length - 6 }}</span>
                  </div>
                </div>
                
                <!-- Fallback Generic Clip -->
                <div v-else class="generic-clip">
                  <span class="clip-name">{{ clip.instrument }}</span>
                  <div class="clip-waveform">
                    <div 
                      v-for="i in 20" 
                      :key="i"
                      class="waveform-bar"
                      :style="{ height: `${Math.random() * 100}%` }"
                    ></div>
                  </div>
                </div>
              </div>
              
              <div class="clip-resize-handle left" @mousedown.stop="startResizeClip(clip.id, 'left', $event)"></div>
              <div class="clip-resize-handle right" @mousedown.stop="startResizeClip(clip.id, 'right', $event)"></div>
            </div>
          </div>
        </div>
      </div>
      
      <div class="playhead" :style="{ left: `${playheadPosition}px` }"></div>
    </div>
    
    <!-- Context Menu -->
    <div 
      v-if="contextMenu.visible"
      class="context-menu"
      :style="{ 
        left: `${contextMenu.x}px`, 
        top: `${contextMenu.y}px` 
      }"
      @click.stop
    >
      <div class="context-menu-item" @click="duplicateClip">
        <Copy class="context-icon" />
        <span>Duplicate Clip</span>
      </div>
      <div class="context-menu-item" @click="splitClip">
        <Scissors class="context-icon" />
        <span>Split Clip</span>
      </div>
      <div class="context-menu-divider"></div>
      <div class="context-menu-item danger" @click="removeClip">
        <Trash2 class="context-icon" />
        <span>Remove Clip</span>
      </div>
    </div>
    
    <!-- Context Menu Overlay -->
    <div 
      v-if="contextMenu.visible"
      class="context-menu-overlay"
      @click="hideContextMenu"
    ></div>
    
    <div class="timeline-footer">
      <div class="timeline-controls">
        <button class="btn btn-ghost" @click="zoomOut">
          <ZoomOut class="icon" />
        </button>
        <span class="zoom-level">{{ Math.round(audioStore.zoom * 100) }}%</span>
        <button class="btn btn-ghost" @click="zoomIn">
          <ZoomIn class="icon" />
        </button>
        <button class="btn btn-ghost" @click="toggleMetronome">
          <span v-if="audioStore.metronomeEnabled">🔊</span>
          <span v-else>🔈</span>
          Metronome
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick, type ComponentPublicInstance } from 'vue'
import { useAudioStore, type AudioClip } from '../stores/audioStore'
import { useSampleStore } from '../stores/sampleStore'
import { ZoomIn, ZoomOut, Trash2, Copy, Scissors } from 'lucide-vue-next'
import { drawWaveform } from '../utils/waveform'
import { extractChordFromSampleUrl } from '../utils/chordVisualization'

const audioStore = useAudioStore()
const sampleStore = useSampleStore()
const timelineContent = ref<HTMLElement>()

const selectedClipId = computed(() => audioStore.selectedClipId)
const isDragging = ref(false)
const isResizing = ref(false)
const dragStartX = ref(0)
const dragStartTime = ref(0)

// Context menu state
const contextMenu = ref({
  visible: false,
  x: 0,
  y: 0,
  clipId: '',
  trackId: ''
})

// Store canvas refs for each sample clip
const clipWaveformCanvases = ref<Record<string, HTMLCanvasElement | null>>({})

function setClipWaveformCanvas(el: Element | ComponentPublicInstance | null, clip: AudioClip) {
  // Handle the case where el might be a component instance
  const canvas = el instanceof Element ? el : null
  
  if (canvas && canvas instanceof HTMLCanvasElement && clip.waveform) {
    clipWaveformCanvases.value[clip.id] = canvas
    // Set canvas width and height to match the clip's rendered size
    const width = clip.duration * beatWidth.value * 4
    canvas.width = Math.max(40, Math.round(width)) // minimum width for visibility
    // Find the parent .audio-clip element to get its height
    const parentClip = canvas.closest('.audio-clip') as HTMLElement | null
    if (parentClip) {
      canvas.height = parentClip.offsetHeight
    } else {
      canvas.height = 20 // fallback
    }
    drawWaveform(canvas, clip.waveform)
  } else if (!canvas) {
    clipWaveformCanvases.value[clip.id] = null
  }
}

// Timeline calculations
const beatWidth = computed(() => 60 * audioStore.zoom) // pixels per beat
const timelineWidth = computed(() => audioStore.songStructure.duration * 4 * beatWidth.value)
const timelineBeats = computed(() => {
  const beats = []
  const totalBeats = audioStore.songStructure.duration * 4
  // Determine step: show fewer marks if zoomed out
  let step = 1
  if (beatWidth.value < 20) step = 4 // show only bar lines
  if (beatWidth.value < 10) step = 8 // show every 2 bars
  for (let i = 0; i < totalBeats; i += step) {
    beats.push(i)
  }
  return beats
})

const playheadPosition = computed(() => {
  return audioStore.currentTime * beatWidth.value * 4 // Convert seconds to pixels
})

const getClipStyle = (clip: AudioClip) => {
  const left = clip.startTime * beatWidth.value * 4 // Convert beats to pixels
  const width = clip.duration * beatWidth.value * 4
  return {
    left: `${left}px`,
    width: `${width}px`
  }
}

const addClipToTrack = (trackId: string, event: MouseEvent) => {
  if (isDragging.value || isResizing.value) return
  const rect = (event.currentTarget as HTMLElement).getBoundingClientRect()
  const clickX = event.clientX - rect.left
  const startTime = clickX / (beatWidth.value * 4) // Convert pixels to beats
  
  // Find the track
  const track = audioStore.songStructure.tracks.find(t => t.id === trackId)
  
  // Check if this is a sample track (instrument matches a sample id)
  const sample = track && sampleStore
    ? Object.values(sampleStore.sampleLibrary).flat().find(s => s.id === track.instrument)
    : null
  
  if (sample) {
    // Add a sample clip with JSON configuration support
    const newClip = {
      startTime: Math.max(0, startTime),
      duration: sample.duration || 4,
      type: 'sample' as const,
      instrument: sample.id,
      sampleUrl: sample.url,
      waveform: sample.waveform,
      volume: 0.8,
      effects: {
        reverb: 0,
        delay: 0,
        distortion: 0
      }
    } as const
    
    // This will now use JSON configuration if available
    audioStore.addClip(trackId, newClip)
    return
  }
  
  // Otherwise, add a synth/instrument clip with JSON configuration support
  const newClip = {
    startTime: Math.max(0, startTime),
    duration: 4, // 1 bar default (will be overridden by JSON config if available)
    type: 'synth' as const,
    instrument: track ? track.instrument : 'synth',
    volume: 0.8,
    effects: {
      reverb: 0,
      delay: 0,
      distortion: 0
    }
  } as const
  
  // This will now use JSON configuration if available
  audioStore.addClip(trackId, newClip)
}

const selectClip = (clipId: string) => {
  audioStore.selectClip(clipId)
  hideContextMenu()
}

const showContextMenu = (clipId: string, trackId: string, event: MouseEvent) => {
  event.preventDefault()
  event.stopPropagation()
  
  audioStore.selectClip(clipId)
  contextMenu.value = {
    visible: true,
    x: event.clientX,
    y: event.clientY,
    clipId,
    trackId
  }
}

const hideContextMenu = () => {
  contextMenu.value.visible = false
}

const removeClip = () => {
  if (contextMenu.value.clipId && contextMenu.value.trackId) {
    audioStore.removeClip(contextMenu.value.trackId, contextMenu.value.clipId)
    
    // Clear selection if the removed clip was selected
    if (selectedClipId.value === contextMenu.value.clipId) {
      audioStore.selectClip(null)
    }
  }
  hideContextMenu()
}

const duplicateClip = () => {
  if (contextMenu.value.clipId && contextMenu.value.trackId) {
    // Find the original clip
    const track = audioStore.songStructure.tracks.find(t => t.id === contextMenu.value.trackId)
    const originalClip = track?.clips.find(c => c.id === contextMenu.value.clipId)
    
    if (originalClip) {
      const newClip = {
        startTime: originalClip.startTime + originalClip.duration, // Place right after original
        duration: originalClip.duration,
        type: originalClip.type,
        instrument: originalClip.instrument,
        notes: originalClip.notes ? [...originalClip.notes] : undefined,
        sampleUrl: originalClip.sampleUrl,
        volume: originalClip.volume,
        effects: { ...originalClip.effects }
      }
      
      audioStore.addClip(contextMenu.value.trackId, newClip)
    }
  }
  hideContextMenu()
}

const splitClip = () => {
  if (contextMenu.value.clipId && contextMenu.value.trackId) {
    const track = audioStore.songStructure.tracks.find(t => t.id === contextMenu.value.trackId)
    const originalClip = track?.clips.find(c => c.id === contextMenu.value.clipId)
    
    if (originalClip && originalClip.duration > 0.5) {
      const splitPoint = originalClip.duration / 2
      
      // Update original clip to first half
      audioStore.updateClip(contextMenu.value.trackId, contextMenu.value.clipId, {
        duration: splitPoint
      })
      
      // Create second half
      const secondHalf = {
        startTime: originalClip.startTime + splitPoint,
        duration: splitPoint,
        type: originalClip.type,
        instrument: originalClip.instrument,
        notes: originalClip.notes ? [...originalClip.notes] : undefined,
        sampleUrl: originalClip.sampleUrl,
        volume: originalClip.volume,
        effects: { ...originalClip.effects }
      }
      
      audioStore.addClip(contextMenu.value.trackId, secondHalf)
    }
  }
  hideContextMenu()
}

const startDragClip = (clipId: string, event: MouseEvent) => {
  // Don't start drag if right-clicking
  if (event.button === 2) return
  
  audioStore.selectClip(clipId)
  isDragging.value = true
  dragStartX.value = event.clientX
  
  // Find the clip to get its current start time
  for (const track of audioStore.songStructure.tracks) {
    const clip = track.clips.find(c => c.id === clipId)
    if (clip) {
      dragStartTime.value = clip.startTime
      break
    }
  }
  
  document.addEventListener('mousemove', handleDragClip)
  document.addEventListener('mouseup', stopDragClip)
  event.preventDefault()
}

const handleDragClip = (event: MouseEvent) => {
  if (!isDragging.value || !selectedClipId.value) return
  
  const deltaX = event.clientX - dragStartX.value
  const deltaTime = deltaX / (beatWidth.value * 4)
  const newStartTime = Math.max(0, dragStartTime.value + deltaTime)
  
  // Find and update the clip
  for (const track of audioStore.songStructure.tracks) {
    const clip = track.clips.find(c => c.id === selectedClipId.value)
    if (clip) {
      audioStore.updateClip(track.id, clip.id, { startTime: newStartTime })
      break
    }
  }
}

const stopDragClip = () => {
  isDragging.value = false
  document.removeEventListener('mousemove', handleDragClip)
  document.removeEventListener('mouseup', stopDragClip)
}

const resizeSide = ref<'left' | 'right' | null>(null)

const startResizeClip = (clipId: string, side: 'left' | 'right', event: MouseEvent) => {
  audioStore.selectClip(clipId)
  isResizing.value = true
  dragStartX.value = event.clientX
  resizeSide.value = side

  document.addEventListener('mousemove', handleResizeClipEvent)
  document.addEventListener('mouseup', stopResizeClip)
  event.preventDefault()
}

const handleResizeClip = (event: MouseEvent, side: 'left' | 'right') => {
  if (!isResizing.value || !selectedClipId.value) return

  const deltaX = event.clientX - dragStartX.value
  const deltaTime = deltaX / (beatWidth.value * 4)

  // Find and update the clip
  for (const track of audioStore.songStructure.tracks) {
    const clip = track.clips.find(c => c.id === selectedClipId.value)
    if (clip) {
      if (side === 'left') {
        const newStartTime = Math.max(0, clip.startTime + deltaTime)
        const newDuration = Math.max(0.25, clip.duration - deltaTime)
        audioStore.updateClip(track.id, clip.id, { 
          startTime: newStartTime, 
          duration: newDuration 
        })
      } else {
        const newDuration = Math.max(0.25, clip.duration + deltaTime)
        audioStore.updateClip(track.id, clip.id, { duration: newDuration })
      }
      break
    }
  }
}

const handleResizeClipEvent = (event: MouseEvent) => {
  if (resizeSide.value) {
    handleResizeClip(event, resizeSide.value)
  }
}

const stopResizeClip = () => {
  isResizing.value = false
  resizeSide.value = null
  document.removeEventListener('mousemove', handleResizeClipEvent)
  document.removeEventListener('mouseup', stopResizeClip)
}

const zoomIn = () => {
  audioStore.setZoom(audioStore.zoom * 1.2)
}

const zoomOut = () => {
  audioStore.setZoom(audioStore.zoom / 1.2)
}

const toggleMetronome = () => {
  audioStore.toggleMetronome()
}

// Chord visualization methods
const isChordSample = (clip: AudioClip): boolean => {
  if (!clip.sampleUrl) return false
  
  // Check if the sample URL contains chord patterns
  const filename = clip.sampleUrl.split('/').pop() || ''
  const nameWithoutExt = filename.replace(/\.(wav|mp3|ogg)$/i, '')
  
  // Look for chord patterns like "C_major", "F#_min7", etc.
  const chordPattern = /^[A-G][#b]?_(major|minor|dom7|maj7|min7|augmented|diminished|sus2|sus4)$/i
  return chordPattern.test(nameWithoutExt)
}

const getChordDisplayName = (clip: AudioClip): string => {
  if (!clip.sampleUrl) return clip.instrument || 'Unknown'
  
  const chordInfo = extractChordFromSampleUrl(clip.sampleUrl)
  if (chordInfo) {
    // Extract instrument type from the sample URL path
    const urlParts = clip.sampleUrl.split('/')
    const instrument = urlParts.find(part => ['piano', 'guitar', 'bass', 'synth'].includes(part.toLowerCase()))
    
    // Show both chord and instrument info for clarity
    if (instrument) {
      return `${chordInfo.displayName} (${instrument})`
    }
    return chordInfo.displayName
  }
  
  return clip.instrument || 'Unknown'
}

const getClipBarNumber = (clip: AudioClip): number => {
  // Calculate which bar this clip starts in (1-indexed)
  const timeSignature = audioStore.songStructure.timeSignature
  const beatsPerBar = timeSignature[0]
  const tempo = audioStore.songStructure.tempo
  
  // Convert startTime (in seconds) to beats, then to bars
  // At 120 BPM, 1 beat = 0.5 seconds
  const beatsPerSecond = tempo / 60
  const beatPosition = clip.startTime * beatsPerSecond
  const barNumber = Math.floor(beatPosition / beatsPerBar) + 1
  
  return Math.max(1, barNumber)
}

const getChordBarStyle = (clip: AudioClip) => {
  const chordInfo = clip.sampleUrl ? extractChordFromSampleUrl(clip.sampleUrl) : null
  let backgroundColor = chordInfo ? chordInfo.color : '#9E7FFF'
  
  // Slightly adjust color based on audio format for visual distinction
  if (clip.sampleUrl) {
    if (clip.sampleUrl.includes('/wav/')) {
      // WAV files get full opacity (highest quality)
      backgroundColor = chordInfo?.color || '#9E7FFF'
    } else if (clip.sampleUrl.includes('/mp3/')) {
      // MP3 files get slightly desaturated
      backgroundColor = adjustBrightness(chordInfo?.color || '#9E7FFF', -10)
    } else if (clip.sampleUrl.includes('/midi/')) {
      // MIDI files get different treatment
      backgroundColor = adjustBrightness(chordInfo?.color || '#9E7FFF', 15)
    }
  }
  
  return {
    backgroundColor,
    width: '100%',
    height: '4px',
    borderRadius: '2px',
    opacity: '0.8',
    boxShadow: '0 1px 2px rgba(0, 0, 0, 0.1)'
  }
}

// Helper function to adjust color brightness
const adjustBrightness = (color: string, percent: number): string => {
  // Simple hex color brightness adjustment
  const hex = color.replace('#', '')
  const r = Math.max(0, Math.min(255, parseInt(hex.substr(0, 2), 16) + percent))
  const g = Math.max(0, Math.min(255, parseInt(hex.substr(2, 2), 16) + percent))
  const b = Math.max(0, Math.min(255, parseInt(hex.substr(4, 2), 16) + percent))
  
  return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`
}

const getAudioFormat = (clip: AudioClip): string => {
  if (!clip.sampleUrl) return ''
  
  if (clip.sampleUrl.includes('/wav/')) return 'WAV'
  if (clip.sampleUrl.includes('/mp3/')) return 'MP3'
  if (clip.sampleUrl.includes('/midi/')) return 'MIDI'
  
  // Extract from file extension as fallback
  const extension = clip.sampleUrl.split('.').pop()?.toUpperCase()
  return extension || 'UNK'
}

// Global click handler to hide context menu
const handleGlobalClick = () => {
  if (contextMenu.value.visible) {
    hideContextMenu()
  }
}

// Global escape key handler
const handleGlobalKeydown = (event: KeyboardEvent) => {
  if (event.key === 'Escape' && contextMenu.value.visible) {
    hideContextMenu()
  }
  
  // Delete key to remove selected clip
  if (event.key === 'Delete' && selectedClipId.value) {
    for (const track of audioStore.songStructure.tracks) {
      const clip = track.clips.find(c => c.id === selectedClipId.value)
      if (clip) {
        audioStore.removeClip(track.id, clip.id)
        audioStore.selectClip(null)
        break
      }
    }
  }
}

// Redraw waveform when clips, zoom, or duration change
watch([
  () => audioStore.songStructure.tracks.map(t => t.clips),
  () => audioStore.zoom
], async () => {
  await nextTick()
  audioStore.songStructure.tracks.forEach(track => {
    track.clips.forEach(clip => {
      if (clip.type === 'sample' && clip.waveform && clipWaveformCanvases.value[clip.id]) {
        // Update canvas width and height to match new clip size
        const el = clipWaveformCanvases.value[clip.id]!
        const width = clip.duration * beatWidth.value * 4
        el.width = Math.max(40, Math.round(width))
        const parentClip = el.closest('.audio-clip') as HTMLElement | null
        if (parentClip) {
          el.height = parentClip.offsetHeight
        } else {
          el.height = 20
        }
        drawWaveform(el, clip.waveform)
      }
    })
  })
}, { immediate: true })

onMounted(() => {
  document.addEventListener('click', handleGlobalClick)
  document.addEventListener('keydown', handleGlobalKeydown)
})

onUnmounted(() => {
  document.removeEventListener('click', handleGlobalClick)
  document.removeEventListener('keydown', handleGlobalKeydown)
  document.removeEventListener('mousemove', handleDragClip)
  document.removeEventListener('mouseup', stopDragClip)
  document.removeEventListener('mousemove', handleResizeClipEvent)
  document.removeEventListener('mouseup', stopResizeClip)
})
</script>

<style scoped>
.timeline-editor {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--background);
}

.timeline-header {
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  height: 40px;
  position: relative;
  overflow: hidden;
}

.timeline-ruler {
  position: relative;
  height: 100%;
  background: linear-gradient(to right, var(--border) 1px, transparent 1px);
  background-size: v-bind('beatWidth + "px"') 100%;
}

.ruler-mark {
  position: absolute;
  top: 0;
  height: 100%;
  display: flex;
  align-items: center;
  padding-left: 4px;
}

.ruler-mark.bar-line {
  border-left: 2px solid var(--text-secondary);
  z-index: 2;
}

.ruler-mark.beat-line {
  border-left: 1px solid var(--border);
  z-index: 1;
}

.ruler-label {
  font-size: 0.75rem;
  color: var(--text-secondary);
  font-weight: 600;
  background: var(--surface);
  padding: 0.125rem 0.25rem;
  border-radius: 3px;
  margin-left: 2px;
}

.timeline-content {
  flex: 1;
  overflow: auto;
  position: relative;
  background: var(--background);
}

.timeline-tracks {
  min-width: v-bind('timelineWidth + "px"');
}

.timeline-track {
  display: flex;
  height: 80px;
  border-bottom: 1px solid var(--border);
  transition: background-color 0.2s ease, height 0.3s cubic-bezier(0.4, 0, 0.2, 1), min-height 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.timeline-track:hover {
  background: rgba(158, 127, 255, 0.05);
}

.timeline-track.selected {
  background: rgba(158, 127, 255, 0.1);
}

.timeline-track.maximized {
  min-height: 180px;
  height: 180px;
}

.track-label {
  width: 200px;
  padding: 1rem;
  background: var(--surface);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  justify-content: center;
  flex-shrink: 0;
}

.track-name {
  font-weight: 500;
  color: var(--text);
  font-size: 0.875rem;
}

.track-instrument {
  font-size: 0.75rem;
  color: var(--text-secondary);
  text-transform: capitalize;
}

.track-lane {
  flex: 1;
  position: relative;
  cursor: crosshair;
  background-image: 
    linear-gradient(to right, var(--text-secondary) 1px, transparent 1px),
    linear-gradient(to right, var(--border) 1px, transparent 1px);
  background-size: 
    v-bind('(beatWidth * 4) + "px"') 100%,
    v-bind('beatWidth + "px"') 100%;
  background-position: 0 0, 0 0;
}

.audio-clip {
  position: absolute;
  top: 8px;
  height: 64px;
  background: var(--gradient-primary);
  border-radius: 8px;
  cursor: move;
  box-shadow: var(--shadow-md);
  transition: all 0.2s ease;
  overflow: hidden;
}

.audio-clip:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-lg);
}

.audio-clip.selected {
  box-shadow: 0 0 0 2px var(--accent), var(--shadow-lg);
}

.clip-content {
  padding: 0.5rem;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.clip-name {
  font-size: 0.75rem;
  font-weight: 500;
  color: white;
  text-transform: capitalize;
}

.clip-notes {
  display: flex;
  gap: 0.25rem;
  flex-wrap: wrap;
}

.clip-note {
  background: rgba(255, 255, 255, 0.1);
  padding: 0.125rem 0.5rem;
  border-radius: 4px;
  font-size: 0.625rem;
  color: var(--text);
}

/* Chord visualization styles */
.chord-clip {
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.chord-info {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 0.25rem;
  flex-direction: column;
  gap: 0.125rem;
}

.chord-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.chord-name {
  font-size: 0.875rem;
  font-weight: 600;
  color: white;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
}

.chord-bar {
  font-size: 0.6875rem;
  color: rgba(255, 255, 255, 0.8);
  font-weight: 500;
}

.audio-format {
  font-size: 0.625rem;
  color: rgba(255, 255, 255, 0.7);
  font-weight: 500;
  background: rgba(0, 0, 0, 0.2);
  padding: 0.125rem 0.25rem;
  border-radius: 3px;
  letter-spacing: 0.5px;
}

.chord-visual {
  margin-top: auto;
}

.chord-duration-bar {
  height: 4px;
  border-radius: 2px;
  background: var(--accent);
  opacity: 0.8;
  transition: opacity 0.2s ease;
}

.audio-clip:hover .chord-duration-bar {
  opacity: 1;
}

.sample-clip {
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.instrument-clip {
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.note-overflow {
  background: rgba(255, 255, 255, 0.1);
  padding: 0.125rem 0.5rem;
  border-radius: 4px;
  font-size: 0.625rem;
  color: var(--text-secondary);
  font-style: italic;
}

.generic-clip {
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.clip-waveform {
  display: flex;
  align-items: end;
  gap: 1px;
  height: 50px;
  opacity: 0.7;
}

.waveform-bar {
  width: 2px;
  background: white;
  border-radius: 1px;
  min-height: 2px;
}

.clip-resize-handle {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 8px;
  cursor: ew-resize;
  background: rgba(255, 255, 255, 0.2);
  opacity: 0;
  transition: opacity 0.2s ease;
}

.clip-resize-handle.left {
  left: 0;
  border-radius: 8px 0 0 8px;
}

.clip-resize-handle.right {
  right: 0;
  border-radius: 0 8px 8px 0;
}

.audio-clip:hover .clip-resize-handle {
  opacity: 1;
}

.playhead {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 2px;
  background: var(--accent);
  z-index: 10;
  pointer-events: none;
  box-shadow: 0 0 8px rgba(244, 114, 182, 0.5);
}

.timeline-footer {
  background: var(--surface);
  border-top: 1px solid var(--border);
  padding: 0.75rem 1rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.timeline-controls {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.zoom-level {
  font-size: 0.875rem;
  color: var(--text-secondary);
  font-weight: 500;
  min-width: 50px;
  text-align: center;
}

.icon {
  width: 16px;
  height: 16px;
}

/* Context Menu Styles */
.context-menu-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 998;
}

.context-menu {
  position: fixed;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  box-shadow: var(--shadow-lg);
  z-index: 999;
  min-width: 180px;
  padding: 0.5rem 0;
  backdrop-filter: blur(8px);
}

.context-menu-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
  cursor: pointer;
  transition: background-color 0.2s ease;
  font-size: 0.875rem;
  color: var(--text);
}

.context-menu-item:hover {
  background: rgba(158, 127, 255, 0.1);
}

.context-menu-item.danger {
  color: var(--error);
}

.context-menu-item.danger:hover {
  background: rgba(239, 68, 68, 0.1);
}

.context-menu-divider {
  height: 1px;
  background: var(--border);
  margin: 0.5rem 0;
}

.context-icon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

@media (max-width: 768px) {
  .track-label {
    width: 150px;
    padding: 0.75rem;
  }
  
  .timeline-track {
    height: 60px;
  }
  
  .audio-clip {
    height: 44px;
  }
  
  .context-menu {
    min-width: 160px;
  }
  
  .context-menu-item {
    padding: 0.625rem 0.875rem;
    font-size: 0.8125rem;
  }
}
</style>
