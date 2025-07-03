<template>
  <div class="timeline-editor">
    <div class="timeline-header">
      <div class="timeline-ruler">
        <div 
          v-for="beat in timelineBeats" 
          :key="beat"
          class="ruler-mark"
          :style="{ left: `${beat * beatWidth}px` }"
        >
          <span class="ruler-label">{{ Math.floor(beat / 4) + 1 }}.{{ (beat % 4) + 1 }}</span>
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
          <div class="track-label">
            <span class="track-name">{{ track.name }}</span>
            <span class="track-instrument">{{ $t(`instruments.${track.instrument}`) }}</span>
          </div>
          
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
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useAudioStore, type AudioClip } from '../stores/audioStore'
import { ZoomIn, ZoomOut, Trash2, Copy, Scissors } from 'lucide-vue-next'

const audioStore = useAudioStore()
const timelineContent = ref<HTMLElement>()

const selectedClipId = ref<string | null>(null)
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

// Timeline calculations
const beatWidth = computed(() => 60 * audioStore.zoom) // pixels per beat
const timelineWidth = computed(() => audioStore.songStructure.duration * 4 * beatWidth.value)
const timelineBeats = computed(() => {
  const beats = []
  for (let i = 0; i < audioStore.songStructure.duration * 4; i++) {
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
  
  const newClip = {
    startTime: Math.max(0, startTime),
    duration: 4, // 1 bar default
    type: 'synth' as const,
    instrument: 'synth',
    volume: 0.8,
    effects: {
      reverb: 0,
      delay: 0,
      distortion: 0
    }
  }
  
  audioStore.addClip(trackId, newClip)
}

const selectClip = (clipId: string) => {
  selectedClipId.value = clipId
  hideContextMenu()
}

const showContextMenu = (clipId: string, trackId: string, event: MouseEvent) => {
  event.preventDefault()
  event.stopPropagation()
  
  selectedClipId.value = clipId
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
      selectedClipId.value = null
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
  
  selectedClipId.value = clipId
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

const startResizeClip = (clipId: string, side: 'left' | 'right', event: MouseEvent) => {
  selectedClipId.value = clipId
  isResizing.value = true
  dragStartX.value = event.clientX
  
  document.addEventListener('mousemove', (e) => handleResizeClip(e, side))
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

const stopResizeClip = () => {
  isResizing.value = false
  document.removeEventListener('mousemove', handleResizeClip)
  document.removeEventListener('mouseup', stopResizeClip)
}

const zoomIn = () => {
  audioStore.setZoom(audioStore.zoom * 1.2)
}

const zoomOut = () => {
  audioStore.setZoom(audioStore.zoom / 1.2)
}

// Global click handler to hide context menu
const handleGlobalClick = (event: MouseEvent) => {
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
        selectedClipId.value = null
        break
      }
    }
  }
}

onMounted(() => {
  document.addEventListener('click', handleGlobalClick)
  document.addEventListener('keydown', handleGlobalKeydown)
})

onUnmounted(() => {
  document.removeEventListener('click', handleGlobalClick)
  document.removeEventListener('keydown', handleGlobalKeydown)
  document.removeEventListener('mousemove', handleDragClip)
  document.removeEventListener('mouseup', stopDragClip)
  document.removeEventListener('mousemove', handleResizeClip)
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
  border-left: 1px solid var(--text-secondary);
  display: flex;
  align-items: center;
  padding-left: 4px;
}

.ruler-label {
  font-size: 0.75rem;
  color: var(--text-secondary);
  font-weight: 500;
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
  transition: background-color 0.2s ease;
}

.timeline-track:hover {
  background: rgba(158, 127, 255, 0.05);
}

.timeline-track.selected {
  background: rgba(158, 127, 255, 0.1);
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
  background: linear-gradient(to right, var(--border) 1px, transparent 1px);
  background-size: v-bind('beatWidth + "px"') 100%;
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

.clip-waveform {
  display: flex;
  align-items: end;
  gap: 1px;
  height: 20px;
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
