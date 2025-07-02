import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as Tone from 'tone'

export interface AudioClip {
  id: string
  trackId: string
  startTime: number
  duration: number
  type: 'synth' | 'sample'
  instrument: string
  notes?: string[]
  sampleUrl?: string
  volume: number
  effects: {
    reverb: number
    delay: number
    distortion: number
  }
}

export interface Track {
  id: string
  name: string
  instrument: string
  volume: number
  pan: number
  muted: boolean
  solo: boolean
  clips: AudioClip[]
  effects: {
    reverb: number
    delay: number
    distortion: number
  }
  // New properties for sample support
  sampleUrl?: string
  isSample?: boolean
}

export interface SongStructure {
  id: string
  name: string
  tempo: number
  timeSignature: [number, number]
  key: string
  tracks: Track[]
  duration: number
  createdAt: string
  updatedAt: string
}

export const useAudioStore = defineStore('audio', () => {
  // State
  const isPlaying = ref(false)
  const currentTime = ref(0)
  const isLooping = ref(false)
  const metronomeEnabled = ref(false)
  const masterVolume = ref(0.8)
  const zoom = ref(1)
  const selectedTrackId = ref<string | null>(null)
  
  const songStructure = ref<SongStructure>({
    id: 'default-song',
    name: 'Untitled Song',
    tempo: 120,
    timeSignature: [4, 4],
    key: 'C',
    tracks: [],
    duration: 32,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString()
  })

  // Audio context and instruments
  const instruments = ref<Map<string, Tone.Instrument>>(new Map())
  const samplers = ref<Map<string, Tone.Sampler>>(new Map())
  const effects = ref<Map<string, Tone.Effect>>(new Map())
  let transport: typeof Tone.Transport

  // Computed
  const totalTracks = computed(() => songStructure.value.tracks.length)
  const selectedTrack = computed(() => 
    songStructure.value.tracks.find(track => track.id === selectedTrackId.value)
  )

  // Actions
  const initializeAudio = async () => {
    try {
      await Tone.start()
      transport = Tone.Transport
      transport.bpm.value = songStructure.value.tempo
      
      // Initialize default instruments
      const synth = new Tone.PolySynth(Tone.Synth)
      const piano = new Tone.Sampler({
        urls: {
          C4: "https://tonejs.github.io/audio/salamander/C4.mp3",
          "D#4": "https://tonejs.github.io/audio/salamander/Ds4.mp3",
          "F#4": "https://tonejs.github.io/audio/salamander/Fs4.mp3",
          A4: "https://tonejs.github.io/audio/salamander/A4.mp3",
        },
        release: 1,
      })
      
      // Initialize more instruments
      const electricPiano = new Tone.Sampler({
        urls: {
          C4: "https://tonejs.github.io/audio/casio/C4.mp3",
          "D#4": "https://tonejs.github.io/audio/casio/Ds4.mp3",
          "F#4": "https://tonejs.github.io/audio/casio/Fs4.mp3",
          A4: "https://tonejs.github.io/audio/casio/A4.mp3",
        },
        release: 1,
      })
      
      const synthLead = new Tone.MonoSynth({
        oscillator: { type: "sawtooth" },
        envelope: { attack: 0.1, decay: 0.3, sustain: 0.3, release: 0.8 },
        filterEnvelope: { attack: 0.001, decay: 0.7, sustain: 0.1, release: 0.8, baseFrequency: 300, octaves: 4 }
      })
      
      const synthPad = new Tone.PolySynth(Tone.Synth, {
        oscillator: { type: "sine" },
        envelope: { attack: 0.8, decay: 0.5, sustain: 0.8, release: 2 }
      })
      
      instruments.value.set('synth', synth.toDestination())
      instruments.value.set('piano', piano.toDestination())
      instruments.value.set('electric-piano', electricPiano.toDestination())
      instruments.value.set('synth-lead', synthLead.toDestination())
      instruments.value.set('synth-pad', synthPad.toDestination())
      
      console.log('Audio initialized successfully')
    } catch (error) {
      console.error('Failed to initialize audio:', error)
    }
  }

  const loadSample = async (sampleUrl: string, instrumentId: string) => {
    try {
      const sampler = new Tone.Sampler({
        urls: {
          C4: sampleUrl
        },
        release: 1,
      }).toDestination()
      
      samplers.value.set(instrumentId, sampler)
      return sampler
    } catch (error) {
      console.error('Failed to load sample:', error)
      return null
    }
  }

  const getInstrumentForTrack = (track: Track) => {
    if (track.isSample && track.sampleUrl) {
      return samplers.value.get(track.instrument)
    }
    return instruments.value.get(track.instrument)
  }

  const play = () => {
    if (Tone.context.state !== 'running') {
      Tone.context.resume()
    }
    transport.start()
    isPlaying.value = true
  }

  const pause = () => {
    transport.pause()
    isPlaying.value = false
  }

  const stop = () => {
    transport.stop()
    transport.position = 0
    currentTime.value = 0
    isPlaying.value = false
  }

  const setTempo = (bpm: number) => {
    songStructure.value.tempo = bpm
    transport.bpm.value = bpm
    updateSongStructure()
  }

  const addTrack = (name: string, instrument: string, sampleUrl?: string) => {
    const newTrack: Track = {
      id: `track-${Date.now()}`,
      name,
      instrument,
      volume: 0.8,
      pan: 0,
      muted: false,
      solo: false,
      clips: [],
      effects: {
        reverb: 0,
        delay: 0,
        distortion: 0
      },
      sampleUrl,
      isSample: !!sampleUrl
    }
    
    // If it's a sample, load it
    if (sampleUrl) {
      loadSample(sampleUrl, instrument)
    }
    
    songStructure.value.tracks.push(newTrack)
    updateSongStructure()
    return newTrack.id
  }

  const removeTrack = (trackId: string) => {
    const index = songStructure.value.tracks.findIndex(track => track.id === trackId)
    if (index !== -1) {
      const track = songStructure.value.tracks[index]
      
      // Clean up sampler if it's a sample track
      if (track.isSample) {
        const sampler = samplers.value.get(track.instrument)
        if (sampler) {
          sampler.dispose()
          samplers.value.delete(track.instrument)
        }
      }
      
      songStructure.value.tracks.splice(index, 1)
      if (selectedTrackId.value === trackId) {
        selectedTrackId.value = null
      }
      updateSongStructure()
    }
  }

  const updateTrack = (trackId: string, updates: Partial<Track>) => {
    const track = songStructure.value.tracks.find(t => t.id === trackId)
    if (track) {
      // Handle instrument/sample changes
      if (updates.instrument && updates.instrument !== track.instrument) {
        // Clean up old sampler if it was a sample
        if (track.isSample) {
          const oldSampler = samplers.value.get(track.instrument)
          if (oldSampler) {
            oldSampler.dispose()
            samplers.value.delete(track.instrument)
          }
        }
        
        // Load new sample if needed
        if (updates.sampleUrl) {
          loadSample(updates.sampleUrl, updates.instrument)
          updates.isSample = true
        } else {
          updates.isSample = false
          updates.sampleUrl = undefined
        }
      }
      
      Object.assign(track, updates)
      updateSongStructure()
    }
  }

  const addClip = (trackId: string, clip: Omit<AudioClip, 'id' | 'trackId'>) => {
    const track = songStructure.value.tracks.find(t => t.id === trackId)
    if (track) {
      const newClip: AudioClip = {
        ...clip,
        id: `clip-${Date.now()}`,
        trackId
      }
      track.clips.push(newClip)
      updateSongStructure()
      return newClip.id
    }
    return null
  }

  const removeClip = (trackId: string, clipId: string) => {
    const track = songStructure.value.tracks.find(t => t.id === trackId)
    if (track) {
      const index = track.clips.findIndex(clip => clip.id === clipId)
      if (index !== -1) {
        track.clips.splice(index, 1)
        updateSongStructure()
      }
    }
  }

  const updateClip = (trackId: string, clipId: string, updates: Partial<AudioClip>) => {
    const track = songStructure.value.tracks.find(t => t.id === trackId)
    if (track) {
      const clip = track.clips.find(c => c.id === clipId)
      if (clip) {
        Object.assign(clip, updates)
        updateSongStructure()
      }
    }
  }

  const updateSongStructure = () => {
    songStructure.value.updatedAt = new Date().toISOString()
  }

  const loadSongStructure = (structure: SongStructure) => {
    songStructure.value = structure
    transport.bpm.value = structure.tempo
    
    // Load samples for sample tracks
    structure.tracks.forEach(track => {
      if (track.isSample && track.sampleUrl) {
        loadSample(track.sampleUrl, track.instrument)
      }
    })
  }

  const exportSongStructure = () => {
    return JSON.stringify(songStructure.value, null, 2)
  }

  const toggleLoop = () => {
    isLooping.value = !isLooping.value
    transport.loop = isLooping.value
  }

  const toggleMetronome = () => {
    metronomeEnabled.value = !metronomeEnabled.value
  }

  const setMasterVolume = (volume: number) => {
    masterVolume.value = volume
    Tone.Destination.volume.value = Tone.gainToDb(volume)
  }

  const setZoom = (newZoom: number) => {
    zoom.value = Math.max(0.1, Math.min(5, newZoom))
  }

  const selectTrack = (trackId: string | null) => {
    selectedTrackId.value = trackId
  }

  return {
    // State
    isPlaying,
    currentTime,
    isLooping,
    metronomeEnabled,
    masterVolume,
    zoom,
    selectedTrackId,
    songStructure,
    
    // Computed
    totalTracks,
    selectedTrack,
    
    // Actions
    initializeAudio,
    loadSample,
    getInstrumentForTrack,
    play,
    pause,
    stop,
    setTempo,
    addTrack,
    removeTrack,
    updateTrack,
    addClip,
    removeClip,
    updateClip,
    updateSongStructure,
    loadSongStructure,
    exportSongStructure,
    toggleLoop,
    toggleMetronome,
    setMasterVolume,
    setZoom,
    selectTrack
  }
})
