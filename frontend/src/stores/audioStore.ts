import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as Tone from 'tone'
import { 
  ChordService, 
  type ChordProgressionType, 
  type SampleInstrument 
} from '../services/chordService'

export interface LyricFragment {
  text: string
  notes: string[]
  start: number
  duration?: number
  durations?: number[]
}

export interface Voice {
  voice_id: string
  lyrics: LyricFragment[]
}

export interface AudioClip {
  id: string
  trackId: string
  startTime: number
  duration: number
  type: 'synth' | 'sample' | 'lyrics'
  instrument: string
  notes?: string[]
  sampleUrl?: string
  sampleDuration?: number // Optional sample duration (e.g., 1s for 1s samples)
  volume: number
  effects: {
    reverb: number
    delay: number
    distortion: number
  }
  // Add waveform for sample clips
  waveform?: number[]
  // Lyrics-specific properties (for simple arrangements)
  text?: string // For lyrics clips
  chordName?: string // For lyrics clips
  voiceId?: string // For lyrics clips - which voice to use for singing
  // Advanced multi-voice structure (do not use simple fields when using this)
  voices?: Voice[]
}

export interface Track {
  id: string
  name: string
  instrument: string
  category?: string // Add category field for sample-based instruments
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
  const selectedClipId = ref<string | null>(null)
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
  const instruments = ref<Map<string, any>>(new Map())
  const scheduledEvents = ref<any[]>([]) // Can be timeout IDs or Transport event IDs
  let transport: typeof Tone.Transport
  let metronome: Tone.Synth | null = null

  // Track all active sample players
  const samplePlayers: Tone.Player[] = []
  
  // Track all HTML audio elements for previews
  const previewAudioElements = ref<Set<HTMLAudioElement>>(new Set())

  // Position tracking for simplified playback
  let playbackStartTime = 0
  let pausedPosition = 0 // Track where we paused
  let positionTrackingInterval: NodeJS.Timeout | null = null

  // Track the position tracking event ID separately
  let positionTrackingEventId: number | null = null

  // Computed
  const totalTracks = computed(() => songStructure.value.tracks.length)
  const selectedTrack = computed(() => 
    songStructure.value.tracks.find(track => track.id === selectedTrackId.value)
  )
  const getSelectedClip = computed(() => {
    if (!selectedClipId.value) return null
    
    // Find the clip across all tracks
    for (const track of songStructure.value.tracks) {
      const clip = track.clips.find(c => c.id === selectedClipId.value)
      if (clip) return clip
    }
    return null
  })

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

      // Start Tone.js context with longer timeout and better error handling
      console.log('Starting Tone.js context...')
      try {
        await Tone.start()
        console.log('✅ Tone.js context started successfully')
      } catch (startError) {
        console.error('Failed to start Tone.js context:', startError)
        throw new Error(`Failed to start audio context: ${startError instanceof Error ? startError.message : 'Unknown error'}`)
      }
      
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
          preloadSamplesForInstrument('strings', 'guitar', 1),
          preloadSamplesForInstrument('keys', 'piano', 1),
          preloadSamplesForInstrument('keys', 'piano', 2)
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
      //synth.triggerAttackRelease('C4', '8n')
      
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

  // Fallback sample finder - tries to find alternative samples if primary fails
  const findAlternativeSample = async (category: string, instrument: string, note: string): Promise<string | null> => {
    // List of alternative chord names to try
    const alternatives = [
      note, // Original
      note.replace('_minor', '_major'), // Try major if minor fails
      note.replace('_major', '_minor'), // Try minor if major fails
      'C_major', // Universal fallback
      'C_minor'  // Alternative universal fallback
    ]
    
    // File formats to try in order of preference
    const formats = [
      { ext: 'mp3', folder: 'mp3' },
      { ext: 'wav', folder: 'wav' }
    ]
    
    for (const altNote of alternatives) {
      if (altNote === note && altNote !== 'C_major' && altNote !== 'C_minor') continue // Skip original unless it's a fallback
      
      // Try both MP3 and WAV formats
      for (const format of formats) {
        const altSamplePath = `instruments/${category}/${instrument}/${format.folder}/${altNote}.${format.ext}`
        const altUrlSafePath = altSamplePath.split('/').map(part => encodeURIComponent(part)).join('/')
        
        try {
          const validation = await validateAudioFile(altUrlSafePath, altSamplePath)
          if (validation.valid) {
            console.log(`🔄 Found alternative sample: ${altSamplePath}`)
            return altUrlSafePath
          }
        } catch (error) {
          // Continue to next format/alternative
          continue
        }
      }
    }
    
    return null // No alternatives found
  }

  // Utility function to validate audio file before loading with Tone.js
  const validateAudioFile = async (urlSafePath: string, samplePath: string): Promise<{ valid: boolean, error?: string, info?: any }> => {
    try {
      // First, check if file exists with a HEAD request
      const headResponse = await fetch(urlSafePath, { method: 'HEAD' })
      if (!headResponse.ok) {
        return { valid: false, error: `File not found (${headResponse.status})` }
      }
      
      const contentType = headResponse.headers.get('content-type')
      const contentLength = headResponse.headers.get('content-length')
      
      console.log(`🔍 Validating audio file: ${samplePath}`)
      console.log(`   Content-Type: ${contentType}`)
      console.log(`   Content-Length: ${contentLength} bytes`)
      
      // Check for common server misconfigurations
      if (contentType === 'text/html') {
        return { 
          valid: false, 
          error: `🚨 SERVER CONFIGURATION ISSUE: The web server is returning HTML instead of audio file. This usually means:
1. The file path is incorrect, OR
2. The web server is not configured to serve MP3/WAV files from the samples directory, OR  
3. The server is returning a 404/error page in HTML format.
Check your web server configuration to ensure it can serve audio files from: ${samplePath}`,
          info: { contentType, contentLength, serverIssue: true }
        }
      }
      
      // Check content type
      if (contentType && !contentType.startsWith('audio/')) {
        return { 
          valid: false, 
          error: `Invalid content type: ${contentType}. Expected audio/*`,
          info: { contentType, contentLength }
        }
      }
      
      // Check file size (very small files are likely corrupted)
      const fileSize = contentLength ? parseInt(contentLength) : 0
      if (fileSize > 0 && fileSize < 1000) { // Less than 1KB is suspicious for audio
        return { 
          valid: false, 
          error: `File too small: ${fileSize} bytes. Likely corrupted.`,
          info: { contentType, contentLength: fileSize }
        }
      }
      
      // Try to load the file with the Web Audio API to check if it's decodable
      try {
        const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)()
        const response = await fetch(urlSafePath)
        const arrayBuffer = await response.arrayBuffer()
        
        // Try to decode the audio data
        await audioContext.decodeAudioData(arrayBuffer.slice(0)) // slice to avoid transferring the buffer
        
        return { 
          valid: true,
          info: { contentType, contentLength: fileSize, decodable: true }
        }
        
      } catch (decodeError) {
        return { 
          valid: false, 
          error: `Audio decode failed: ${decodeError instanceof Error ? decodeError.message : 'Unknown decode error'}`,
          info: { contentType, contentLength: fileSize, decodeError: decodeError instanceof Error ? decodeError.message : 'Unknown' }
        }
      }
      
    } catch (error) {
      return { 
        valid: false, 
        error: `Validation failed: ${error instanceof Error ? error.message : 'Unknown error'}` 
      }
    }
  }

  // Enhanced sample loading and management
  const preloadedSamples = ref<Map<string, Map<string, Tone.Player>>>(new Map()) // instrument -> note -> player

  // Preload samples for an instrument - supports both simplified and duration-based structures
  const preloadSamplesForInstrument = async (category: string, instrument: string, sampleDuration: number = 1, useSimplifiedStructure: boolean = true) => {
    const structureType = useSimplifiedStructure ? 'simplified' : 'duration-based'
    const instrumentKey = useSimplifiedStructure ? 
      `${category}_${instrument}_simplified` : 
      `${category}_${instrument}_${sampleDuration}s`
      
    if (preloadedSamples.value.has(instrumentKey)) {
      return preloadedSamples.value.get(instrumentKey)!
    }

    const sampleMap = new Map<string, Tone.Player>()
    
    // Common chord types to preload
    const chordsToPreload = [
      'C_major', 'D_major', 'E_major', 'F_major', 'G_major', 'A_major', 'B_major',
      'C_minor', 'D_minor', 'E_minor', 'F_minor', 'G_minor', 'A_minor', 'B_minor',
      'As_major', 'Cs_major', 'Ds_major', 'Fs_major', 'Gs_major',
      'As_minor', 'Cs_minor', 'Ds_minor', 'Fs_minor', 'Gs_minor'
    ]

    console.log(`Preloading chord samples for ${category}/${instrument} (${structureType} structure)...`)
    
    // Format duration properly for duration-based structure
    const durationStr = sampleDuration === Math.floor(sampleDuration) ? 
      `${sampleDuration}.0s` : `${sampleDuration}s`
    
    const loadPromises = chordsToPreload.map(async (chord) => {
      try {
        const formats = [
          { ext: 'mp3', folder: 'mp3' },
          { ext: 'wav', folder: 'wav' }
        ]
        
        // Try to load the chord sample in order of preference (MP3 first, then WAV)
        for (const format of formats) {
          // Choose path structure based on simplified vs duration-based
          const samplePath = useSimplifiedStructure ?
            `instruments/${category}/${instrument}/${format.folder}/${chord}.${format.ext}` :
            `instruments/${category}/${instrument}/${durationStr}/${format.folder}/${chord}.${format.ext}`
          const urlSafePath = samplePath.split('/').map(part => encodeURIComponent(part)).join('/')
          
          try {
            // Validate audio file before loading
            const validation = await validateAudioFile(urlSafePath, samplePath)
            if (!validation.valid) {
              continue // Try next format
            }
            
            const player = new Tone.Player({
              url: urlSafePath,
              autostart: false,
              volume: 0, // Will be set per use
              fadeIn: 0.01,
              fadeOut: 0.01
            })

            // Use the player's load method to ensure it's properly loaded
            await player.load(urlSafePath)
            if (player.loaded) {
              sampleMap.set(chord, player)
              console.log(`✅ Loaded chord sample (${structureType}): ${samplePath}`)
              break // Successfully loaded, don't try other formats
            }
          } catch (error) {
            console.warn(`Failed to load chord sample: ${samplePath}`, error)
            // Continue to next format
          }
        }
      } catch (error) {
        console.warn(`Error loading chord sample for ${chord}:`, error)
      }
    })

    await Promise.all(loadPromises)
    preloadedSamples.value.set(instrumentKey, sampleMap)
    console.log(`🎵 Preloaded ${sampleMap.size} chord samples for ${category}/${instrument} (${structureType})`)
    
    return sampleMap
  }

  // Get or create a sample player with flexible structure support
  const getSamplePlayer = async (category: string, instrument: string, note: string, _sampleDuration: number = 1): Promise<Tone.Player | null> => {
    // Try simplified structure first (no duration folders), then fall back to duration-based structure
    const defaultDuration = 1.0
    
    const instrumentKey = `${category}_${instrument}_simplified`
    let instrumentSamples = preloadedSamples.value.get(instrumentKey)
    
    if (!instrumentSamples) {
      // Try to preload from simplified structure first
      instrumentSamples = await preloadSamplesForInstrument(category, instrument, defaultDuration, true)
      if (!instrumentSamples || instrumentSamples.size === 0) {
        // Fall back to duration-based structure
        instrumentSamples = await preloadSamplesForInstrument(category, instrument, defaultDuration, false)
      }
    }
    
    const player = instrumentSamples.get(note)
    if (player && player.loaded) {
      // Try to create a new player instance for parallel playback using the default duration
      const formats = [
        { ext: 'mp3', folder: 'mp3' },
        { ext: 'wav', folder: 'wav' }
      ]
      
      for (const format of formats) {
        const samplePath = `instruments/${category}/${instrument}/${format.folder}/${note}.${format.ext}`
        const urlSafePath = samplePath.split('/').map(part => encodeURIComponent(part)).join('/')
        
        try {
          const validation = await validateAudioFile(urlSafePath, samplePath)
          if (validation.valid) {
            const newPlayer = new Tone.Player({
              url: urlSafePath,
              autostart: false,
              volume: 0,
              fadeIn: 0.01,
              fadeOut: 0.01
            }).toDestination()
            
            // Wait for the new player to load
            await Tone.loaded()
            return newPlayer.loaded ? newPlayer : null
          }
        } catch (error) {
          continue // Try next format
        }
      }
    }
    
    // Fallback: create individual player using flexible structure
    const pathVariants = [
      `instruments/${category}/${instrument}/mp3/${note}.mp3`, // Simplified MP3
      `instruments/${category}/${instrument}/wav/${note}.wav`, // Simplified WAV
    ]
    
    // Try path variants (simplified first, then duration-based)
    for (const samplePath of pathVariants) {
      const urlSafePath = samplePath.split('/').map((part: string) => encodeURIComponent(part)).join('/')
      const format = samplePath.includes('.mp3') ? { ext: 'mp3', folder: 'mp3' } : { ext: 'wav', folder: 'wav' }
      
      try {
        // First validate the audio file
        console.log(`🔍 Validating audio file before creating fallback player...`)
        let validation = await validateAudioFile(urlSafePath, samplePath)
        let finalUrlSafePath = urlSafePath
        let finalSamplePath = samplePath
        
        if (!validation.valid) {
          console.warn(`⚠️ Sample validation failed for ${format.ext.toUpperCase()}: ${validation.error}`)
          
          // Special handling for server configuration issues
          if (validation.info?.serverIssue) {
            console.error(`🚨 SERVER CONFIGURATION PROBLEM DETECTED:`)
            console.error(`   File path: ${samplePath}`)
            console.error(`   URL: ${urlSafePath}`)
            console.error(`   The web server is not properly configured to serve audio files.`)
            console.error(`   Please check your development server configuration.`)
          }
          
          continue // Try next format
        }
        
        console.log(`✅ Primary sample validation passed for ${format.ext.toUpperCase()}`, validation.info)
        
        const fallbackPlayer = new Tone.Player({
          url: finalUrlSafePath,
          autostart: false,
          volume: 0,
          fadeIn: 0.01,
          fadeOut: 0.01
        }).toDestination()
        
        // Wait for the player to load completely with better error handling
        return new Promise((resolve) => {
          // Set up a timeout to avoid hanging
          const loadTimeout = setTimeout(() => {
            console.error(`⏱️ Timeout loading sample: ${finalSamplePath}`)
            resolve(null)
          }, 5000) // 5 second timeout
          
          fallbackPlayer.load(finalUrlSafePath).then(() => {
            clearTimeout(loadTimeout)
            console.log(`✅ Loaded fallback sample: ${finalSamplePath}`)
            resolve(fallbackPlayer)
          }).catch((error) => {
            clearTimeout(loadTimeout)
            console.error(`❌ Failed to load fallback sample: ${finalSamplePath}`, error)
            
            // Enhanced error analysis for MP3 decoding issues
            if (error.name === 'EncodingError' || error.message.includes('Unable to decode audio data') || 
                error.message.includes('decoding') || error.message.includes('decode')) {
              console.error(`🎵 AUDIO DECODING ERROR: MP3 file cannot be decoded by Tone.js/Web Audio API`)
              console.error(`   File: ${finalSamplePath}`)
              console.error(`   Validation passed: File exists and has correct content-type`)
              console.error(`   Issue: The MP3 encoding is not compatible with the Web Audio API`)
              console.error(`   Solutions:`)
              console.error(`   1. Re-encode the MP3 with different settings (try lower bitrate or different encoder)`)
              console.error(`   2. Convert to WAV format for guaranteed compatibility`)
              console.error(`   3. Use FFmpeg to re-encode: ffmpeg -i input.mp3 -codec:a libmp3lame -b:a 192k output.mp3`)
              console.error(`   4. Or run the conversion script: convert-samples.bat`)
            } else {
              console.error(`   Error type: ${error.name}`)
              console.error(`   Error message: ${error.message}`)
              console.error(`   File validation was successful, but Tone.js failed to load`)
              console.error(`   This could indicate:`)
              console.error(`   1. MP3 encoding is not fully compatible with Tone.js`)
              console.error(`   2. File corruption during conversion`)
              console.error(`   3. Tone.js version compatibility issue`)
              console.error(`   4. Audio context state issues`)
            }
            
            // Try to provide more context about the audio context state
            console.error(`   Audio context state: ${Tone.context.state}`)
            console.error(`   Audio context sample rate: ${Tone.context.sampleRate}`)
            
            resolve(null)
          })
        })
        
      } catch (error) {
        console.error(`Failed to create fallback player for ${samplePath}:`, error)
        continue // Try next format
      }
    }
    
    // If no format worked, try to find an alternative sample using default duration
    console.log(`🔄 No direct samples found, searching for alternatives...`)
    const alternativeUrl = await findAlternativeSample(category, instrument, note)
    
    if (alternativeUrl) {
      // Validate the alternative
      const altPath = alternativeUrl.split('/').map(decodeURIComponent).join('/')
      const validation = await validateAudioFile(alternativeUrl, altPath)
      
      if (validation.valid) {
        console.log(`✅ Using alternative sample: ${altPath}`)
        
        const alternativePlayer = new Tone.Player({
          url: alternativeUrl,
          autostart: false,
          volume: 0,
          fadeIn: 0.01,
          fadeOut: 0.01
        }).toDestination()
        
        return new Promise((resolve) => {
          alternativePlayer.load(alternativeUrl).then(() => {
            console.log(`✅ Loaded alternative sample: ${altPath}`)
            resolve(alternativePlayer)
          }).catch((error) => {
            console.error(`❌ Failed to load alternative sample: ${altPath}`, error)
            resolve(null)
          })
        })
      } else {
        console.error(`❌ Alternative sample also failed validation: ${validation.error}`)
      }
    } else {
      console.error(`❌ No alternative samples found for ${category}/${instrument}/${note}`)
    }
    
    return null
  }

  // Check if samples are available for an instrument
  const hasSamplesForInstrument = async (category: string, instrument: string): Promise<boolean> => {
    try {
      // Check both MP3 and WAV formats
      const formats = [
        { ext: 'mp3', folder: 'mp3' },
        { ext: 'wav', folder: 'wav' }
      ]
      
      for (const format of formats) {
        const samplePath = `instruments/${category}/${instrument}/${format.folder}/C_major.${format.ext}`
        const urlSafePath = samplePath.split('/').map(part => encodeURIComponent(part)).join('/')
        
        try {
          const response = await fetch(urlSafePath, { method: 'HEAD' })
          if (response.ok) {
            console.log(`✅ Found ${format.ext.toUpperCase()} samples for ${category}/${instrument}`)
            return true
          }
        } catch (error) {
          continue // Try next format
        }
      }
      
      return false
    } catch (error) {
      return false
    }
  }

  // Enhanced clip scheduling with automatic sample detection
  const scheduleClip = async (clip: AudioClip, track: Track, fromPosition: number = 0) => {
    if (track.muted) return

    const startTime = clip.startTime
    const duration = clip.duration
    const clipEndTime = startTime + duration
    
    // Skip clips that have completely finished before the current position
    if (clipEndTime <= fromPosition && fromPosition > 0) {
      console.log(`[scheduleClip] Skipping clip that ended before position ${fromPosition}:`, clip)
      return
    }

    // Automatically determine if we should use samples or synth
    const category = getTrackCategory(track)
    const shouldUseSamples = clip.type === 'sample' || await hasSamplesForInstrument(category, track.instrument)
    
    if (shouldUseSamples && (clip.notes && clip.notes.length > 0 || !clip.notes)) {
      console.log(`[scheduleClip] Using samples for ${track.instrument}`)
      
      // For samples, ensure we have chord names, not individual notes
      let sampleNotes = clip.notes
      if (!sampleNotes || sampleNotes.length === 0 || !sampleNotes[0].includes('_')) {
        // Generate appropriate chord names for samples
        sampleNotes = generateChordNamesForClip(clip, songStructure.value.key)
        console.log(`[scheduleClip] Generated chord names for samples:`, sampleNotes)
      }
      
      // Create a modified clip with chord names
      const sampleClip = { ...clip, notes: sampleNotes }
      scheduleClipWithSamples(sampleClip, track, fromPosition)
    } else {
      console.log(`[scheduleClip] Using synth for ${track.instrument}`)
      scheduleClipWithSynth(clip, track, fromPosition)
    }
  }

  // Schedule clip using samples with precise timing and looping
  const scheduleClipWithSamples = async (clip: AudioClip, track: Track, fromPosition: number = 0) => {
    const notes = clip.notes || []
    if (notes.length === 0) {
      console.warn('No notes provided for sample clip:', clip)
      return
    }

    const sampleDuration = clip.sampleDuration || 1 // Default to 1 second samples
    const volume = (clip.volume ?? 1) * (track.volume ?? 1) * (masterVolume.value ?? 1)
    
    // Calculate how many chords/notes fit in the clip duration with no gaps
    const totalChords = Math.floor(clip.duration / sampleDuration)
    
    console.log(`[scheduleClipWithSamples] Scheduling clip with ${notes.length} notes, ${totalChords} positions, ${sampleDuration}s per chord`)

    // Schedule each chord/note position within the clip
    for (let chordIndex = 0; chordIndex < totalChords; chordIndex++) {
      const chordStartTime = clip.startTime + (chordIndex * sampleDuration)
      
      // Skip chords that are before the current position
      if (chordStartTime + sampleDuration <= fromPosition) continue
      
      // Get the note for this position (cycle through the chord progression)
      const noteIndex = chordIndex % notes.length
      const currentNote = notes[noteIndex]
      
      // Schedule this chord/note using setTimeout instead of Transport
      const timeoutId = setTimeout(async () => {
        try {
          // For chord samples (like piano chords), use the chord name directly
          if (currentNote.includes('_')) {
            // This is a chord name like "C_major"
            const category = getTrackCategory(track)
            const player = await getSamplePlayer(category, track.instrument, currentNote, sampleDuration)
            if (player && player.loaded) {
              player.volume.value = Tone.gainToDb(Math.max(0.01, volume))
              player.start(0, 0, sampleDuration)
              console.log(`🎹 Playing chord ${currentNote} (position ${chordIndex + 1}/${totalChords})`)
            } else {
              console.warn(`Failed to get chord player for ${track.instrument} ${currentNote} or player not loaded`)
            }
          } else {
            // This is a single note like "C4"
            const category = getTrackCategory(track)
            const player = await getSamplePlayer(category, track.instrument, currentNote, sampleDuration)
            if (player && player.loaded) {
              player.volume.value = Tone.gainToDb(Math.max(0.01, volume))
              player.start(0, 0, sampleDuration)
              console.log(`🎵 Playing note ${currentNote} (position ${chordIndex + 1}/${totalChords})`)
            } else {
              console.warn(`Failed to get note player for ${track.instrument} ${currentNote} or player not loaded`)
            }
          }
        } catch (error) {
          console.error(`Error playing sample:`, error)
        }
      }, Math.max(0, (chordStartTime - fromPosition) * 1000)) // Adjust delay based on current position
      
      scheduledEvents.value.push(timeoutId as any)
    }
  }

  // Schedule clip using synthesizer - SIMPLIFIED VERSION
  const scheduleClipWithSynth = (clip: AudioClip, track: Track, fromPosition: number = 0) => {
    console.log(`[scheduleClipWithSynth] SIMPLIFIED: Getting instrument for ${track.instrument}`)
    
    // Try to get existing instrument first
    let instrument = instruments.value.get(track.instrument)
    
    // If instrument doesn't exist or might be corrupted, create a fresh one
    if (!instrument) {
      console.log(`[scheduleClipWithSynth] Creating fresh instrument for ${track.instrument}`)
      try {
        // Create a fresh synth instrument
        instrument = new Tone.PolySynth(Tone.Synth, {
          oscillator: { type: "sine" },
          envelope: { attack: 0.8, decay: 0.5, sustain: 0.8, release: 2 }
        }).toDestination()
        
        // Store it for future use
        instruments.value.set(track.instrument, instrument)
        console.log(`✅ Created fresh ${track.instrument} instrument`)
      } catch (createError) {
        console.error(`❌ Failed to create fresh instrument:`, createError)
        return
      }
    }

    const notes = clip.notes || generateNotesForClip(clip, songStructure.value.key)
    if (!notes.length) {
      console.log(`[scheduleClipWithSynth] No notes for clip`, clip)
      return
    }

    const sampleDuration = clip.sampleDuration || 1
    const clipVolume = clip.volume * track.volume * masterVolume.value
    
    if ('volume' in instrument) {
      instrument.volume.value = Tone.gainToDb(Math.max(0.01, clipVolume))
    }

    // Calculate how many chords/notes fit in the clip duration with no gaps
    const totalPositions = Math.floor(clip.duration / sampleDuration)
    
    console.log(`[scheduleClipWithSynth] SIMPLIFIED: Scheduling synth clip with ${notes.length} notes, ${totalPositions} positions, ${sampleDuration}s per position`)

    // Use Tone.js Draw.schedule instead of Transport.schedule to avoid Transport issues
    for (let positionIndex = 0; positionIndex < totalPositions; positionIndex++) {
      const positionStartTime = clip.startTime + (positionIndex * sampleDuration)
      
      // Skip positions that are before the current position
      if (positionStartTime + sampleDuration <= fromPosition) continue
      
      // Get the note for this position
      const noteIndex = positionIndex % notes.length
      const currentNote = notes[noteIndex]
      
      // Schedule using setTimeout instead of Transport for simplicity
      const timeoutId = setTimeout(async () => {
        try {
          // Ensure audio context is still running
          if (Tone.context.state !== 'running') {
            console.warn('Audio context not running, attempting to resume...')
            await Tone.context.resume()
          }
          
          // Create a completely fresh instrument for each note to avoid state issues
          const freshInstrument = new Tone.PolySynth(Tone.Synth, {
            oscillator: { type: "sine" },
            envelope: { attack: 0.1, decay: 0.3, sustain: 0.6, release: 1 }
          }).toDestination()
          
          const noteDuration = sampleDuration * 0.9
          const noteToPlay = Array.isArray(currentNote) ? currentNote[0] : currentNote
          
          console.log(`🎵 SIMPLIFIED: About to play note ${noteToPlay} with FRESH instrument (position ${positionIndex + 1}/${totalPositions})`)
          
          freshInstrument.triggerAttackRelease(noteToPlay, noteDuration)
          console.log(`✅ SIMPLIFIED: Successfully played note ${noteToPlay} with fresh instrument`)
          
          // Dispose the fresh instrument after a delay to prevent memory leaks
          setTimeout(() => {
            freshInstrument.dispose()
          }, (noteDuration * 1000) + 1000)
          
        } catch (error) {
          console.error('Error playing note with fresh instrument:', error)
          console.error('Error details:', {
            message: error instanceof Error ? error.message : 'Unknown error',
            name: error instanceof Error ? error.name : 'Unknown',
            contextState: Tone.context.state
          })
        }
      }, Math.max(0, (positionStartTime - fromPosition) * 1000)) // Adjust delay based on current position
      
      // Store timeout ID so we can clear it later
      scheduledEvents.value.push(timeoutId as any)
    }
  }

  // Helper function to convert chord names to note arrays
  // Currently unused but kept for future use
  /*
  const convertChordToNotes = (chordName: string): string[] => {
    // Basic chord conversion - this could be expanded
    const chordMap: Record<string, string[]> = {
      'C_major': ['C4', 'E4', 'G4'],
      'D_major': ['D4', 'F#4', 'A4'],
      'E_major': ['E4', 'G#4', 'B4'],
      'F_major': ['F4', 'A4', 'C5'],
      'G_major': ['G4', 'B4', 'D5'],
      'A_major': ['A4', 'C#5', 'E5'],
      'B_major': ['B4', 'D#5', 'F#5'],
      'C_minor': ['C4', 'Eb4', 'G4'],
      'D_minor': ['D4', 'F4', 'A4'],
      'E_minor': ['E4', 'G4', 'B4'],
      'F_minor': ['F4', 'Ab4', 'C5'],
      'G_minor': ['G4', 'Bb4', 'D5'],
      'A_minor': ['A4', 'C5', 'E5'],
      'B_minor': ['B4', 'D5', 'F#5'],
      'C_dom7': ['C4', 'E4', 'G4', 'Bb4'],
      'D_dom7': ['D4', 'F#4', 'A4', 'C5'],
      'E_dom7': ['E4', 'G#4', 'B4', 'D5'],
      'F_dom7': ['F4', 'A4', 'C5', 'Eb5'],
      'G_dom7': ['G4', 'B4', 'D5', 'F5'],
      'A_dom7': ['A4', 'C#5', 'E5', 'G5'],
      'B_dom7': ['B4', 'D#5', 'F#5', 'A5'],
      'C_maj7': ['C4', 'E4', 'G4', 'B4'],
      'D_maj7': ['D4', 'F#4', 'A4', 'C#5'],
      'E_maj7': ['E4', 'G#4', 'B4', 'D#5'],
      'F_maj7': ['F4', 'A4', 'C5', 'E5'],
      'G_maj7': ['G4', 'B4', 'D5', 'F#5'],
      'A_maj7': ['A4', 'C#5', 'E5', 'G#5'],
      'B_maj7': ['B4', 'D#5', 'F#5', 'A#5'],
      'C_min7': ['C4', 'Eb4', 'G4', 'Bb4'],
      'D_min7': ['D4', 'F4', 'A4', 'C5'],
      'E_min7': ['E4', 'G4', 'B4', 'D5'],
      'F_min7': ['F4', 'Ab4', 'C5', 'Eb5'],
      'G_min7': ['G4', 'Bb4', 'D5', 'F5'],
      'A_min7': ['A4', 'C5', 'E5', 'G5'],
      'B_min7': ['B4', 'D5', 'F#5', 'A5']
    }
    
    return chordMap[chordName] || [chordName.split('_')[0] + '4'] // Fallback to root note
  }
  */

  const scheduleMetronome = (fromPosition: number = 0) => {
    if (!metronomeEnabled.value || !metronome) {
      console.log('[scheduleMetronome] Skipped - metronome disabled or not initialized')
      return
    }

    const tempo = songStructure.value.tempo
    const timeSignature = songStructure.value.timeSignature[0] // beats per bar
    const beatInterval = 60 / tempo // seconds per beat
    
    console.log(`[scheduleMetronome] Starting continuous metronome at ${tempo} BPM (${beatInterval.toFixed(3)}s per beat)`)
    
    // Schedule metronome to run for a long time (10 minutes) or until stopped
    const maxDuration = 600 // 10 minutes in seconds
    const totalBeats = Math.ceil(maxDuration / beatInterval)
    
    let scheduledBeats = 0
    
    // Calculate which beat we should start from based on current position
    const startBeat = Math.floor(fromPosition / beatInterval)
    
    // Schedule each beat using setTimeout (consistent with simplified playback)
    for (let beat = startBeat; beat < startBeat + totalBeats; beat++) {
      const beatTime = beat * beatInterval
      
      // Skip beats that are too far in the past
      if (beatTime < fromPosition - beatInterval) continue
      
      const isDownbeat = beat % timeSignature === 0
      const delay = Math.max(10, (beatTime - fromPosition) * 1000) // Convert to milliseconds, minimum 10ms
      
      const timeoutId = setTimeout(() => {
        if (metronome && metronomeEnabled.value && isPlaying.value) {
          try {
            // Use different pitches for downbeat vs regular beats
            const pitch = isDownbeat ? "C5" : "C4"
            const velocity = isDownbeat ? 0.8 : 0.5
            
            metronome.volume.value = Tone.gainToDb(velocity * masterVolume.value)
            metronome.triggerAttackRelease(pitch, "32n", "+0.01")
            
            console.log(`🎵 Metronome: Beat ${beat + 1} (${isDownbeat ? 'DOWNBEAT' : 'beat'}) at ${beatTime.toFixed(2)}s (delay: ${delay}ms)`)
          } catch (error) {
            console.error('Error playing metronome beat:', error)
          }
        }
      }, delay)
      
      scheduledEvents.value.push(timeoutId)
      scheduledBeats++
      
      // Don't schedule too many beats at once to avoid performance issues
      if (scheduledBeats > 1000) break
    }
    
    console.log(`[scheduleMetronome] Scheduled ${scheduledBeats} metronome beats starting from beat ${startBeat + 1}`)
  }

  // Simple position tracking without Transport
  const startPositionTracking = () => {
    if (positionTrackingInterval) {
      clearInterval(positionTrackingInterval)
    }
    
    positionTrackingInterval = setInterval(() => {
      if (isPlaying.value) {
        const elapsed = (Date.now() - playbackStartTime) / 1000
        // currentTime represents the position within the song timeline
        currentTime.value = elapsed
        
        // Check if we've reached the end of the song and should loop or stop
        const maxSongDuration = Math.max(songStructure.value.duration, getActualSongDuration())
        if (currentTime.value >= maxSongDuration) {
          if (isLooping.value) {
            // Restart playback for looping
            playbackStartTime = Date.now()
            currentTime.value = 0
            console.log('🔄 Looping playback restarted')
          } else {
            // Stop at the end
            stop()
            console.log('⏹️ Playback completed')
          }
        }
      }
    }, 50) // Update every 50ms for smooth playhead movement
  }
  
  // Get the actual duration of the song based on clips
  const getActualSongDuration = (): number => {
    let maxEndTime = 0
    songStructure.value.tracks.forEach(track => {
      track.clips.forEach(clip => {
        const clipEndTime = clip.startTime + clip.duration
        maxEndTime = Math.max(maxEndTime, clipEndTime)
      })
    })
    return Math.max(maxEndTime, 4) // Minimum 4 seconds
  }
  
  const stopPositionTracking = () => {
    if (positionTrackingInterval) {
      clearInterval(positionTrackingInterval)
      positionTrackingInterval = null
    }
  }

  const clearScheduledEvents = () => {
    // Clear music events but preserve position tracking
    scheduledEvents.value.forEach(eventId => {
      if (typeof eventId === 'number') {
        // This is a setTimeout ID
        clearTimeout(eventId)
      } else {
        // This is a Transport event ID
        transport.clear(eventId)
      }
    })
    scheduledEvents.value = []
    
    // Stop and clear all sample players
    samplePlayers.forEach(player => {
      try {
        if (player.state === 'started') {
          player.stop()
        }
        player.dispose()
      } catch (error) {
        console.warn('Error disposing sample player:', error)
      }
    })
    samplePlayers.length = 0
    
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
  // Currently unused due to simplified approach that always starts fresh
  /*
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
  */
  
  // Also unused due to simplified approach
  /*  // Immediate clip scheduling for clips that should be playing right now
  const scheduleClipImmediate = (clip: AudioClip, track: Track, fromPosition: number) => {
    if (track.muted) return
    
    const startTime = clip.startTime
    const duration = clip.duration
    const clipEndTime = startTime + duration
    
    // Only handle clips that should be playing right now
    if (fromPosition < startTime || fromPosition >= clipEndTime) return
    
    const volume = (clip.volume ?? 1) * (track.volume ?? 1) * (masterVolume.value ?? 1)
    const sampleDuration = clip.sampleDuration || 1
    
    // Handle sample clips with chord/note progression
    if (clip.type === 'sample' && clip.notes && clip.notes.length > 0) {
      // Use timing utilities for precise playback calculation
      const currentPosition = getCurrentPlayingPosition(fromPosition, clip.startTime, sampleDuration)
      const currentNote = clip.notes[currentPosition.positionIndex % clip.notes.length]
      
      console.log(`[scheduleClipImmediate] Starting chord ${currentNote} immediately with ${currentPosition.remainingTime.toFixed(2)}s remaining`)
      
      // Start the current chord/note immediately
      getSamplePlayer(track.instrument, currentNote, sampleDuration).then(player => {
        if (player) {
          player.volume.value = Tone.gainToDb(Math.max(0.01, volume))
          samplePlayers.push(player)
          // Start with offset to sync with current position
          player.start("+0.01", currentPosition.timeIntoPosition, currentPosition.remainingTime)
        }
      }).catch(error => {
        console.error(`Error starting immediate sample playback:`, error)
      })
      
      return
    }
    
    // Handle sample clips with sampleUrl (legacy support)
    if (clip.type === 'sample' && clip.sampleUrl) {
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
      return
    }
    
    // Handle synth clips
    const instrument = instruments.value.get(track.instrument)
    if (!instrument || clip.type === 'sample') {
      return
    }

    const notes = clip.notes || generateNotesForClip(clip, songStructure.value.key)
    if (!notes.length) return

    const clipVolume = clip.volume * track.volume * masterVolume.value
    if ('volume' in instrument) {
      instrument.volume.value = Tone.gainToDb(Math.max(0.01, clipVolume))
    }

    // Calculate which chord/note should be playing now
    const timeIntoClip = fromPosition - startTime
    const currentPositionIndex = Math.floor(timeIntoClip / sampleDuration)
    
    // For chord instruments, trigger the current chord
    if (['piano', 'electric-piano', 'synth-pad'].includes(clip.instrument)) {
      const noteIndex = currentPositionIndex % notes.length
      const currentItem = notes[noteIndex]
      
      let chordNotes: string[] = []
      
      if (typeof currentItem === 'string' && currentItem.includes('_')) {
        // This is a chord name like "C_major" - convert to notes
        chordNotes = convertChordToNotes(currentItem)
      } else if (Array.isArray(currentItem)) {
        // This is already an array of notes
        chordNotes = currentItem
      } else {
        // This is a single note
        chordNotes = [currentItem]
      }
      
      if (chordNotes.length > 0 && 'triggerAttackRelease' in instrument) {
        const timeIntoCurrent = timeIntoClip % sampleDuration
        const remainingChordTime = sampleDuration - timeIntoCurrent
        const playDuration = Math.min(remainingChordTime * 0.9, 2)
        
        instrument.triggerAttackRelease(chordNotes, playDuration, "+0.01")
        console.log(`[scheduleClipImmediate] Triggering chord [${chordNotes.join(', ')}] immediately`)
      }
    } else {
      // For lead instruments, trigger the current note
      const noteIndex = currentPositionIndex % notes.length
      const currentNote = Array.isArray(notes[noteIndex]) ? notes[noteIndex][0] : notes[noteIndex]
      
      if ('triggerAttackRelease' in instrument) {
        const timeIntoCurrent = timeIntoClip % sampleDuration
        const remainingNoteTime = sampleDuration - timeIntoCurrent
        const playDuration = Math.min(remainingNoteTime * 0.8, 2)
        
        instrument.triggerAttackRelease(currentNote, playDuration, "+0.01")
        console.log(`[scheduleClipImmediate] Triggering note ${currentNote} immediately`)
      }
    }
  }
  */

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

      console.log('[play] SIMPLIFIED: Starting playback without Transport...')
      
      // Stop any current playback
      clearScheduledEvents()
      
      // Handle resume from pause vs fresh start
      if (isPaused.value) {
        // Resume from where we paused
        console.log(`[play] Resuming from position ${pausedPosition}s`)
        playbackStartTime = Date.now() - (pausedPosition * 1000)
        currentTime.value = pausedPosition
      } else {
        // Fresh start
        console.log('[play] Starting fresh playback')
        currentTime.value = 0
        pausedPosition = 0
        playbackStartTime = Date.now()
      }
      
      // Clear pause state
      isPaused.value = false
      
      // Start position tracking
      startPositionTracking()
      
      // Schedule all content from current position
      generateAndScheduleSong(currentTime.value)
      
      isPlaying.value = true
      console.log('[play] SIMPLIFIED: Playback started with setTimeout scheduling')
      
    } catch (error) {
      console.error('Failed to start playback:', error)
      initializationError.value = error instanceof Error ? error.message : 'Unknown error'
    }
  }

  const pause = () => {
    console.log('⏸️ SIMPLIFIED: Pausing playback...')
    
    // Save current position for resume
    pausedPosition = currentTime.value
    
    // Stop position tracking
    stopPositionTracking()
    
    // Clear all scheduled timeouts
    clearScheduledEvents()
    
    isPlaying.value = false
    isPaused.value = true // Mark as paused (not stopped)
    
    console.log(`⏸️ SIMPLIFIED: Playback paused at position ${pausedPosition}s`)
  }

  const stop = () => {
    console.log('🛑 SIMPLIFIED: Stopping all audio playback...')
    
    // Stop position tracking
    stopPositionTracking()
    
    // Clear all scheduled timeouts
    clearScheduledEvents()
    
    // Reset position
    currentTime.value = 0
    pausedPosition = 0
    isPlaying.value = false
    isPaused.value = false
    
    console.log('✅ SIMPLIFIED: All audio playback stopped')
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

  // Lyrics management - now using track/clip pattern
  const getLyricsTrack = () => {
    return songStructure.value.tracks.find(track => track.name === 'Lyrics & Vocals')
  }

  const ensureLyricsTrack = () => {
    let lyricsTrack = getLyricsTrack()
    if (!lyricsTrack) {
      lyricsTrack = {
        id: `track-${Date.now()}`,
        name: 'Lyrics & Vocals',
        instrument: 'vocals',
        category: 'vocals',
        volume: 0.8,
        pan: 0,
        muted: false,
        solo: false,
        clips: [],
        effects: {
          reverb: 0,
          delay: 0,
          distortion: 0
        }
      }
      songStructure.value.tracks.push(lyricsTrack)
      updateSongStructure()
    }
    return lyricsTrack
  }

  const addLyricsSegment = (segment: { startTime: number, endTime: number, text: string, notes?: string[], chordName?: string, voiceId?: string }) => {
    const lyricsTrack = ensureLyricsTrack()
    
    // Create new clip with advanced multi-voice structure
    const newClip: Omit<AudioClip, 'id' | 'trackId'> = {
      startTime: segment.startTime,
      duration: segment.endTime - segment.startTime,
      type: 'lyrics',
      instrument: 'vocals',
      volume: 0.8,
      effects: {
        reverb: 0,
        delay: 0,
        distortion: 0
      },
      // Use new multi-voice structure instead of simple fields
      voices: [
        {
          voice_id: segment.voiceId || 'default',
          lyrics: [
            {
              text: segment.text,
              notes: segment.notes || [],
              start: 0.0, // Start at beginning of clip
              duration: segment.endTime - segment.startTime
            }
          ]
        }
      ]
    }
    
    return addClip(lyricsTrack.id, newClip)
  }

  const updateLyricsSegment = (clipId: string, segment: { startTime: number, endTime: number, text: string, notes?: string[], chordName?: string, voiceId?: string }) => {
    const lyricsTrack = getLyricsTrack()
    if (!lyricsTrack) return

    const clip = lyricsTrack.clips.find(c => c.id === clipId)
    if (clip) {
      clip.startTime = segment.startTime
      clip.duration = segment.endTime - segment.startTime
      
      // Update using new multi-voice structure
      if (!clip.voices || clip.voices.length === 0) {
        // Initialize voices array if it doesn't exist
        clip.voices = [
          {
            voice_id: segment.voiceId || 'default',
            lyrics: []
          }
        ]
      }
      
      // Update the first voice (for simple edits)
      const firstVoice = clip.voices[0]
      firstVoice.voice_id = segment.voiceId || firstVoice.voice_id || 'default'
      
      // Update or create the main lyrics fragment
      if (firstVoice.lyrics.length === 0) {
        firstVoice.lyrics.push({
          text: segment.text,
          notes: segment.notes || [],
          start: 0.0,
          duration: segment.endTime - segment.startTime
        })
      } else {
        // Update existing fragment
        const fragment = firstVoice.lyrics[0]
        fragment.text = segment.text
        fragment.notes = segment.notes || []
        fragment.duration = segment.endTime - segment.startTime
      }
      
      // Remove old simple structure fields if they exist
      delete clip.text
      delete clip.chordName
      delete clip.voiceId
      delete clip.notes
      
      updateSongStructure()
    }
  }

  const removeLyricsSegment = (clipId: string) => {
    const lyricsTrack = getLyricsTrack()
    if (!lyricsTrack) return

    removeClip(lyricsTrack.id, clipId)
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
    console.log(`🎵 Metronome ${metronomeEnabled.value ? 'enabled' : 'disabled'}`)
    
    // If playback is running, re-schedule to add/remove metronome events
    if (isPlaying.value) {
      console.log('Re-scheduling metronome during playback')
      // Clear all events and restart with updated metronome setting
      clearScheduledEvents()
      generateAndScheduleSong(currentTime.value)
    } else {
      // Play a test click when enabling metronome (only when not playing)
      if (metronomeEnabled.value && metronome) {
        metronome.volume.value = Tone.gainToDb(0.6 * masterVolume.value)
        metronome.triggerAttackRelease('C5', '16n')
        console.log('🎵 Metronome test click')
      }
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

  // Generate chord names suitable for sample files
  const generateChordNamesForClip = (clip: AudioClip, key: string = 'C'): string[] => {
    // Chord progressions using actual chord names that match sample files
    const chordProgressions = {
      'C': ['C_major', 'F_major', 'G_major', 'A_minor'],
      'G': ['G_major', 'C_major', 'D_major', 'E_minor'],
      'F': ['F_major', 'As_major', 'C_major', 'D_minor'], // As = Bb
      'Am': ['A_minor', 'F_major', 'C_major', 'G_major'],
      'Em': ['E_minor', 'C_major', 'G_major', 'D_major'],
      'Dm': ['D_minor', 'As_major', 'F_major', 'C_major'] // As = Bb
    }

    const progression = chordProgressions[key as keyof typeof chordProgressions] || chordProgressions['C']
    
    // Generate chord sequence based on clip duration and sample duration
    const sampleDuration = clip.sampleDuration || 1
    const numChords = Math.max(1, Math.floor(clip.duration / sampleDuration))
    
    console.log(`[generateChordNamesForClip] Generating ${numChords} chords for ${clip.duration}s clip with ${sampleDuration}s samples`)
    
    return Array.from({ length: numChords }, (_, i) => 
      progression[i % progression.length]
    )
  }

  // Helper function to determine category from instrument name
  // This can be enhanced to query the backend or use a mapping
  const getInstrumentCategory = (instrument: string): string => {
    // Map common instrument names to categories
    const categoryMap: Record<string, string> = {
      'guitar': 'strings',
      'piano': 'keys',
      'bass': 'strings',
      'drums': 'percussion',
      'synth': 'synths',
      'violin': 'strings',
      'trumpet': 'brass',
      'horn': 'brass',
      'horn1': 'brass',
      'horn2': 'brass',
      'horn3': 'brass',
      'horn4': 'brass',
      'horn5': 'brass',
      'french horn': 'brass',
      'trombone': 'brass',
      'tuba': 'brass',
      'flute': 'woodwinds',
      'clarinet': 'woodwinds',
      'saxophone': 'woodwinds',
      'sax': 'woodwinds',
      'oboe': 'woodwinds',
      'bassoon': 'woodwinds',
      'vocals': 'vocals',
      'voice': 'vocals',
      'choir': 'vocals',
      'strings': 'strings',
      'cello': 'strings',
      'viola': 'strings',
      'double bass': 'strings',
      'harp': 'strings',
      'electric guitar': 'guitars',
      'acoustic guitar': 'guitars',
      'electric piano': 'keys',
      'organ': 'keys',
      'harpsichord': 'keys',
      'xylophone': 'percussion',
      'vibraphone': 'percussion',
      'marimba': 'percussion',
      'timpani': 'percussion',
      'cymbals': 'percussion',
      'snare': 'percussion',
      'kick': 'percussion',
      'hihat': 'percussion'
    }
    
    // Try exact match first
    if (categoryMap[instrument.toLowerCase()]) {
      return categoryMap[instrument.toLowerCase()]
    }
    
    // Try partial matches
    for (const [key, category] of Object.entries(categoryMap)) {
      if (instrument.toLowerCase().includes(key)) {
        return category
      }
    }
    
    // Default fallback
    return 'other'
  }

  // Get category from track, with fallback to instrument name mapping
  const getTrackCategory = (track: Track): string => {
    if (track.category) {
      return track.category
    }
    return getInstrumentCategory(track.instrument)
  }

  // Migration function to convert old lyrics clips to new multi-voice structure
  const migrateLyricsClipsToMultiVoice = () => {
    const lyricsTrack = getLyricsTrack()
    if (!lyricsTrack) return

    let migrationCount = 0
    
    lyricsTrack.clips.forEach(clip => {
      if (clip.type === 'lyrics' && !clip.voices && (clip.text || clip.notes)) {
        // This is an old-format lyrics clip, migrate it
        clip.voices = [
          {
            voice_id: clip.voiceId || 'default',
            lyrics: [
              {
                text: clip.text || '',
                notes: clip.notes || [],
                start: 0.0,
                duration: clip.duration
              }
            ]
          }
        ]
        
        // Remove old simple structure fields
        delete clip.text
        delete clip.chordName
        delete clip.voiceId
        delete clip.notes
        
        migrationCount++
      }
    })
    
    if (migrationCount > 0) {
      console.log(`Migrated ${migrationCount} lyrics clips to new multi-voice structure`)
      updateSongStructure()
    }
  }

  // Auto-migrate existing clips on store initialization
  migrateLyricsClipsToMultiVoice()

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
    selectedClipId,
    isInitialized,
    isInitializing,
    initializationError,
    songStructure,
    totalTracks,
    selectedTrack,
    getSelectedClip,
    
    // Audio control
    initializeAudio,
    forceInitialize,
    resetAudio,
    play,
    pause,
    stop,
    setTempo,
    toggleLoop,
    toggleMetronome,
    setMasterVolume,
    setZoom,
    
    // Track management
    addTrack,
    removeTrack,
    updateTrack,
    selectTrack: (trackId: string | null) => { selectedTrackId.value = trackId },
    
    // Clip management
    addClip,
    removeClip,
    updateClip,
    selectClip: (clipId: string | null) => { selectedClipId.value = clipId },
    
    // Song structure
    updateSongStructure,
    loadSongStructure,
    exportSongStructure,
    
    // Lyrics management
    getLyricsTrack,
    ensureLyricsTrack,
    addLyricsSegment,
    updateLyricsSegment,
    removeLyricsSegment,
    migrateLyricsClipsToMultiVoice,
    
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
    scheduleClipWithSynth,
    
    // Preview audio management
    registerPreviewAudio,
    unregisterPreviewAudio
  }
})
