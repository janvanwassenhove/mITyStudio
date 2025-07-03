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
  const isInitialized = ref(false)
  const isInitializing = ref(false)
  const initializationError = ref<string | null>(null)
  
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
  const scheduledEvents = ref<number[]>([])
  let transport: typeof Tone.Transport
  let metronome: Tone.Synth | null = null

  // Computed
  const totalTracks = computed(() => songStructure.value.tracks.length)
  const selectedTrack = computed(() => 
    songStructure.value.tracks.find(track => track.id === selectedTrackId.value)
  )

  // Generate chord progressions and melodies
  const generateNotesForClip = (clip: AudioClip, key: string = 'C'): string[] => {
    const scales = {
      'C': ['C4', 'D4', 'E4', 'F4', 'G4', 'A4', 'B4', 'C5'],
      'G': ['G4', 'A4', 'B4', 'C5', 'D5', 'E5', 'F#5', 'G5'],
      'F': ['F4', 'G4', 'A4', 'Bb4', 'C5', 'D5', 'E5', 'F5'],
      'Am': ['A4', 'B4', 'C5', 'D5', 'E5', 'F5', 'G5', 'A5'],
      'Em': ['E4', 'F#4', 'G4', 'A4', 'B4', 'C5', 'D5', 'E5'],
      'Dm': ['D4', 'E4', 'F4', 'G4', 'A4', 'Bb4', 'C5', 'D5']
    }

    const chords = {
      'C': [['C4', 'E4', 'G4'], ['F4', 'A4', 'C5'], ['G4', 'B4', 'D5'], ['Am4', 'C5', 'E5']],
      'G': [['G4', 'B4', 'D5'], ['C5', 'E5', 'G5'], ['D5', 'F#5', 'A5'], ['Em5', 'G5', 'B5']],
      'F': [['F4', 'A4', 'C5'], ['Bb4', 'D5', 'F5'], ['C5', 'E5', 'G5'], ['Dm5', 'F5', 'A5']]
    }

    const scale = scales[key as keyof typeof scales] || scales['C']
    const chordProgression = chords[key as keyof typeof chords] || chords['C']

    switch (clip.instrument) {
      case 'piano':
      case 'electric-piano':
        const numChords = Math.max(1, Math.floor(clip.duration / 2))
        const notes: string[] = []
        for (let i = 0; i < numChords; i++) {
          const chord = chordProgression[i % chordProgression.length]
          notes.push(...chord)
        }
        return notes

      case 'synth-lead':
        const numNotes = Math.max(1, Math.floor(clip.duration * 2))
        return Array.from({ length: numNotes }, () => 
          scale[Math.floor(Math.random() * scale.length)]
        )

      case 'synth-pad':
        const padChord = chordProgression[0]
        return padChord

      case 'synth':
      default:
        const melodyLength = Math.max(1, Math.floor(clip.duration))
        return Array.from({ length: melodyLength }, () => 
          scale[Math.floor(Math.random() * scale.length)]
        )
    }
  }

  // Simplified initialization with better error handling
  const initializeAudio = async () => {
    if (isInitializing.value) {
      console.log('Already initializing, skipping...')
      return
    }

    try {
      isInitializing.value = true
      initializationError.value = null
      console.log('🎵 Starting audio initialization...')
      
      // Check if already initialized
      if (isInitialized.value) {
        console.log('Audio already initialized')
        return
      }

      // Start Tone.js context with timeout
      console.log('Starting Tone.js context...')
      const startPromise = Tone.start()
      const timeoutPromise = new Promise((_, reject) => 
        setTimeout(() => reject(new Error('Tone.js start timeout')), 5000)
      )
      
      await Promise.race([startPromise, timeoutPromise])
      console.log('✅ Tone.js context started')
      
      // Initialize transport
      transport = Tone.Transport
      transport.bpm.value = songStructure.value.tempo
      console.log('✅ Transport initialized')
      
      // Create instruments with error handling
      console.log('Creating instruments...')
      
      const synth = new Tone.PolySynth(Tone.Synth, {
        oscillator: { type: 'triangle' },
        envelope: { attack: 0.1, decay: 0.3, sustain: 0.3, release: 0.8 }
      }).toDestination()
      
      const piano = new Tone.PolySynth(Tone.Synth, {
        oscillator: { type: 'sine' },
        envelope: { attack: 0.02, decay: 0.3, sustain: 0.3, release: 1.2 }
      }).toDestination()
      
      const electricPiano = new Tone.PolySynth(Tone.Synth, {
        oscillator: { type: 'square' },
        envelope: { attack: 0.05, decay: 0.2, sustain: 0.4, release: 0.8 }
      }).toDestination()
      
      const synthLead = new Tone.MonoSynth({
        oscillator: { type: "sawtooth" },
        envelope: { attack: 0.1, decay: 0.3, sustain: 0.3, release: 0.8 },
        filterEnvelope: { 
          attack: 0.001, 
          decay: 0.7, 
          sustain: 0.1, 
          release: 0.8, 
          baseFrequency: 300, 
          octaves: 4 
        }
      }).toDestination()
      
      const synthPad = new Tone.PolySynth(Tone.Synth, {
        oscillator: { type: "sine" },
        envelope: { attack: 0.8, decay: 0.5, sustain: 0.8, release: 2 }
      }).toDestination()

      // Initialize metronome
      metronome = new Tone.Synth({
        oscillator: { type: 'square' },
        envelope: { attack: 0.001, decay: 0.1, sustain: 0, release: 0.1 }
      }).toDestination()
      
      console.log('✅ Instruments created')
      
      // Store instruments
      instruments.value.clear()
      instruments.value.set('synth', synth)
      instruments.value.set('piano', piano)
      instruments.value.set('electric-piano', electricPiano)
      instruments.value.set('synth-lead', synthLead)
      instruments.value.set('synth-pad', synthPad)
      
      // Set up transport position tracking
      transport.scheduleRepeat((time) => {
        currentTime.value = transport.seconds
      }, "16n")
      
      // Set master volume
      Tone.Destination.volume.value = Tone.gainToDb(masterVolume.value)
      
      // Test audio with a simple beep
      console.log('Testing audio...')
      synth.triggerAttackRelease('C4', '8n')
      
      isInitialized.value = true
      console.log('🎉 Audio initialization completed successfully!')
      
    } catch (error) {
      console.error('❌ Audio initialization failed:', error)
      initializationError.value = error instanceof Error ? error.message : 'Unknown initialization error'
      isInitialized.value = false
    } finally {
      isInitializing.value = false
    }
  }

  const scheduleClip = (clip: AudioClip, track: Track) => {
    const instrument = instruments.value.get(track.instrument)
    if (!instrument || track.muted) return

    const notes = clip.notes || generateNotesForClip(clip, songStructure.value.key)
    if (!notes.length) return

    const clipVolume = clip.volume * track.volume * masterVolume.value
    
    // Set instrument volume
    if ('volume' in instrument) {
      instrument.volume.value = Tone.gainToDb(Math.max(0.01, clipVolume))
    }

    switch (clip.instrument) {
      case 'piano':
      case 'electric-piano':
      case 'synth-pad':
        // Play chords
        const chordDuration = Math.max(0.5, clip.duration / Math.ceil(notes.length / 3))
        for (let i = 0; i < notes.length; i += 3) {
          const chord = notes.slice(i, i + 3).filter(note => note)
          if (chord.length === 0) continue
          
          const chordTime = clip.startTime + (i / 3) * chordDuration
          
          const eventId = transport.schedule((time) => {
            if (instrument && 'triggerAttackRelease' in instrument) {
              instrument.triggerAttackRelease(chord, chordDuration * 0.9, time)
            }
          }, `${chordTime}:0:0`)
          
          scheduledEvents.value.push(eventId)
        }
        break

      case 'synth-lead':
        // Play melody notes in sequence
        const noteDuration = Math.max(0.25, clip.duration / notes.length)
        notes.forEach((note, index) => {
          const noteTime = clip.startTime + index * noteDuration
          
          const eventId = transport.schedule((time) => {
            if (instrument && 'triggerAttackRelease' in instrument) {
              instrument.triggerAttackRelease(note, noteDuration * 0.8, time)
            }
          }, `${noteTime}:0:0`)
          
          scheduledEvents.value.push(eventId)
        })
        break

      case 'synth':
      default:
        // Play simple pattern
        notes.forEach((note, index) => {
          const noteTime = clip.startTime + index
          
          const eventId = transport.schedule((time) => {
            if (instrument && 'triggerAttackRelease' in instrument) {
              instrument.triggerAttackRelease(note, "4n", time)
            }
          }, `${noteTime}:0:0`)
          
          scheduledEvents.value.push(eventId)
        })
        break
    }
  }

  const scheduleMetronome = () => {
    if (!metronomeEnabled.value || !metronome) return

    const totalBeats = songStructure.value.duration * songStructure.value.timeSignature[0]
    
    for (let beat = 0; beat < totalBeats; beat++) {
      const isDownbeat = beat % songStructure.value.timeSignature[0] === 0
      
      const eventId = transport.schedule((time) => {
        if (metronome) {
          metronome.triggerAttackRelease(isDownbeat ? "C5" : "C4", "32n", time)
        }
      }, `${beat}:0:0`)
      
      scheduledEvents.value.push(eventId)
    }
  }

  const clearScheduledEvents = () => {
    scheduledEvents.value.forEach(eventId => {
      transport.clear(eventId)
    })
    scheduledEvents.value = []
  }

  const generateAndScheduleSong = () => {
    if (!isInitialized.value) {
      console.warn('Audio not initialized')
      return
    }

    clearScheduledEvents()

    // Check if any tracks are soloed
    const soloTracks = songStructure.value.tracks.filter(track => track.solo)
    const tracksToPlay = soloTracks.length > 0 ? soloTracks : songStructure.value.tracks

    // Schedule all clips
    tracksToPlay.forEach(track => {
      track.clips.forEach(clip => {
        scheduleClip(clip, track)
      })
    })

    // Schedule metronome
    if (metronomeEnabled.value) {
      scheduleMetronome()
    }

    // Set loop points
    if (isLooping.value) {
      transport.loopStart = 0
      transport.loopEnd = `${songStructure.value.duration}:0:0`
      transport.loop = true
    } else {
      transport.loop = false
    }

    console.log(`Scheduled ${scheduledEvents.value.length} events`)
  }

  const play = async () => {
    try {
      if (!isInitialized.value) {
        await initializeAudio()
      }

      if (!isInitialized.value) {
        console.error('Cannot play: Audio not initialized')
        return
      }

      // Ensure audio context is running
      if (Tone.context.state !== 'running') {
        await Tone.context.resume()
      }

      generateAndScheduleSong()
      transport.start()
      isPlaying.value = true
      console.log('Playback started')
    } catch (error) {
      console.error('Failed to start playback:', error)
    }
  }

  const pause = () => {
    if (transport) {
      transport.pause()
      isPlaying.value = false
    }
  }

  const stop = () => {
    if (transport) {
      transport.stop()
      transport.position = 0
      currentTime.value = 0
      isPlaying.value = false
      clearScheduledEvents()
    }
  }

  const setTempo = (bpm: number) => {
    songStructure.value.tempo = bpm
    if (transport) {
      transport.bpm.value = bpm
    }
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
    
    songStructure.value.tracks.push(newTrack)
    updateSongStructure()
    return newTrack.id
  }

  const removeTrack = (trackId: string) => {
    const index = songStructure.value.tracks.findIndex(track => track.id === trackId)
    if (index !== -1) {
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
        trackId,
        notes: generateNotesForClip({ ...clip, id: '', trackId } as AudioClip, songStructure.value.key)
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
        
        if (updates.instrument || updates.duration) {
          clip.notes = generateNotesForClip(clip, songStructure.value.key)
        }
        
        updateSongStructure()
      }
    }
  }

  const updateSongStructure = () => {
    songStructure.value.updatedAt = new Date().toISOString()
  }

  const loadSongStructure = (structure: SongStructure) => {
    songStructure.value = structure
    if (transport) {
      transport.bpm.value = structure.tempo
    }
  }

  const exportSongStructure = () => {
    return JSON.stringify(songStructure.value, null, 2)
  }

  const toggleLoop = () => {
    isLooping.value = !isLooping.value
    if (transport) {
      transport.loop = isLooping.value
      if (isLooping.value) {
        transport.loopStart = 0
        transport.loopEnd = `${songStructure.value.duration}:0:0`
      }
    }
  }

  const toggleMetronome = () => {
    metronomeEnabled.value = !metronomeEnabled.value
  }

  const setMasterVolume = (volume: number) => {
    masterVolume.value = volume
    if (Tone.Destination) {
      Tone.Destination.volume.value = Tone.gainToDb(volume)
    }
  }

  const setZoom = (newZoom: number) => {
    zoom.value = Math.max(0.1, Math.min(5, newZoom))
  }

  const selectTrack = (trackId: string | null) => {
    selectedTrackId.value = trackId
  }

  // Force initialization with better error handling
  const forceInitialize = async () => {
    console.log('🔄 Force initialize called')
    
    if (isInitializing.value) {
      console.log('Already initializing, please wait...')
      return
    }

    // Reset state
    isInitialized.value = false
    initializationError.value = null
    
    await initializeAudio()
  }

  // Reset audio system
  const resetAudio = () => {
    console.log('🔄 Resetting audio system')
    
    // Stop everything
    if (transport) {
      transport.stop()
      clearScheduledEvents()
    }
    
    // Clear instruments
    instruments.value.clear()
    
    // Reset state
    isInitialized.value = false
    isInitializing.value = false
    initializationError.value = null
    isPlaying.value = false
    currentTime.value = 0
    
    console.log('Audio system reset complete')
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
    isInitialized,
    isInitializing,
    initializationError,
    
    // Computed
    totalTracks,
    selectedTrack,
    
    // Actions
    initializeAudio,
    forceInitialize,
    resetAudio,
    generateAndScheduleSong,
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
