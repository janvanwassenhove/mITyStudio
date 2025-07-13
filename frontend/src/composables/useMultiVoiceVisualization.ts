/**
 * Multi-Voice Visualization Composable
 * Handles advanced visualization logic for multi-voice lyrics clips
 */
import { ref, computed } from 'vue'

export function useMultiVoiceVisualization() {
  // State
  const showTimelines = ref(true)
  const timelineZoom = ref(1)
  const selectedFragment = ref<string | null>(null)

  // Methods
  const toggleVoiceVisualization = () => {
    showTimelines.value = !showTimelines.value
  }

  const getVoiceColor = (voiceIndex: number): string => {
    const colors = [
      '#3b82f6', '#ef4444', '#10b981', '#f59e0b', 
      '#8b5cf6', '#ec4899', '#14b8a6', '#f97316'
    ]
    return colors[voiceIndex % colors.length]
  }

  const zoomTimeline = (direction: 'in' | 'out') => {
    const factor = direction === 'in' ? 1.5 : 0.75
    timelineZoom.value = Math.max(0.5, Math.min(timelineZoom.value * factor, 4))
  }

  const resetTimelineZoom = () => {
    timelineZoom.value = 1
  }

  const getTimelineTicks = (clip: any) => {
    const ticks = []
    const step = timelineZoom.value > 2 ? 0.5 : 1
    for (let i = 0; i <= clip.duration; i += step) {
      ticks.push(i)
    }
    return ticks
  }

  const getTimelineWidth = (clip: any) => {
    return Math.max(clip.duration * 50 * timelineZoom.value, 400)
  }

  const getTimePosition = (time: number, clip: any) => {
    return (time / clip.duration) * 100
  }

  // Fragment helpers
  const selectFragment = (clip: any, voice: any, fragment: any) => {
    selectedFragment.value = `${clip.id}-${voice.voice_id}-${fragment.start}`
  }

  const getFragmentWidth = (fragment: any) => {
    const duration = fragment.duration || 1
    return Math.max(duration * 10, 5) // Minimum 5% width
  }

  const isFragmentSelected = (clipId: string, voiceId: string, fragmentIndex: number) => {
    return selectedFragment.value === `${clipId}-${voiceId}-${fragmentIndex}`
  }

  const getFragmentDuration = (fragment: any) => {
    return fragment.duration || 1
  }

  const getTotalVoiceDuration = (voice: any) => {
    if (!voice.lyrics) return '0.0'
    return voice.lyrics.reduce((sum: number, fragment: any) => 
      sum + (fragment.duration || 1), 0
    ).toFixed(1)
  }

  // Note color mapping
  const getNoteColor = (note: string) => {
    const noteColors: Record<string, string> = {
      'C': '#e74c3c', 'C#': '#e67e22', 'D': '#f39c12', 'D#': '#f1c40f',
      'E': '#2ecc71', 'F': '#27ae60', 'F#': '#16a085', 'G': '#3498db',
      'G#': '#2980b9', 'A': '#9b59b6', 'A#': '#8e44ad', 'B': '#e91e63'
    }
    const noteName = note.replace(/\d+$/, '') // Remove octave number
    return noteColors[noteName] || '#95a5a6'
  }

  return {
    // State
    showTimelines,
    timelineZoom,
    selectedFragment,
    
    // Methods
    toggleVoiceVisualization,
    getVoiceColor,
    zoomTimeline,
    resetTimelineZoom,
    getTimelineTicks,
    getTimelineWidth,
    getTimePosition,
    selectFragment,
    getFragmentWidth,
    isFragmentSelected,
    getFragmentDuration,
    getTotalVoiceDuration,
    getNoteColor
  }
}
