/**
 * Voice Management Composable
 * Handles voice track operations and interactions
 */
import { ref } from 'vue'

export function useVoiceManagement() {
  // State for muted voices (per clip)
  const mutedVoices = ref<Record<string, Set<string>>>({})

  // Voice operations
  const playVoiceTrack = (clip: any, voice: any) => {
    console.log('Playing voice track:', voice.voice_id)
    // Would integrate with audio engine
  }

  const muteVoiceTrack = (clipId: string, voiceId: string) => {
    if (!mutedVoices.value[clipId]) {
      mutedVoices.value[clipId] = new Set()
    }
    
    const clipMutes = mutedVoices.value[clipId]
    if (clipMutes.has(voiceId)) {
      clipMutes.delete(voiceId)
    } else {
      clipMutes.add(voiceId)
    }
  }

  const isVoiceMuted = (clipId: string, voiceId: string) => {
    return mutedVoices.value[clipId]?.has(voiceId) || false
  }

  const editVoice = (clip: any, voice: any, editCallback: (clipId: string) => void) => {
    console.log('Editing voice:', voice.voice_id, 'in clip:', clip.id)
    editCallback(clip.id)
  }

  const removeVoice = (clip: any, voice: any) => {
    if (confirm('Remove this voice track?')) {
      console.log('Removing voice:', voice.voice_id, 'from clip:', clip.id)
      if (clip.voices && Array.isArray(clip.voices)) {
        const index = clip.voices.indexOf(voice)
        if (index !== -1) {
          clip.voices.splice(index, 1)
        }
      }
    }
  }

  const addVoiceToClip = (clip: any, selectedVoice: string) => {
    console.log('Adding new voice to clip:', clip.id)
    
    // Initialize voices array if it doesn't exist
    if (!clip.voices) {
      clip.voices = []
    }
    
    // Add a new voice with default settings
    const newVoice = {
      voice_id: selectedVoice || 'default',
      lyrics: [{
        text: clip.text || '',
        notes: clip.notes ? [...clip.notes] : [],
        start: 0,
        duration: clip.duration || 4
      }]
    }
    
    clip.voices.push(newVoice)
  }

  const playMultiVoiceClip = (clip: any, playSegmentCallback: (clip: any) => void) => {
    console.log('Playing multi-voice clip:', clip.id)
    playSegmentCallback(clip)
  }

  return {
    // State
    mutedVoices,
    
    // Methods
    playVoiceTrack,
    muteVoiceTrack,
    isVoiceMuted,
    editVoice,
    removeVoice,
    addVoiceToClip,
    playMultiVoiceClip
  }
}
