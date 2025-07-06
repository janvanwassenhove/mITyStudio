import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as Tone from 'tone'
import { 
  ChordService, 
  type ChordProgressionType, 
  type SampleInstrument 
} from '../services/chordService'

export interface AudioClip {
  id: string
  trackId: string
  startTime: number
  duration: number
  type: 'synth' | 'sample'
  instrument: string
  notes?: string[]
  sampleUrl?: string
  sampleDuration?: number // Optional sample duration (e.g., 1 for 1s samples)
  volume: number
  effects: {
    reverb: number
    delay: number
    distortion: number
  }
  // Add waveform for sample clips
  waveform?: number[]
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
  const isPaused = ref(false)
  const currentTime = ref(0)
  const isLooping = ref(false)
  const metronomeEnabled = ref(false)
  const masterVolume = ref(0.8)
  const zoom = ref(1)
  const selectedTrackId = ref<string | null>(null)
  const isInitialized = ref(false)
  const isInitializing = ref(false)
  const initializationError = ref<string | null>(null)
  const metronomeBars = ref(4)
  
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
  const instruments = ref<Map<string, any>>(new Map())
  const scheduledEvents = ref<number[]>([])
  let transport: typeof Tone.Transport
  let metronome: Tone.Synth | null = null

  // Track all active sample players
  const samplePlayers: Tone.Player[] = []
  
  // Track all HTML audio elements for previews
  const previewAudioElements = ref<Set<HTMLAudioElement>>(new Set())

  // Track the position tracking event ID separately
  let positionTrackingEventId: number | null = null

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
      
      // Preload common samples
      console.log('Preloading samples...')
      try {
        await Promise.all([
          preloadSamplesForInstrument('guitar', 1),
          preloadSamplesForInstrument('piano', 1),
          preloadSamplesForInstrument('piano', 2)
        ])
        console.log('✅ Sample preloading completed')
      } catch (error) {
        console.warn('Sample preloading had issues:', error)
      }
      
      // Set up transport position tracking
      setupPositionTracking()
      
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

  // Setup position tracking separately from music events
  const setupPositionTracking = () => {
    if (positionTrackingEventId !== null) {
      transport.clear(positionTrackingEventId)
    }
    positionTrackingEventId = transport.scheduleRepeat((_time) => {
      currentTime.value = transport.seconds
    }, "16n")
    console.log('✅ Position tracking established')
  }

  // Enhanced sample loading and management
  const preloadedSamples = ref<Map<string, Map<string, Tone.Player>>>(new Map()) // instrument -> note -> player

  // Preload samples for an instrument
  const preloadSamplesForInstrument = async (instrument: string, sampleDuration: number = 1) => {
    const instrumentKey = `${instrument}_${sampleDuration}s`
    if (preloadedSamples.value.has(instrumentKey)) {
      return preloadedSamples.value.get(instrumentKey)!
    }

    const sampleMap = new Map<string, Tone.Player>()
    
    // Common notes to preload
    const notesToPreload = [
      'C4', 'C#4', 'D4', 'D#4', 'E4', 'F4', 'F#4', 'G4', 'G#4', 'A4', 'A#4', 'B4',
      'C5', 'C#5', 'D5', 'D#5', 'E5', 'F5', 'F#5', 'G5', 'G#5', 'A5', 'A#5', 'B5'
    ]

    console.log(`Preloading samples for ${instrument} (${sampleDuration}s duration)...`)
    
    const loadPromises = notesToPreload.map(async (note) => {
      try {
        const samplePath = `samples/${instrument}/${sampleDuration}s/wav/${note}.wav`
        const player = new Tone.Player({
          url: samplePath,
          autostart: false,
          volume: 0, // Will be set per use
          fadeIn: 0.01,
          fadeOut: 0.01
        })

        try {
          await Tone.loaded()
          if (player.loaded) {
            sampleMap.set(note, player)
            console.log(`✅ Loaded sample: ${samplePath}`)
          }
        } catch (error) {
          console.warn(`Failed to load sample: ${samplePath}`, error)
        }
      } catch (error) {
        console.warn(`Error loading sample for ${note}:`, error)
      }
    })

    await Promise.all(loadPromises)
    preloadedSamples.value.set(instrumentKey, sampleMap)
    console.log(`🎵 Preloaded ${sampleMap.size} samples for ${instrument}`)
    
    return sampleMap
  }

  // Get or create a sample player
  const getSamplePlayer = async (instrument: string, note: string, sampleDuration: number = 1): Promise<Tone.Player | null> => {
    const instrumentKey = `${instrument}_${sampleDuration}s`
    let instrumentSamples = preloadedSamples.value.get(instrumentKey)
    
    if (!instrumentSamples) {
      instrumentSamples = await preloadSamplesForInstrument(instrument, sampleDuration)
    }
    
    const player = instrumentSamples.get(note)
    if (player && player.loaded) {
      // Create a new player instance for parallel playback
      const samplePath = `samples/${instrument}/${sampleDuration}s/wav/${note}.wav`
      return new Tone.Player({
        url: samplePath,
        autostart: false,
        volume: 0,
        fadeIn: 0.01,
        fadeOut: 0.01
      }).toDestination()
    }
    
    // Fallback: create individual player
    const samplePath = `samples/${instrument}/${sampleDuration}s/wav/${note}.wav`
    try {
      const fallbackPlayer = new Tone.Player({
        url: samplePath,
        autostart: false,
        volume: 0,
        fadeIn: 0.01,
        fadeOut: 0.01
      })
      
      await Tone.loaded()
      return fallbackPlayer.loaded ? fallbackPlayer : null
    } catch (error) {
      console.error(`Failed to create fallback player for ${samplePath}:`, error)
      return null
    }
  }

  // Enhanced clip scheduling with precise timing and looping
  const scheduleClip = (clip: AudioClip, track: Track, fromPosition: number = 0) => {
    if (track.muted) return

    const startTime = clip.startTime
    const duration = clip.duration
    const clipEndTime = startTime + duration
    
    // Skip clips that have completely finished before the current position
    if (clipEndTime <= fromPosition && fromPosition > 0) {
      console.log(`[scheduleClip] Skipping clip that ended before position ${fromPosition}:`, clip)
      return
    }

    // Handle sample-based clips with looping
    if (clip.type === 'sample' && clip.notes && clip.notes.length > 0) {
      scheduleClipWithSamples(clip, track, fromPosition)
      return
    }

    // Handle synth clips
    scheduleClipWithSynth(clip, track, fromPosition)
  }

  // Schedule clip using samples with precise timing and looping
  const scheduleClipWithSamples = async (clip: AudioClip, track: Track, fromPosition: number = 0) => {
    const notes = clip.notes || []
    if (notes.length === 0) {
      console.warn('No notes provided for sample clip:', clip)
      return
    }

    const sampleDuration = clip.sampleDuration || 1 // Default to 1 second samples
    const totalLoops = Math.ceil(clip.duration / sampleDuration)
    const volume = (clip.volume ?? 1) * (track.volume ?? 1) * (masterVolume.value ?? 1)
    
    console.log(`[scheduleClipWithSamples] Scheduling clip with ${notes.length} notes, ${totalLoops} loops, ${sampleDuration}s per loop`)

    // Schedule each loop iteration
    for (let loopIndex = 0; loopIndex < totalLoops; loopIndex++) {
      const loopStartTime = clip.startTime + (loopIndex * sampleDuration)
      
      // Skip loops that are before the current position
      if (loopStartTime + sampleDuration <= fromPosition) continue
      
      // Get the note for this loop (cycle through the chord progression)
      const noteIndex = loopIndex % notes.length
      const currentNote = notes[noteIndex]
      
      // Schedule this note
      const eventId = transport.schedule(async (time) => {
        try {
          const player = await getSamplePlayer(track.instrument, currentNote, sampleDuration)
          if (player) {
            player.volume.value = Tone.gainToDb(Math.max(0.01, volume))
            player.start(time, 0, sampleDuration)
            console.log(`🎵 Playing ${currentNote} at ${time.toFixed(2)}s (loop ${loopIndex + 1}/${totalLoops})`)
          } else {
            console.warn(`Failed to get player for ${track.instrument} ${currentNote}`)
          }
        } catch (error) {
          console.error(`Error playing sample:`, error)
        }
      }, `${loopStartTime}:0:0`)
      
      scheduledEvents.value.push(eventId)
    }
  }

  // Schedule clip using synthesizer
  const scheduleClipWithSynth = (clip: AudioClip, track: Track, fromPosition: number = 0) => {
    const instrument = instruments.value.get(track.instrument)
    if (!instrument) {
      console.log(`[scheduleClipWithSynth] No instrument found for ${track.instrument}`)
      return
    }

    const notes = clip.notes || generateNotesForClip(clip, songStructure.value.key)
    if (!notes.length) {
      console.log(`[scheduleClipWithSynth] No notes for clip`, clip)
      return
    }

    const sampleDuration = clip.sampleDuration || 1
    const totalLoops = Math.ceil(clip.duration / sampleDuration)
    const clipVolume = clip.volume * track.volume * masterVolume.value
    
    if ('volume' in instrument) {
      instrument.volume.value = Tone.gainToDb(Math.max(0.01, clipVolume))
    }

    console.log(`[scheduleClipWithSynth] Scheduling synth clip with ${notes.length} notes, ${totalLoops} loops`)

    // Schedule each loop iteration
    for (let loopIndex = 0; loopIndex < totalLoops; loopIndex++) {
      const loopStartTime = clip.startTime + (loopIndex * sampleDuration)
      
      // Skip loops that are before the current position
      if (loopStartTime + sampleDuration <= fromPosition) continue
      
      // For chord instruments, play all notes simultaneously
      if (['piano', 'electric-piano', 'synth-pad'].includes(clip.instrument)) {
        const eventId = transport.schedule((time) => {
          if (instrument && 'triggerAttackRelease' in instrument) {
            const noteDuration = Math.min(sampleDuration * 0.9, 2) // Slightly shorter to prevent overlap
            instrument.triggerAttackRelease(notes, noteDuration, time)
            console.log(`🎹 Playing chord [${notes.join(', ')}] at ${time.toFixed(2)}s (loop ${loopIndex + 1}/${totalLoops})`)
          }
        }, `${loopStartTime}:0:0`)
        
        scheduledEvents.value.push(eventId)
      } else {
        // For lead instruments, cycle through notes
        const noteIndex = loopIndex % notes.length
        const currentNote = notes[noteIndex]
        
        const eventId = transport.schedule((time) => {
          if (instrument && 'triggerAttackRelease' in instrument) {
            const noteDuration = Math.min(sampleDuration * 0.9, 2)
            instrument.triggerAttackRelease(currentNote, noteDuration, time)
            console.log(`🎵 Playing note ${currentNote} at ${time.toFixed(2)}s (loop ${loopIndex + 1}/${totalLoops})`)
          }
        }, `${loopStartTime}:0:0`)
        
        scheduledEvents.value.push(eventId)
      }
    }
  }

  const scheduleMetronome = (fromPosition: number = 0) => {
    if (!metronomeEnabled.value || !metronome) return

    const totalBeats = metronomeBars.value * songStructure.value.timeSignature[0]
    for (let beat = 0; beat < totalBeats; beat++) {
      const beatTime = beat
      
      // Skip beats that are before the current position
      if (beatTime < fromPosition) continue
      
      const isDownbeat = beat % songStructure.value.timeSignature[0] === 0
      const eventId = transport.schedule((time) => {
        if (metronome) {
          metronome.triggerAttackRelease(isDownbeat ? "C5" : "C4", "32n", time)
        }
      }, `${beatTime}:0:0`)
      scheduledEvents.value.push(eventId)
    }
  }

  const clearScheduledEvents = () => {
    // Clear music events but preserve position tracking
    scheduledEvents.value.forEach(eventId => {
      transport.clear(eventId)
    })
    scheduledEvents.value = []
    console.log('🧹 Cleared scheduled music events (position tracking preserved)')
  }

  const generateAndScheduleSong = (fromPosition: number = 0) => {
    if (!isInitialized.value) {
      console.warn('Audio not initialized')
      return
    }

    clearScheduledEvents()

    // Check if any tracks are soloed
    const soloTracks = songStructure.value.tracks.filter(track => track.solo)
    const tracksToPlay = soloTracks.length > 0 ? soloTracks : songStructure.value.tracks

    console.log(`[generateAndScheduleSong] Scheduling for tracks from position ${fromPosition}:`, tracksToPlay.map(t => t.name))
    
    // For fresh playback (fromPosition = 0), ensure all clips are scheduled
    if (fromPosition === 0) {
      console.log(`[generateAndScheduleSong] Fresh playback - scheduling all clips`)
    }
    
    // Schedule all clips
    tracksToPlay.forEach(track => {
      track.clips.forEach(clip => {
        scheduleClip(clip, track, fromPosition)
      })
    })

    // Schedule metronome
    if (metronomeEnabled.value) {
      scheduleMetronome(fromPosition)
    }

    // Set loop points - ensure proper loop end time based on actual content
    if (isLooping.value) {
      // Calculate the actual end time based on the longest clip
      let maxEndTime = songStructure.value.duration
      tracksToPlay.forEach(track => {
        track.clips.forEach(clip => {
          const clipEndTime = clip.startTime + clip.duration
          maxEndTime = Math.max(maxEndTime, clipEndTime)
        })
      })
      
      transport.loopStart = 0
      transport.loopEnd = `${Math.max(maxEndTime, 4)}:0:0` // Ensure minimum 4 second loop
      transport.loop = true
      console.log(`[generateAndScheduleSong] Loop enabled: 0 to ${maxEndTime}s`)
    } else {
      transport.loop = false
      console.log(`[generateAndScheduleSong] Loop disabled`)
    }

    console.log(`[generateAndScheduleSong] Scheduled events:`, scheduledEvents.value.length)
  }

  // Immediate scheduling for resume from pause - starts audio right away
  const generateAndScheduleSongImmediate = (fromPosition: number) => {
    if (!isInitialized.value) {
      console.warn('Audio not initialized')
      return
    }

    clearScheduledEvents()

    // Check if any tracks are soloed
    const soloTracks = songStructure.value.tracks.filter(track => track.solo)
    const tracksToPlay = soloTracks.length > 0 ? soloTracks : songStructure.value.tracks

    console.log(`[generateAndScheduleSongImmediate] Starting immediate playback from position ${fromPosition}:`, tracksToPlay.map(t => t.name))
    
    // Start currently playing clips immediately
    tracksToPlay.forEach(track => {
      track.clips.forEach(clip => {
        scheduleClipImmediate(clip, track, fromPosition)
      })
    })

    // Schedule future events normally
    tracksToPlay.forEach(track => {
      track.clips.forEach(clip => {
        scheduleClip(clip, track, fromPosition)
      })
    })

    // Schedule metronome from current position
    if (metronomeEnabled.value) {
      scheduleMetronome(fromPosition)
    }

    // Set loop points
    if (isLooping.value) {
      transport.loopStart = 0
      transport.loopEnd = `${songStructure.value.duration}:0:0`
      transport.loop = true
    } else {
      transport.loop = false
    }

    console.log(`[generateAndScheduleSongImmediate] Immediate scheduling complete`)
  }

  // Immediate clip scheduling for clips that should be playing right now
  const scheduleClipImmediate = (clip: AudioClip, track: Track, fromPosition: number) => {
    // Only handle sample clips that are currently playing
    if (clip.type === 'sample' && clip.sampleUrl) {
      if (track.muted) return
      
      const startTime = clip.startTime
      const duration = clip.duration
      const clipEndTime = startTime + duration
      
      // Only start clips that should be playing right now
      if (fromPosition >= startTime && fromPosition < clipEndTime) {
        const volume = (clip.volume ?? 1) * (track.volume ?? 1) * (masterVolume.value ?? 1)
        
        // Use Tone.Player for sample playback
        const player = new Tone.Player({
          url: clip.sampleUrl,
          autostart: false,
          volume: Tone.gainToDb(Math.max(0.01, volume)),
        }).toDestination()
        
        samplePlayers.push(player)
        
        // Calculate how far into the sample we should start
        const sampleOffset = fromPosition - startTime
        const remainingDuration = clipEndTime - fromPosition
        
        console.log(`[scheduleClipImmediate] Starting sample immediately with offset: ${sampleOffset}, duration: ${remainingDuration}`)
        
        // Start immediately (no scheduling delay)
        player.start("+0.01", sampleOffset, remainingDuration)
      }
    }
    
    // Handle instruments that should be playing right now
    const instrument = instruments.value.get(track.instrument)
    if (!instrument || track.muted || clip.type === 'sample') {
      return
    }

    const clipEndTime = clip.startTime + clip.duration
    
    // Only trigger instruments for clips that should be playing right now
    if (fromPosition >= clip.startTime && fromPosition < clipEndTime) {
      const notes = clip.notes || generateNotesForClip(clip, songStructure.value.key)
      if (!notes.length) return

      const clipVolume = clip.volume * track.volume * masterVolume.value
      if ('volume' in instrument) {
        instrument.volume.value = Tone.gainToDb(Math.max(0.01, clipVolume))
      }

      console.log(`[scheduleClipImmediate] Triggering instrument immediately:`, clip.instrument)

      // Trigger the current note/chord immediately based on position within clip
      const timeIntoClip = fromPosition - clip.startTime
      
      switch (clip.instrument) {
        case 'piano':
        case 'electric-piano':
        case 'synth-pad':
          const chordDuration = Math.max(0.5, clip.duration / Math.ceil(notes.length / 3))
          const currentChordIndex = Math.floor(timeIntoClip / chordDuration) * 3
          const chord = notes.slice(currentChordIndex, currentChordIndex + 3).filter(note => note)
          if (chord.length > 0 && 'triggerAttackRelease' in instrument) {
            const remainingChordTime = chordDuration - (timeIntoClip % chordDuration)
            instrument.triggerAttackRelease(chord, Math.min(remainingChordTime, chordDuration) * 0.9, "+0.01")
          }
          break
        case 'synth-lead':
          const noteDuration = Math.max(0.25, clip.duration / notes.length)
          const currentNoteIndex = Math.floor(timeIntoClip / noteDuration)
          if (currentNoteIndex < notes.length && 'triggerAttackRelease' in instrument) {
            const remainingNoteTime = noteDuration - (timeIntoClip % noteDuration)
            instrument.triggerAttackRelease(notes[currentNoteIndex], Math.min(remainingNoteTime, noteDuration) * 0.8, "+0.01")
          }
          break
        case 'synth':
        default:
          const currentNoteIdx = Math.floor(timeIntoClip)
          if (currentNoteIdx < notes.length && 'triggerAttackRelease' in instrument) {
            instrument.triggerAttackRelease(notes[currentNoteIdx], "4n", "+0.01")
          }
          break
      }
    }
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

      // Check if we're resuming from pause
      const isResumingFromPause = isPaused.value
      
      if (isResumingFromPause) {
        console.log('[play] Resuming from pause...')
        const pausedPosition = transport.seconds
        console.log(`[play] Paused position: ${transport.position} (${pausedPosition}s)`)
        
        // Clear pause state
        isPaused.value = false
        
        // Don't reset transport position - keep it where it was paused
        // This eliminates the need for position offset calculations
        
        // Ensure position tracking is active
        if (positionTrackingEventId === null) {
          setupPositionTracking()
        }
        
        // Reschedule events from current position using immediate scheduling
        console.log('[play] Rescheduling events from current position...')
        generateAndScheduleSongImmediate(pausedPosition)
        
        transport.start()
        isPlaying.value = true
        console.log('[play] Resumed from pause with immediate scheduling')
      } else {
        console.log('[play] Starting fresh playback...')
        
        // Ensure position tracking is active
        if (positionTrackingEventId === null) {
          setupPositionTracking()
        }
        
        generateAndScheduleSong()
        transport.start()
        isPlaying.value = true
        console.log('[play] Fresh playback started')
      }
    } catch (error) {
      console.error('Failed to start playback:', error)
    }
  }

  const pause = () => {
    console.log('⏸️ Pausing playback...')
    if (transport) {
      // Stop and dispose all currently playing sample players
      console.log(`⏸️ Stopping and disposing ${samplePlayers.length} sample players...`)
      samplePlayers.forEach(player => {
        try {
          if (player.state === 'started') {
            player.stop()
          }
          player.dispose()
        } catch (e) {
          console.warn('Error stopping/disposing sample player during pause:', e)
        }
      })
      samplePlayers.length = 0 // Clear the array so new players can be created on resume
      
      // Clear scheduled events because we'll need to reschedule them on resume
      clearScheduledEvents()
      
      transport.pause()
      isPlaying.value = false
      isPaused.value = true // Track that we're in paused state
      console.log(`⏸️ Paused at position: ${transport.position} (${transport.seconds}s)`)
    }
  }

  const stop = () => {
    console.log('🛑 Stopping all audio playback...')
    
    if (transport) {
      transport.stop()
      transport.position = 0
      currentTime.value = 0
      isPlaying.value = false
      isPaused.value = false // Clear pause state on stop
      clearScheduledEvents()
      
      // Don't clear position tracking on normal stop - keep it for next play
      // Only clear it on full reset
    }
    
    // Stop and dispose all sample players
    console.log(`🎵 Stopping ${samplePlayers.length} sample players...`)
    samplePlayers.forEach(player => {
      try { 
        if (player.state === 'started') {
          player.stop()
        }
        player.dispose()
      } catch (e) { 
        console.warn('Error stopping sample player:', e)
      }
    })
    samplePlayers.length = 0
    
    // Stop all preview audio elements
    console.log(`🔊 Stopping ${previewAudioElements.value.size} preview audio elements...`)
    previewAudioElements.value.forEach(audio => {
      try {
        audio.pause()
        audio.currentTime = 0
      } catch (e) { 
        console.warn('Error stopping preview audio:', e)
      }
    })
    
    console.log('✅ All audio playback stopped')
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
    if (!track) return null

    // Use enhanced clip creation with JSON configuration support
    const newClip = createClipWithConfiguration(trackId, clip)
    
    track.clips.push(newClip)
    updateSongStructure()
    return newClip.id
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
    
    // Auto-calculate song duration based on content
    let maxEndTime = 8 // Minimum 8 seconds
    songStructure.value.tracks.forEach(track => {
      track.clips.forEach(clip => {
        const clipEndTime = clip.startTime + clip.duration
        maxEndTime = Math.max(maxEndTime, clipEndTime)
      })
    })
    
    // Add some padding and round up to nearest 4 seconds
    const newDuration = Math.ceil((maxEndTime + 2) / 4) * 4
    if (newDuration !== songStructure.value.duration) {
      console.log(`Updating song duration from ${songStructure.value.duration}s to ${newDuration}s`)
      songStructure.value.duration = newDuration
    }
  }

  const loadSongStructure = (structure: SongStructure) => {
    songStructure.value = structure
    
    // Initialize track configurations from the loaded data
    initializeTrackConfigurations()
    
    // Update transport settings
    if (transport) {
      transport.bpm.value = structure.tempo
    }
    
    console.log('Loaded song structure with JSON configurations:', {
      tracks: structure.tracks.length,
      configurations: trackConfigurations.value.size,
      tempo: structure.tempo,
      key: structure.key
    })
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
    // If playback is running, re-schedule song to add/remove metronome events
    if (isPlaying.value) {
      clearScheduledEvents()
      generateAndScheduleSong(transport.seconds)
    }
    // Play a test click when enabling metronome
    if (metronomeEnabled.value && metronome) {
      metronome.triggerAttackRelease('C6', '16n')
    }
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

  const setMetronomeBars = (bars: number) => {
    metronomeBars.value = bars
  }

  // Register a preview audio element to be stopped when stop() is called
  const registerPreviewAudio = (audio: HTMLAudioElement) => {
    previewAudioElements.value.add(audio)
  }

  // Unregister a preview audio element
  const unregisterPreviewAudio = (audio: HTMLAudioElement) => {
    previewAudioElements.value.delete(audio)
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
      
      // Clear position tracking on full reset
      if (positionTrackingEventId !== null) {
        transport.clear(positionTrackingEventId)
        positionTrackingEventId = null
      }
    }
    // Stop and dispose all sample players
    samplePlayers.forEach(player => {
      try { player.stop(); player.dispose(); } catch (e) { /* ignore */ }
    })
    samplePlayers.length = 0
    
    // Clear instruments
    instruments.value.clear()
    // Reset state
    isInitialized.value = false
    isInitializing.value = false
    initializationError.value = null
    isPlaying.value = false
    isPaused.value = false
    currentTime.value = 0
    console.log('Audio system reset complete')
  }

  // Chord generation functionality
  const generateChordProgression = async (
    trackId: string,
    progressionType: ChordProgressionType,
    startTime: number = 0,
    chordDuration: number = 2,
    numRepeats: number = 1
  ) => {
    const track = songStructure.value.tracks.find(t => t.id === trackId)
    if (!track) {
      console.warn('Track not found for chord generation')
      return
    }

    // Determine instrument type from track
    const sampleInstrument: SampleInstrument = 
      track.instrument === 'piano' || track.instrument === 'electric-piano' ? 'piano' : 'guitar'

    try {
      console.log(`Generating chord progression for ${track.name} (${sampleInstrument})`)
      
      // Generate chord progression
      const progression = ChordService.generateChordProgression(
        songStructure.value.key,
        progressionType,
        sampleInstrument,
        numRepeats,
        chordDuration
      )

      // Create clips from chord progression
      const chordClips = ChordService.generateChordClips(progression, startTime, chordDuration)
      
      console.log(`Generated ${chordClips.length} chord clips:`, chordClips.map(c => c.sampleUrl))
      
      // Pre-load all samples to avoid delays
      const loadPromises = chordClips.map(clipData => 
        new Promise<void>((resolve) => {
          const testPlayer = new Tone.Player({
            url: clipData.sampleUrl,
            onload: () => {
              testPlayer.dispose()
              resolve()
            },
            onerror: (error) => {
              console.warn(`Failed to pre-load sample: ${clipData.sampleUrl}`, error)
              testPlayer.dispose()
              resolve() // Don't reject, just warn
            }
          })
        })
      )
      
      // Wait for samples to load (with timeout)
      try {
        await Promise.race([
          Promise.all(loadPromises),
          new Promise((_, reject) => setTimeout(() => reject(new Error('Timeout')), 3000))
        ])
        console.log('All chord samples pre-loaded successfully')
      } catch (error) {
        console.warn('Some samples may not have loaded, continuing anyway:', error)
      }
      
      // Add clips to track
      chordClips.forEach(clipData => {
        const clip: Omit<AudioClip, 'id' | 'trackId'> = {
          startTime: clipData.startTime,
          duration: clipData.duration,
          type: 'sample',
          instrument: track.instrument,
          sampleUrl: clipData.sampleUrl,
          volume: 0.8,
          effects: {
            reverb: 0,
            delay: 0,
            distortion: 0
          }
        }
        addClip(trackId, clip)
      })

      console.log(`Generated chord progression for track ${track.name}:`, progression)
      
      // If playback is currently active, reschedule to include new clips
      if (isPlaying.value) {
        console.log('Rescheduling playback to include new chord clips')
        generateAndScheduleSong(transport.seconds)
      }
    } catch (error) {
      console.error('Failed to generate chord progression:', error)
    }
  }

  const generateRandomChordProgression = async (
    trackId: string,
    startTime: number = 0,
    chordDuration: number = 2,
    length: number = 4
  ) => {
    const track = songStructure.value.tracks.find(t => t.id === trackId)
    if (!track) {
      console.warn('Track not found for random chord generation')
      return
    }

    // Determine instrument type from track
    const sampleInstrument: SampleInstrument = 
      track.instrument === 'piano' || track.instrument === 'electric-piano' ? 'piano' : 'guitar'

    try {
      console.log(`Generating random chord progression for ${track.name} (${sampleInstrument})`)
      
      // Generate random chord progression
      const progression = ChordService.generateRandomProgression(
        songStructure.value.key,
        sampleInstrument,
        length,
        chordDuration
      )

      // Create clips from chord progression
      const chordClips = ChordService.generateChordClips(progression, startTime, chordDuration)
      
      console.log(`Generated ${chordClips.length} random chord clips:`, chordClips.map(c => c.sampleUrl))
      
      // Pre-load all samples to avoid delays
      const loadPromises = chordClips.map(clipData => 
        new Promise<void>((resolve) => {
          const testPlayer = new Tone.Player({
            url: clipData.sampleUrl,
            onload: () => {
              testPlayer.dispose()
              resolve()
            },
            onerror: (error) => {
              console.warn(`Failed to pre-load sample: ${clipData.sampleUrl}`, error)
              testPlayer.dispose()
              resolve() // Don't reject, just warn
            }
          })
        })
      )
      
      // Wait for samples to load (with timeout)
      try {
        await Promise.race([
          Promise.all(loadPromises),
          new Promise((_, reject) => setTimeout(() => reject(new Error('Timeout')), 3000))
        ])
        console.log('All random chord samples pre-loaded successfully')
      } catch (error) {
        console.warn('Some random chord samples may not have loaded, continuing anyway:', error)
      }
      
      // Add clips to track
      chordClips.forEach(clipData => {
        const clip: Omit<AudioClip, 'id' | 'trackId'> = {
          startTime: clipData.startTime,
          duration: clipData.duration,
          type: 'sample',
          instrument: track.instrument,
          sampleUrl: clipData.sampleUrl,
          volume: 0.8,
          effects: {
            reverb: 0,
            delay: 0,
            distortion: 0
          }
        }
        addClip(trackId, clip)
      })

      console.log(`Generated random chord progression for track ${track.name}:`, progression)
      
      // If playback is currently active, reschedule to include new clips
      if (isPlaying.value) {
        console.log('Rescheduling playback to include new random chord clips')
        generateAndScheduleSong(transport.seconds)
      }
    } catch (error) {
      console.error('Failed to generate random chord progression:', error)
    }
  }

  const getChordProgressionSuggestions = () => {
    return ChordService.getProgressionSuggestions()
  }

  const getAvailableKeys = () => {
    return ChordService.getAvailableKeys()
  }

  const getAvailableProgressionTypes = (): ChordProgressionType[] => {
    return ChordService.getAvailableProgressions()
  }

  // Clear all clips from a track
  const clearTrackClips = (trackId: string) => {
    const track = songStructure.value.tracks.find(t => t.id === trackId)
    if (track) {
      track.clips = []
      updateSongStructure()
      console.log(`Cleared all clips from track ${track.name}`)
    }
  }

  // Enhanced clip configuration system
  interface ClipConfiguration {
    instrument: string
    duration?: number
    notes?: string[]
    chordProgression?: string[]
    speed?: number // Notes per beat
    effects?: {
      reverb?: number
      delay?: number
      distortion?: number
    }
  }

  // Track configurations from JSON that should be used for new clips
  const trackConfigurations = ref<Map<string, ClipConfiguration>>(new Map())

  const initializeTrackConfigurations = () => {
    trackConfigurations.value.clear()
    
    // Extract configuration patterns from existing clips in the JSON
    songStructure.value.tracks.forEach(track => {
      if (track.clips.length > 0) {
        // Use the first clip as template for this track/instrument combination
        const templateClip = track.clips[0]
        const config: ClipConfiguration = {
          instrument: templateClip.instrument,
          duration: templateClip.duration,
          notes: templateClip.notes ? [...templateClip.notes] : undefined,
          effects: { ...templateClip.effects }
        }
        
        // If multiple clips exist, try to detect patterns
        if (track.clips.length > 1) {
          // Calculate average duration
          const avgDuration = track.clips.reduce((sum, clip) => sum + clip.duration, 0) / track.clips.length
          config.duration = avgDuration
          
          // Extract chord progression if available
          const chordProgression = track.clips
            .filter(clip => clip.notes && clip.notes.length > 0)
            .map(clip => clip.notes?.[0]) // Use first note as chord root
            .filter(note => note !== undefined) as string[]
          
          if (chordProgression.length > 0) {
            config.chordProgression = chordProgression
          }
        }
        
        trackConfigurations.value.set(track.id, config)
      }
    })
  }

  // Generate notes based on JSON configuration or fall back to generated ones
  const generateNotesFromConfiguration = (clip: AudioClip, trackId: string): string[] => {
    const config = trackConfigurations.value.get(trackId)
    
    // If we have a configuration with predefined notes, use them
    if (config && config.notes && config.notes.length > 0) {
      return [...config.notes]
    }
    
    // If we have a chord progression, use it
    if (config && config.chordProgression && config.chordProgression.length > 0) {
      const progressionIndex = Math.floor(clip.startTime / (config.duration || 4)) % config.chordProgression.length
      const rootNote = config.chordProgression[progressionIndex]
      // Extract note name from the full note (e.g., "C4" -> "C")
      const noteName = rootNote.replace(/\d+$/, '') as any
      // Generate chord notes using ChordService public method
      return ChordService.generateChordNotes(noteName, 'major')
    }
    
    // Fall back to the original generation logic
    return generateNotesForClip(clip, songStructure.value.key)
  }

  // Enhanced clip creation with JSON configuration support
  const createClipWithConfiguration = (trackId: string, clipData: Omit<AudioClip, 'id' | 'trackId' | 'notes'>): AudioClip => {
    const config = trackConfigurations.value.get(trackId)
    
    // Apply configuration overrides
    const enhancedClipData = {
      ...clipData,
      duration: config?.duration || clipData.duration,
      effects: {
        ...clipData.effects,
        ...config?.effects
      }
    }

    // Create the base clip
    const newClip: AudioClip = {
      ...enhancedClipData,
      id: `clip-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      trackId
    }

    // Generate notes based on configuration
    if (newClip.type === 'synth' || (newClip.type === 'sample' && !newClip.sampleUrl)) {
      newClip.notes = generateNotesFromConfiguration(newClip, trackId)
    }

    return newClip
  }



  return {
    // State
    isPlaying,
    isPaused,
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
    metronomeBars,
    
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
    selectTrack,
    setMetronomeBars,
    registerPreviewAudio,
    unregisterPreviewAudio,
    
    // Chord generation
    generateChordProgression,
    generateRandomChordProgression,
    getChordProgressionSuggestions,
    getAvailableKeys,
    getAvailableProgressionTypes,
    clearTrackClips,
    
    // JSON configuration support
    initializeTrackConfigurations,
    createClipWithConfiguration,
    generateNotesFromConfiguration,
    
    // Enhanced sample management
    preloadSamplesForInstrument,
    getSamplePlayer,
    scheduleClipWithSamples,
    scheduleClipWithSynth
  }
})
