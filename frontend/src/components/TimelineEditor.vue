<template>
  <div class="timeline-editor">
    <div class="timeline-header" ref="timelineHeader">
      <div class="timeline-ruler" @click="seekToPosition">
        <div 
          v-for="beat in timelineBeats" 
          :key="beat"
          class="ruler-mark"
          :class="{ 'bar-line': beat % 4 === 0, 'beat-line': beat % 4 !== 0 }"
          :style="{ left: `${beat * beatWidth}px` }"
        >
          <span v-if="beat % 4 === 0" class="ruler-label">{{ Math.floor(beat / 4) + 1 }}</span>
        </div>
        <!-- Playhead in ruler -->
        <div class="ruler-playhead" :style="{ left: `${playheadPosition}px` }"></div>
      </div>
    </div>
    
    <div class="timeline-content" ref="timelineContent" @scroll="syncTimelineScroll">
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
                <!-- If a clip provides a waveform (samples, recordings, vocals), render the waveform canvas first so
                     vocal recordings and live-updated clips show waveform and grow as data arrives. Fallback to chord
                     visualization only when no waveform exists. -->
                <div v-if="clip.waveform && clip.waveform.length" class="sample-clip">
                  <span class="clip-name">{{ clip.instrument }}</span>
                  <div class="clip-waveform">
                    <canvas
                      :ref="el => setClipWaveformCanvas(el, clip)"
                      class="waveform-canvas"
                      :height="20"
                    ></canvas>
                  </div>
                </div>

                <!-- Chord Sample Clips (fallback when no waveform is available) -->
                <div v-else-if="clip.type === 'sample' && clip.sampleUrl && isChordSample(clip)" class="chord-clip">
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
                
                <!-- Instrument Clips with Notes -->
                <div v-else-if="clip.notes && clip.notes.length" class="instrument-clip">
                  <span class="clip-name">{{ clip.instrument }}</span>
                  <div class="clip-notes">
                    <span v-for="(note, idx) in clip.notes.slice(0, 6)" :key="idx" class="clip-note">{{ note }}</span>
                    <span v-if="clip.notes.length > 6" class="note-overflow">+{{ clip.notes.length - 6 }}</span>
                  </div>
                </div>
                
                <!-- Lyrics Clips -->
                <div v-else-if="clip.type === 'lyrics' && clip.voices && clip.voices.length" class="lyrics-clip">
                  <span class="clip-name">{{ clip.instrument }} - {{ clip.voiceId }}</span>
                  <div class="clip-lyrics">
                    <span v-for="(voice, idx) in clip.voices.slice(0, 1)" :key="idx" class="lyrics-text">
                      {{ voice.lyrics && voice.lyrics[0] ? voice.lyrics[0].text.substring(0, 50) + (voice.lyrics[0].text.length > 50 ? '...' : '') : 'Lyrics' }}
                    </span>
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
    
    <!-- Master Lyric Lane -->
    <div class="master-lyric-lane" v-if="vocalTracks.length > 0">
      <div class="lyric-lane-header">
        <div class="lane-label">
          <span class="lane-title">Master Lyrics</span>
          <div class="vocal-track-toggles">
            <button 
              class="toggle-all-btn"
              :class="{ 'active': allTracksVisible }"
              @click="toggleAllTracks"
              title="Toggle All Vocals"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 2L2 7l10 5 10-5-10-5z"/>
                <path d="M2 17l10 5 10-5"/>
                <path d="M2 12l10 5 10-5"/>
              </svg>
              All
            </button>
            <div class="track-toggle-divider"></div>
            <button 
              v-for="track in vocalTracks" 
              :key="track.id"
              class="track-toggle-btn"
              :class="{ 
                'active': vocalTracksVisibility[track.id],
                'speaker-lead': getTrackSpeakerType(track) === 'lead',
                'speaker-harmony': getTrackSpeakerType(track) === 'harmony',
                'speaker-choir': getTrackSpeakerType(track) === 'choir'
              }"
              @click="toggleTrackVisibility(track.id)"
              :title="`Toggle ${track.name} (${track.voiceId || 'Unknown Voice'})`"
            >
              <svg v-if="getTrackSpeakerType(track) === 'lead'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
              </svg>
              <svg v-else-if="getTrackSpeakerType(track) === 'harmony'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"/>
                <path d="M8 12h8"/>
                <path d="M12 8v8"/>
              </svg>
              <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="3"/>
                <circle cx="12" cy="12" r="8"/>
                <circle cx="12" cy="12" r="13"/>
              </svg>
              {{ getTrackShortName(track) }}
            </button>
          </div>
        </div>
      </div>
      <div class="lyric-lane-content" ref="lyricLaneContent" @scroll="syncLyricLaneScroll">
        <div class="lyric-tracks-stacked">
          <div 
            v-for="track in vocalTracks"
            :key="track.id"
            v-show="vocalTracksVisibility[track.id]"
            class="lyric-track-row"
            :class="`speaker-${getTrackSpeakerType(track)}`"
          >
            <div class="lyric-words-container">
              <div 
                v-for="(word, index) in masterLyricsByTrack[track.id] || []"
                :key="`${word.trackId}-${word.clipId}-${index}`"
                class="lyric-word-chip"
                :class="[
                  `speaker-${word.speakerType}`,
                  { 
                    'active': isWordActive(word),
                    'karaoke-highlight': isWordActive(word) && audioStore.isPlaying
                  }
                ]"
                :style="getLyricChipStyle(word)"
                @click="seekToWord(word)"
              >
                <div class="word-text">{{ word.text }}</div>
                <div v-if="isWordActive(word) && audioStore.isPlaying" class="karaoke-sweep" :style="getKaraokeSweepStyle(word)"></div>
              </div>
            </div>
            <div class="lyric-track-label">
              <span class="track-name">{{ getTrackShortName(track) }}</span>
              <span class="track-voice">{{ track.voiceId || 'Default' }}</span>
            </div>
          </div>
        </div>
        <!-- Playhead in lyric lane -->
        <div class="lyric-lane-playhead" :style="{ left: `${playheadPosition}px` }"></div>
      </div>
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
        <button class="btn btn-ghost" @click="toggleMetronome">
          <span v-if="audioStore.metronomeEnabled">🔊</span>
          <span v-else>🔈</span>
          Metronome
        </button>
        <!-- Development helper for testing master lyric lane -->
        <button class="btn btn-secondary" @click="addTestVocals" style="margin-left: 1rem;">
          📝 Add Test Vocals
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick, type ComponentPublicInstance } from 'vue'
import { useAudioStore, type AudioClip, type LyricFragment } from '../stores/audioStore'
import { useSampleStore } from '../stores/sampleStore'
import { ZoomIn, ZoomOut, Trash2, Copy, Scissors } from 'lucide-vue-next'
import { drawWaveform } from '../utils/waveform'
import { extractChordFromSampleUrl } from '../utils/chordVisualization'

// Master Lyric Lane Interface
interface MasterLyricWord {
  text: string
  startTime: number
  duration: number
  endTime: number
  trackId: string
  clipId: string
  voiceId: string
  speakerType: 'lead' | 'harmony' | 'choir'
  originalLyric: LyricFragment
  syllables?: any[]
}

const audioStore = useAudioStore()
const sampleStore = useSampleStore()
const timelineContent = ref<HTMLElement>()
const lyricLaneContent = ref<HTMLElement>()

// Master Lyric Lane State
const selectedVocalTrack = ref<string>('all')
const masterLyrics = ref<MasterLyricWord[]>([])
const vocalTracksVisibility = ref<Record<string, boolean>>({})
const masterLyricsByTrack = ref<Record<string, MasterLyricWord[]>>({})

const selectedClipId = computed(() => audioStore.selectedClipId)
const isDragging = ref(false)
const isResizing = ref(false)
const dragStartX = ref(0)
const dragStartTime = ref(0)

// Auto-scroll state
const isAutoScrolling = ref(false)
const lastPlayheadPosition = ref(0)
const userScrollTimeout = ref<number | null>(null)

// Context menu state
const contextMenu = ref({
  visible: false,
  x: 0,
  y: 0,
  clipId: '',
  trackId: ''
})

// Timeline header ref for syncing scroll
const timelineHeader = ref<HTMLElement>()

// Sync timeline ruler scroll with content scroll
const syncTimelineScroll = () => {
  if (!timelineContent.value || !timelineHeader.value || isResetting.value) return
  
  // During playback, prevent manual scrolling from interfering with auto-scroll
  if (audioStore.isPlaying) {
    // Delay manual scroll sync to allow auto-scroll to take priority
    setTimeout(() => {
      if (timelineHeader.value && timelineContent.value) {
        timelineHeader.value.scrollLeft = timelineContent.value.scrollLeft
      }
      if (lyricLaneContent.value && timelineContent.value) {
        lyricLaneContent.value.scrollLeft = timelineContent.value.scrollLeft
      }
    }, 16) // ~1 frame delay
    return
  }
  
  // Sync the ruler scroll with content scroll
  timelineHeader.value.scrollLeft = timelineContent.value.scrollLeft
  
  // Also sync the master lyric lane to stay aligned with timeline content
  if (lyricLaneContent.value) {
    lyricLaneContent.value.scrollLeft = timelineContent.value.scrollLeft
  }
  
  // Temporarily disable auto-scroll when user manually scrolls
  if (userScrollTimeout.value) {
    clearTimeout(userScrollTimeout.value)
  }
  
  // Re-enable auto-scroll after user stops scrolling for 2 seconds
  userScrollTimeout.value = setTimeout(() => {
    // Auto-scroll is now re-enabled
  }, 2000) as any
}

// Store canvas refs for each clip (we register canvas even when waveform is not yet available so
// recordings that start with an empty waveform can be drawn live once data arrives).
const clipWaveformCanvases = ref<Record<string, HTMLCanvasElement | null>>({})

function setClipWaveformCanvas(el: Element | ComponentPublicInstance | null, clip: AudioClip) {
  const canvas = el instanceof Element ? el : null

  if (canvas && canvas instanceof HTMLCanvasElement) {
    clipWaveformCanvases.value[clip.id] = canvas
    
    // Defensive check: ensure canvas is still in DOM before manipulating
    if (!canvas.parentElement) {
      return
    }
    
    // Size the canvas to the clip's rendered size (width depends on duration & zoom)
    const width = Math.max(40, Math.round((clip.duration || 1) * beatWidth.value * 4))
    canvas.width = width
    const parentClip = canvas.closest('.audio-clip') as HTMLElement | null
    if (parentClip) {
      canvas.height = parentClip.offsetHeight
    } else {
      canvas.height = 20
    }

    // If waveform data already exists, draw it now. If not, clear the canvas to a subtle background
    if (clip.waveform && clip.waveform.length) {
      drawWaveform(canvas, clip.waveform)
    } else {
      const ctx = canvas.getContext('2d')
      if (ctx) {
        ctx.clearRect(0, 0, canvas.width, canvas.height)
        ctx.fillStyle = 'rgba(255,255,255,0.02)'
        ctx.fillRect(0, 0, canvas.width, canvas.height)
      }
    }
  } else if (!canvas) {
    // Clean up ref if canvas is removed
    delete clipWaveformCanvases.value[clip.id]
  }
}

// Watch for waveform changes across clips and redraw their canvases when data arrives or changes
watch(
  () => audioStore.songStructure.tracks.map(t => t.clips.map(c => ({ id: c.id, waveform: c.waveform, duration: c.duration }))),
  async () => {
    await nextTick()
    audioStore.songStructure.tracks.forEach(track => {
      track.clips.forEach(clip => {
        const canvas = clipWaveformCanvases.value[clip.id]
        if (!canvas) return

        // Coerce duration to finite number, skip clip if clearly invalid
        const dur = Number.isFinite(clip.duration) ? clip.duration : 0
        const safeDur = Math.max(0.01, Math.min(dur, 3600)) // between 10ms and 1 hour
        const width = Math.max(40, Math.round(safeDur * beatWidth.value * 4))
        canvas.width = width
        const parentClip = canvas.closest('.audio-clip') as HTMLElement | null
        canvas.height = parentClip ? parentClip.offsetHeight : 20

        if (Array.isArray(clip.waveform) && clip.waveform.length) {
          try {
            drawWaveform(canvas, clip.waveform)
          } catch (e) {
            // Defensive: if drawWaveform fails, clear to placeholder
            const ctx = canvas.getContext('2d')
            if (ctx) {
              ctx.clearRect(0, 0, canvas.width, canvas.height)
              ctx.fillStyle = 'rgba(255,255,255,0.02)'
              ctx.fillRect(0, 0, canvas.width, canvas.height)
            }
          }
        } else {
          const ctx = canvas.getContext('2d')
          if (ctx) {
            ctx.clearRect(0, 0, canvas.width, canvas.height)
            ctx.fillStyle = 'rgba(255,255,255,0.02)'
            ctx.fillRect(0, 0, canvas.width, canvas.height)
          }
        }
      })
    })
  },
  { deep: true }
)

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

// Auto-scroll functionality
const isResetting = ref(false)

const resetToStart = () => {
  if (!timelineContent.value) return
  
  console.log('🔄 Resetting timeline to start position')
  isResetting.value = true
  
  // Use immediate scrolling instead of smooth for more reliable reset
  timelineContent.value.scrollLeft = 0
  
  // Scroll header/ruler to beginning
  if (timelineHeader.value) {
    timelineHeader.value.scrollLeft = 0
  }
  
  // Scroll master lyric lane to beginning
  if (lyricLaneContent.value) {
    lyricLaneContent.value.scrollLeft = 0
  }
  
  // Reset the flag after a short delay
  setTimeout(() => {
    isResetting.value = false
  }, 100)
  
  console.log('✅ Timeline reset to start completed')
}

const autoScrollToPlayhead = () => {
  if (!timelineContent.value || isDragging.value || isResizing.value) return
  
  const container = timelineContent.value
  const scrollLeft = container.scrollLeft
  const containerWidth = container.clientWidth
  const playheadPos = playheadPosition.value
  
  // During playback, be more aggressive about keeping playhead centered
  if (audioStore.isPlaying) {
    // Keep playhead in the center third of the screen during playback
    const centerThird = containerWidth / 3
    const leftBoundary = scrollLeft + centerThird
    const rightBoundary = scrollLeft + containerWidth - centerThird
    
    // Check if playhead is outside the center area during playback
    if (playheadPos < leftBoundary || playheadPos > rightBoundary) {
      // Center the playhead during playback
      const newScrollLeft = Math.max(0, playheadPos - containerWidth / 2)
      
      // Use immediate scroll during playback for smooth following
      container.scrollLeft = newScrollLeft
      
      // Sync other elements immediately
      if (timelineHeader.value) {
        timelineHeader.value.scrollLeft = newScrollLeft
      }
      
      if (lyricLaneContent.value) {
        lyricLaneContent.value.scrollLeft = newScrollLeft
      }
    }
  } else {
    // When not playing, use the original larger margins
    const scrollMargin = containerWidth * 0.1 // 10% of container width
    const leftBoundary = scrollLeft + scrollMargin
    const rightBoundary = scrollLeft + containerWidth - scrollMargin
    
    // Special case: if playhead is at the very beginning (0), always scroll to start
    if (playheadPos === 0) {
      // Scroll to the beginning
      container.scrollTo({
        left: 0,
        behavior: 'smooth'
      })
      
      // Also sync the header (ruler)
      if (timelineHeader.value) {
        try {
          timelineHeader.value.scrollTo({ left: 0, behavior: 'smooth' })
        } catch (e) {
          timelineHeader.value.scrollLeft = 0
        }
      }
      
      // Also sync the master lyric lane
      if (lyricLaneContent.value) {
        try {
          lyricLaneContent.value.scrollTo({ left: 0, behavior: 'smooth' })
        } catch (e) {
          lyricLaneContent.value.scrollLeft = 0
        }
      }
    } else if (playheadPos < leftBoundary || playheadPos > rightBoundary) {
      // Check if playhead is outside the visible area (with margins)
      // Calculate new scroll position to center the playhead
      const newScrollLeft = Math.max(0, playheadPos - containerWidth / 2)
      
      // Smooth scroll to new position when not playing
      container.scrollTo({
        left: newScrollLeft,
        behavior: 'smooth'
      })
      
      // Also sync the header (ruler) so both tracks and ruler follow the playhead
      if (timelineHeader.value) {
        try {
          timelineHeader.value.scrollTo({ left: newScrollLeft, behavior: 'smooth' })
        } catch (e) {
          // Fallback for browsers that don't support smooth option on element.scrollTo
          timelineHeader.value.scrollLeft = newScrollLeft
        }
      }
      
      // Also sync the master lyric lane to follow the playhead
      if (lyricLaneContent.value) {
        try {
          lyricLaneContent.value.scrollTo({ left: newScrollLeft, behavior: 'smooth' })
        } catch (e) {
          // Fallback for browsers that don't support smooth option on element.scrollTo
          lyricLaneContent.value.scrollLeft = newScrollLeft
        }
      }
    }
  }

  isAutoScrolling.value = true
  // Reset auto-scrolling flag after animation
  setTimeout(() => {
    isAutoScrolling.value = false
  }, 300)
}

// Watch for playhead position changes during playback
watch(
  () => audioStore.currentTime,
  (newTime, oldTime) => {
    console.log(`⏱️ CurrentTime changed: ${oldTime} → ${newTime}, isPlaying: ${audioStore.isPlaying}`)
    
    // During playback, continuously update scroll to follow playhead
    if (audioStore.isPlaying && newTime > oldTime) {
      lastPlayheadPosition.value = playheadPosition.value
      autoScrollToPlayhead()
    } else if (!audioStore.isPlaying && newTime === 0 && oldTime > 0) {
      // When stopped and reset to 0, use dedicated reset function
      console.log('🛑 Detected stop - resetting to start')
      nextTick(() => {
        resetToStart()
      })
    } else if (!audioStore.isPlaying && Math.abs(newTime - oldTime) > 0.05) {
      // When not playing, auto-scroll for significant jumps (seeking)
      lastPlayheadPosition.value = playheadPosition.value
      autoScrollToPlayhead()
    }
  }
)

// Watch for when audio stops to reset scroll position
watch(
  () => audioStore.isPlaying,
  (isPlaying, wasPlaying) => {
    console.log(`🎵 IsPlaying changed: ${wasPlaying} → ${isPlaying}, currentTime: ${audioStore.currentTime}`)
    
    // When audio stops, reset scroll to beginning if currentTime is 0
    if (wasPlaying && !isPlaying && audioStore.currentTime === 0) {
      console.log('🛑 Audio stopped and reset - triggering reset to start')
      nextTick(() => {
        resetToStart()
      })
    }
  }
)

// Also watch for zoom changes to maintain playhead visibility
watch(
  () => audioStore.zoom,
  () => {
    // Delay to allow for layout recalculation
    nextTick(() => {
      if (audioStore.isPlaying) {
        autoScrollToPlayhead()
      }
    })
  }
)

const getClipStyle = (clip: AudioClip) => {
  const start = Number.isFinite(clip.startTime) ? clip.startTime : 0
  const dur = Number.isFinite(clip.duration) ? clip.duration : 0
  const left = start * beatWidth.value * 4 // Convert beats to pixels
  const width = Math.max(1, dur * beatWidth.value * 4)
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
        distortion: 0,
        pitchShift: 0,
        chorus: 0,
        filter: 0,
        bitcrush: 0
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
      distortion: 0,
      pitchShift: 0,
      chorus: 0,
      filter: 0,
      bitcrush: 0
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

// Handle clicking on timeline ruler to seek
const seekToPosition = (event: MouseEvent) => {
  if (!timelineHeader.value) return
  
  const rect = timelineHeader.value.getBoundingClientRect()
  const clickX = event.clientX - rect.left + timelineHeader.value.scrollLeft
  const timePosition = clickX / (beatWidth.value * 4) // Convert pixels to seconds
  
  // Update the current time directly
  const newTime = Math.max(0, timePosition)
  audioStore.currentTime = newTime

  // If audio is currently playing, pause (clears scheduled events and stores position)
  // then resume playback from the newly set time. Using pause+play avoids reset done by stop().
  if (audioStore.isPlaying) {
    audioStore.pause()
    // Small delay to ensure scheduled events are cleared before rescheduling
    setTimeout(() => {
      audioStore.play()
    }, 50)
  }
  
  // Auto-scroll to the new position if it's outside the visible area
  setTimeout(() => {
    autoScrollToPlayhead()
  }, 50)
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

// Master Lyrics Lane Functionality
const vocalTracks = computed(() => {
  return audioStore.songStructure.tracks.filter(track => 
    track.category === 'vocal' || track.instrument === 'vocals' || 
    track.clips.some(clip => clip.type === 'lyrics')
  )
})

const updateMasterLyrics = () => {
  const lyrics: MasterLyricWord[] = []
  console.log('Updating master lyrics, vocalTracks:', vocalTracks.value)
  
  const tracksToProcess = selectedVocalTrack.value === 'all' 
    ? vocalTracks.value
    : selectedVocalTrack.value === 'lead'
    ? vocalTracks.value.filter(track => 
        track.name.toLowerCase().includes('lead') || 
        track.name.toLowerCase().includes('main')
      ).slice(0, 1) // Take only the first lead track
    : vocalTracks.value.filter(track => track.id === selectedVocalTrack.value)
  
  console.log('Tracks to process:', tracksToProcess)

  tracksToProcess.forEach(track => {
    console.log(`Processing track ${track.name}:`, track)
    track.clips.forEach(clip => {
      console.log(`Processing clip:`, clip)
      if (clip.type !== 'lyrics') {
        console.log(`Skipping clip with type: ${clip.type}`)
        return
      }

      // Determine speaker type based on track name and voice
      let speakerType: 'lead' | 'harmony' | 'choir' = 'lead'
      const trackNameLower = track.name.toLowerCase()
      if (trackNameLower.includes('harmony') || trackNameLower.includes('backing')) {
        speakerType = 'harmony'
      } else if (trackNameLower.includes('choir') || trackNameLower.includes('chorus')) {
        speakerType = 'choir'
      }

      // Process both new structure (voices array) and legacy structure (lyrics array)
      const lyricSources = []
      if (clip.voices && clip.voices.length > 0) {
        console.log('Found clip.voices:', clip.voices)
        clip.voices.forEach(voice => lyricSources.push(...voice.lyrics))
      }
      if (clip.lyrics && clip.lyrics.length > 0) {
        console.log('Found clip.lyrics:', clip.lyrics)
        lyricSources.push(...clip.lyrics)
      }
      
      console.log('Lyric sources for this clip:', lyricSources)

      lyricSources.forEach((lyric) => {
        const words = lyric.text.split(/\s+/).filter(word => word.length > 0)
        const wordDuration = lyric.duration || (lyric.durations ? lyric.durations.reduce((a, b) => a + b, 0) : 1)
        const avgWordDuration = wordDuration / words.length

        words.forEach((word, wordIndex) => {
          const wordStartTime = clip.startTime + lyric.start + (wordIndex * avgWordDuration)
          const wordEndTime = wordStartTime + avgWordDuration
          
          lyrics.push({
            text: word,
            startTime: wordStartTime,
            duration: avgWordDuration,
            endTime: wordEndTime,
            trackId: track.id,
            clipId: clip.id,
            voiceId: clip.voiceId || track.voiceId || 'unknown',
            speakerType,
            originalLyric: lyric
          })
        })
      })
    })
  })

  // Sort by start time
  lyrics.sort((a, b) => a.startTime - b.startTime)
  console.log('Final master lyrics:', lyrics)
  masterLyrics.value = lyrics
  
  // Update the per-track lyrics
  updateMasterLyricsByTrack()
}

// New function to organize lyrics by track for stacked display
const updateMasterLyricsByTrack = () => {
  const lyricsByTrack: Record<string, MasterLyricWord[]> = {}
  
  vocalTracks.value.forEach(track => {
    lyricsByTrack[track.id] = []
    
    // Initialize visibility if not set
    if (vocalTracksVisibility.value[track.id] === undefined) {
      vocalTracksVisibility.value[track.id] = true
    }
    
    track.clips.forEach(clip => {
      if (clip.type !== 'lyrics') return

      // Determine speaker type based on track name and voice
      let speakerType: 'lead' | 'harmony' | 'choir' = 'lead'
      const trackNameLower = track.name.toLowerCase()
      if (trackNameLower.includes('harmony') || trackNameLower.includes('backing')) {
        speakerType = 'harmony'
      } else if (trackNameLower.includes('choir') || trackNameLower.includes('chorus')) {
        speakerType = 'choir'
      }

      // Process both new structure (voices array) and legacy structure (lyrics array)
      const lyricSources = []
      if (clip.voices && clip.voices.length > 0) {
        clip.voices.forEach(voice => lyricSources.push(...voice.lyrics))
      }
      if (clip.lyrics && clip.lyrics.length > 0) {
        lyricSources.push(...clip.lyrics)
      }

      lyricSources.forEach((lyric) => {
        const words = lyric.text.split(/\s+/).filter(word => word.length > 0)
        const wordDuration = lyric.duration || (lyric.durations ? lyric.durations.reduce((a, b) => a + b, 0) : 1)
        const avgWordDuration = wordDuration / words.length

        words.forEach((word, wordIndex) => {
          const wordStartTime = clip.startTime + lyric.start + (wordIndex * avgWordDuration)
          const wordEndTime = wordStartTime + avgWordDuration
          
          lyricsByTrack[track.id].push({
            text: word,
            startTime: wordStartTime,
            endTime: wordEndTime,
            duration: avgWordDuration,
            trackId: track.id,
            clipId: clip.id,
            voiceId: track.voiceId || 'default',
            speakerType,
            originalLyric: lyric,
            syllables: lyric.syllables || []
          })
        })
      })
    })
    
    // Sort each track's lyrics by start time
    lyricsByTrack[track.id].sort((a, b) => a.startTime - b.startTime)
  })
  
  masterLyricsByTrack.value = lyricsByTrack
}

// Helper functions for UI
const getTrackSpeakerType = (track: any): 'lead' | 'harmony' | 'choir' => {
  const trackNameLower = track.name.toLowerCase()
  if (trackNameLower.includes('harmony') || trackNameLower.includes('backing')) {
    return 'harmony'
  } else if (trackNameLower.includes('choir') || trackNameLower.includes('chorus')) {
    return 'choir'
  }
  return 'lead'
}

const getTrackShortName = (track: any): string => {
  return track.name.length > 8 ? track.name.substring(0, 8) + '...' : track.name
}

// Track visibility toggle functions
const toggleTrackVisibility = (trackId: string) => {
  vocalTracksVisibility.value[trackId] = !vocalTracksVisibility.value[trackId]
}

const toggleAllTracks = () => {
  const allVisible = allTracksVisible.value
  vocalTracks.value.forEach(track => {
    vocalTracksVisibility.value[track.id] = !allVisible
  })
}

const allTracksVisible = computed(() => {
  return vocalTracks.value.every(track => vocalTracksVisibility.value[track.id])
})

const getLyricChipStyle = (word: MasterLyricWord) => {
  const left = word.startTime * beatWidth.value * 4  // Same calculation as clips and playhead
  const width = Math.max(30, word.duration * beatWidth.value * 4)
  
  return {
    position: 'absolute' as const,
    left: `${left}px`,
    width: `${width}px`,
    height: '28px',
    zIndex: 1
  }
}

const isWordActive = (word: MasterLyricWord) => {
  const currentTime = audioStore.currentTime
  return currentTime >= word.startTime && currentTime < word.endTime
}

const getKaraokeSweepStyle = (word: MasterLyricWord) => {
  const currentTime = audioStore.currentTime
  const progress = Math.min(1, Math.max(0, (currentTime - word.startTime) / word.duration))
  
  return {
    width: `${progress * 100}%`,
    transition: audioStore.isPlaying ? 'width 0.1s ease-out' : 'none'
  }
}

const seekToWord = (word: MasterLyricWord) => {
  // Update the current time directly
  audioStore.currentTime = word.startTime

  // If audio is currently playing, pause then resume from the new position
  if (audioStore.isPlaying) {
    audioStore.pause()
    // Small delay to ensure scheduled events are cleared before rescheduling
    setTimeout(() => {
      audioStore.play()
    }, 50)
  }
  
  // Auto-scroll to the new position
  setTimeout(() => {
    autoScrollToPlayhead()
  }, 50)
}

const syncLyricLaneScroll = () => {
  if (!lyricLaneContent.value || !timelineContent.value || isResetting.value) return
  
  // Sync timeline content scroll with lyric lane scroll
  timelineContent.value.scrollLeft = lyricLaneContent.value.scrollLeft
  
  // Also sync with timeline header
  if (timelineHeader.value) {
    timelineHeader.value.scrollLeft = lyricLaneContent.value.scrollLeft
  }
  
  // Temporarily disable auto-scroll when user manually scrolls the lyric lane
  if (userScrollTimeout.value) {
    clearTimeout(userScrollTimeout.value)
  }
  
  // Re-enable auto-scroll after user stops scrolling for 2 seconds
  userScrollTimeout.value = setTimeout(() => {
    // Auto-scroll is now re-enabled
  }, 2000) as any
}

// Development helper to add test vocal tracks for testing master lyric lane
const addTestVocals = () => {
  // Create test lead vocal track
  const leadTrack = {
    id: "track-test-lead-vocals",
    name: "Test Lead Vocals",
    instrument: "vocals",
    category: "vocal",
    voiceId: "soprano01",
    volume: 0.8,
    pan: 0,
    muted: false,
    solo: false,
    clips: [{
      id: "clip-test-lead-1",
      trackId: "track-test-lead-vocals",
      startTime: 0,
      duration: 8,
      type: "lyrics" as const,
      instrument: "vocals",
      voiceId: "soprano01",
      volume: 0.8,
      sectionId: "verse1",
      sectionSpans: ["verse1"],
      effects: {
        reverb: 0.2,
        delay: 0.1,
        distortion: 0,
        pitchShift: 0,
        chorus: 0,
        filter: 0,
        bitcrush: 0
      },
      voices: [{
        voice_id: "soprano01",
        lyrics: [
          {
            text: "Walking through the digital world",
            notes: ["C4", "D4", "E4", "F4", "G4"],
            start: 0,
            durations: [0.5, 0.5, 0.5, 0.5, 1.0],
            syllables: [
              { t: "Walk", noteIdx: [0], dur: 0.5 },
              { t: "ing", noteIdx: [1], dur: 0.5 },
              { t: "through", noteIdx: [2], dur: 0.5 },
              { t: "the", noteIdx: [3], dur: 0.25 },
              { t: "dig", noteIdx: [3], dur: 0.25 },
              { t: "it", noteIdx: [4], dur: 0.5 },
              { t: "al", noteIdx: [4], dur: 0.5 }
            ],
            phonemes: ["w", "ɔ", "k", "ɪ", "ŋ", "θ", "r", "u", "ð", "ə", "d", "ɪ", "dʒ", "ɪ", "t", "ə", "l"]
          },
          {
            text: "Code and music come alive",
            notes: ["A4", "G4", "F4", "E4", "D4"],
            start: 3.5,
            durations: [0.6, 0.6, 0.6, 0.6, 1.0],
            syllables: [
              { t: "Code", noteIdx: [0], dur: 0.6 },
              { t: "and", noteIdx: [1], dur: 0.6 },
              { t: "mu", noteIdx: [2], dur: 0.3 },
              { t: "sic", noteIdx: [2], dur: 0.3 },
              { t: "come", noteIdx: [3], dur: 0.6 },
              { t: "a", noteIdx: [4], dur: 0.5 },
              { t: "live", noteIdx: [4], dur: 0.5 }
            ],
            phonemes: ["k", "oʊ", "d", "æ", "n", "d", "m", "ju", "z", "ɪ", "k", "k", "ʌ", "m", "ə", "l", "aɪ", "v"]
          }
        ]
      }]
    }],
    effects: {
      reverb: 0.2,
      delay: 0.1,
      distortion: 0,
      pitchShift: 0,
      chorus: 0,
      filter: 0,
      bitcrush: 0
    }
  }

  // Create harmony vocal track
  const harmonyTrack = {
    id: "track-test-harmony-vocals", 
    name: "Test Harmony Vocals",
    instrument: "vocals",
    category: "vocal",
    voiceId: "alto01",
    volume: 0.6,
    pan: -0.3,
    muted: false,
    solo: false,
    clips: [{
      id: "clip-test-harmony-1",
      trackId: "track-test-harmony-vocals",
      startTime: 1,
      duration: 6,
      type: "lyrics" as const,
      instrument: "vocals",
      voiceId: "alto01",
      volume: 0.6,
      sectionId: "verse1",
      sectionSpans: ["verse1"],
      effects: {
        reverb: 0.3,
        delay: 0.2,
        distortion: 0,
        pitchShift: 0,
        chorus: 0,
        filter: 0,
        bitcrush: 0
      },
      voices: [{
        voice_id: "alto01",
        lyrics: [
          {
            text: "Digital world echoes",
            notes: ["E4", "F4", "G4"],
            start: 0.5,
            durations: [0.8, 0.8, 1.4],
            syllables: [
              { t: "Dig", noteIdx: [0], dur: 0.4 },
              { t: "it", noteIdx: [0], dur: 0.4 },
              { t: "al", noteIdx: [1], dur: 0.4 },
              { t: "world", noteIdx: [1], dur: 0.4 },
              { t: "ech", noteIdx: [2], dur: 0.7 },
              { t: "oes", noteIdx: [2], dur: 0.7 }
            ],
            phonemes: ["d", "ɪ", "dʒ", "ɪ", "t", "ə", "l", "w", "ɜr", "l", "d", "ɛ", "k", "oʊ", "z"]
          },
          {
            text: "Music flows",
            notes: ["C5", "B4"],
            start: 4,
            durations: [1.0, 1.0],
            syllables: [
              { t: "Mu", noteIdx: [0], dur: 0.5 },
              { t: "sic", noteIdx: [0], dur: 0.5 },
              { t: "flows", noteIdx: [1], dur: 1.0, melisma: true }
            ],
            phonemes: ["m", "ju", "z", "ɪ", "k", "f", "l", "oʊ", "z"]
          }
        ]
      }]
    }],
    effects: {
      reverb: 0.3,
      delay: 0.2,
      distortion: 0,
      pitchShift: 0,
      chorus: 0,
      filter: 0,
      bitcrush: 0
    }
  }

  // Add tracks to audio store directly
  audioStore.songStructure.tracks.push(leadTrack)
  audioStore.songStructure.tracks.push(harmonyTrack)
  
  // Update song duration to accommodate the vocals
  if (audioStore.songStructure.duration < 16) {
    audioStore.songStructure.duration = 16
  }
  
  // Trigger master lyrics update
  nextTick(() => {
    updateMasterLyrics()
  })
}

// Watch for song structure changes and update master lyrics
watch(
  () => [audioStore.songStructure.tracks, selectedVocalTrack.value],
  () => updateMasterLyrics(),
  { deep: true, immediate: true }
)

// Watch timeline scroll to sync lyric lane
watch(
  () => timelineContent.value?.scrollLeft,
  (newScrollLeft) => {
    if (lyricLaneContent.value && newScrollLeft !== undefined) {
      lyricLaneContent.value.scrollLeft = newScrollLeft
    }
  }
)

// Update CSS custom property for timeline width
watch(timelineWidth, (newWidth) => {
  document.documentElement.style.setProperty('--timeline-width', `${newWidth}px`)
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
  
  // Clear user scroll timeout
  if (userScrollTimeout.value) {
    clearTimeout(userScrollTimeout.value)
  }
})
</script>

<style scoped>
/* Master Lyric Lane Styles */
.master-lyric-lane {
  background: var(--surface);
  border-top: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
  min-height: 80px;
  display: flex;
  flex-direction: column;
}

.lyric-lane-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.5rem 1rem;
  background: rgba(158, 127, 255, 0.05);
  border-bottom: 1px solid var(--border);
  min-height: 32px;
}

.lane-label {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.lane-title {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text);
  min-width: 100px;
}

.vocal-track-toggles {
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.toggle-all-btn {
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--text);
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.toggle-all-btn:hover {
  background: var(--hover);
}

.toggle-all-btn.active {
  background: var(--accent);
  color: white;
}

.track-toggle-divider {
  width: 1px;
  height: 20px;
  background: var(--border);
  margin: 0 0.25rem;
}

.track-toggle-btn {
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--text);
  padding: 0.25rem 0.375rem;
  border-radius: 4px;
  font-size: 0.75rem;
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  gap: 0.25rem;
  min-width: 60px;
}

.track-toggle-btn:hover {
  background: var(--hover);
}

.track-toggle-btn.active {
  border-color: var(--accent);
  background: rgba(158, 127, 255, 0.1);
}

.track-toggle-btn.speaker-lead.active {
  background: rgba(147, 51, 234, 0.1);
  border-color: rgb(147, 51, 234);
  color: rgb(147, 51, 234);
}

.track-toggle-btn.speaker-harmony.active {
  background: rgba(236, 72, 153, 0.1);
  border-color: rgb(236, 72, 153);
  color: rgb(236, 72, 153);
}

.track-toggle-btn.speaker-choir.active {
  background: rgba(34, 197, 94, 0.1);
  border-color: rgb(34, 197, 94);
  color: rgb(34, 197, 94);
}

.track-toggle-btn svg {
  width: 12px;
  height: 12px;
}

.lyric-lane-content {
  flex: 1;
  overflow: auto;
  position: relative;
  background: var(--background);
  min-height: 40px;
}

.lyric-tracks-stacked {
  position: relative;
  width: 100%;
  min-width: var(--timeline-width, 800px);
}

.lyric-track-row {
  display: flex;
  flex-direction: column;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  min-height: 50px;
}

.lyric-track-row:last-child {
  border-bottom: none;
}

.lyric-track-label {
  display: flex;
  flex-direction: row;
  justify-content: flex-start;
  align-items: center;
  gap: 0.5rem;
  padding: 0.25rem 0.5rem;
  background: rgba(0, 0, 0, 0.3);
  border-top: 1px solid var(--border);
  font-size: 0.75rem;
  min-height: 20px;
  order: 2;
  margin-top: 30px;
}

.lyric-track-label .track-name {
  font-weight: 600;
  color: var(--text);
  text-overflow: ellipsis;
  overflow: hidden;
  white-space: nowrap;
}

.lyric-track-label .track-voice {
  color: var(--text-muted);
  font-size: 0.625rem;
  text-overflow: ellipsis;
  overflow: hidden;
  white-space: nowrap;
}

.lyric-track-row.speaker-lead .lyric-track-label {
  border-left: 3px solid rgb(147, 51, 234);
}

.lyric-track-row.speaker-harmony .lyric-track-label {
  border-left: 3px solid rgb(236, 72, 153);
}

.lyric-track-row.speaker-choir .lyric-track-label {
  border-left: 3px solid rgb(34, 197, 94);
}

.lyric-words-container {
  position: relative;
  height: 30px;
  width: 100%;
  flex: 1;
  order: 1;
  margin-top: 5px;
}

.lyric-word-chip {
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(158, 127, 255, 0.8);
  color: white;
  border-radius: 14px;
  font-size: 0.75rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  border: 2px solid transparent;
  min-width: 30px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  padding: 0 8px;
}

.lyric-word-chip:hover {
  transform: scale(1.05);
  background: rgba(158, 127, 255, 0.9);
  box-shadow: 0 2px 8px rgba(158, 127, 255, 0.3);
}

/* Speaker Type Styling */
.lyric-word-chip.speaker-lead {
  background: rgba(158, 127, 255, 0.9); /* Lead = solid fill (primary) */
  border-color: rgba(158, 127, 255, 1);
}

.lyric-word-chip.speaker-harmony {
  background: rgba(244, 114, 182, 0.3); /* Harmony = outline style */
  border-color: rgba(244, 114, 182, 1);
  color: rgba(244, 114, 182, 1);
  border-width: 2px;
}

.lyric-word-chip.speaker-choir {
  background: repeating-linear-gradient(
    45deg,
    rgba(34, 197, 94, 0.3),
    rgba(34, 197, 94, 0.3) 4px,
    rgba(34, 197, 94, 0.1) 4px,
    rgba(34, 197, 94, 0.1) 8px
  ); /* Choir = striped */
  border-color: rgba(34, 197, 94, 1);
  color: rgba(34, 197, 94, 1);
}

/* Active word highlighting */
.lyric-word-chip.active {
  background: rgba(255, 193, 7, 0.9);
  color: var(--surface);
  transform: scale(1.1);
  box-shadow: 0 4px 12px rgba(255, 193, 7, 0.4);
  z-index: 10;
}

/* Karaoke highlight animation */
.lyric-word-chip.karaoke-highlight {
  position: relative;
  overflow: hidden;
}

.karaoke-sweep {
  position: absolute;
  top: 0;
  left: 0;
  bottom: 0;
  background: linear-gradient(
    to right,
    rgba(255, 255, 255, 0.4),
    rgba(255, 255, 255, 0.6),
    rgba(255, 255, 255, 0.4)
  );
  pointer-events: none;
  z-index: 1;
}

.word-text {
  position: relative;
  z-index: 2;
}

/* Lyric lane playhead */
.lyric-lane-playhead {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 2px;
  background: var(--accent);
  z-index: 20;
  pointer-events: none;
  box-shadow: 0 0 4px rgba(244, 114, 182, 0.5);
}

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
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: none; /* Firefox */
  -ms-overflow-style: none; /* IE and Edge */
}

.timeline-header::-webkit-scrollbar {
  display: none; /* Chrome, Safari, Opera */
}

.timeline-ruler {
  position: relative;
  height: 100%;
  background: linear-gradient(to right, var(--border) 1px, transparent 1px);
  background-size: v-bind('beatWidth + "px"') 100%;
  min-width: v-bind('timelineWidth + "px"');
  width: v-bind('timelineWidth + "px"');
  cursor: pointer;
  user-select: none;
}

.timeline-ruler:hover {
  background-color: rgba(158, 127, 255, 0.05);
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
  pointer-events: none;
}

.ruler-playhead {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 2px;
  background: var(--accent);
  z-index: 20;
  pointer-events: none;
  box-shadow: 0 0 4px rgba(244, 114, 182, 0.5);
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

.lyrics-clip {
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  background: linear-gradient(135deg, #7c3aed, #a855f7);
}

.clip-lyrics {
  flex: 1;
  display: flex;
  align-items: center;
  padding: 0.25rem;
  overflow: hidden;
}

.lyrics-text {
  font-size: 0.75rem;
  color: white;
  opacity: 0.9;
  line-height: 1.2;
  word-break: break-word;
  hyphens: auto;
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
