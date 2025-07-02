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
              :style="getClipStyle(clip)"
              @click.stop="selectClip(clip.id)"
              @mousedown="startDragClip(clip.id, $event)"
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
import { ZoomIn, ZoomOut } from 'lucide-vue-next'

const audioStore = useAudioStore()
const timelineContent = ref<HTMLElement>()

const selectedClipId = ref<string | null>(null)
const isDragging = ref(false)
const isResizing = ref(false)
const dragStartX = ref(0)
const dragStartTime = ref(0)

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
}

const startDragClip = (clipId: string, event: MouseEvent) => {
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

onMounted(() => {
  // Set up timeline scrolling and interaction
})

onUnmounted(() => {
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
}
</style>
