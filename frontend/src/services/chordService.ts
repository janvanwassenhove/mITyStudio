import * as Tone from 'tone'

// Chord types available in the samples
export type ChordType = 'major' | 'minor' | 'dom7' | 'maj7' | 'min7' | 'augmented' | 'diminished' | 'sus2' | 'sus4'

// Note names available in samples
export type NoteName = 'C' | 'C#' | 'D' | 'D#' | 'E' | 'F' | 'F#' | 'G' | 'G#' | 'A' | 'A#' | 'B'

// Instrument types with samples
export type SampleInstrument = 'piano' | 'guitar'

// Chord progression types
export type ChordProgressionType = 'I-V-vi-IV' | 'vi-IV-I-V' | 'I-vi-IV-V' | 'ii-V-I' | 'I-IV-V' | 'vi-V-IV-III'

// Key signatures and their relative information
export interface KeyInfo {
  name: string
  root: NoteName
  scale: NoteName[]
  chords: {
    I: { root: NoteName; type: ChordType }
    ii: { root: NoteName; type: ChordType }
    iii: { root: NoteName; type: ChordType }
    IV: { root: NoteName; type: ChordType }
    V: { root: NoteName; type: ChordType }
    vi: { root: NoteName; type: ChordType }
    vii: { root: NoteName; type: ChordType }
  }
}

// Chord information
export interface ChordInfo {
  root: NoteName
  type: ChordType
  notes: string[]
  samplePath: string
}

// Generated chord progression
export interface ChordProgression {
  chords: ChordInfo[]
  duration: number
  instrument: SampleInstrument
}

export class ChordService {
  // Key definitions with proper chord progressions
  private static readonly KEYS: Record<string, KeyInfo> = {
    'C': {
      name: 'C Major',
      root: 'C',
      scale: ['C', 'D', 'E', 'F', 'G', 'A', 'B'],
      chords: {
        I: { root: 'C', type: 'major' },
        ii: { root: 'D', type: 'minor' },
        iii: { root: 'E', type: 'minor' },
        IV: { root: 'F', type: 'major' },
        V: { root: 'G', type: 'major' },
        vi: { root: 'A', type: 'minor' },
        vii: { root: 'B', type: 'diminished' }
      }
    },
    'G': {
      name: 'G Major',
      root: 'G',
      scale: ['G', 'A', 'B', 'C', 'D', 'E', 'F#'],
      chords: {
        I: { root: 'G', type: 'major' },
        ii: { root: 'A', type: 'minor' },
        iii: { root: 'B', type: 'minor' },
        IV: { root: 'C', type: 'major' },
        V: { root: 'D', type: 'major' },
        vi: { root: 'E', type: 'minor' },
        vii: { root: 'F#', type: 'diminished' }
      }
    },
    'F': {
      name: 'F Major',
      root: 'F',
      scale: ['F', 'G', 'A', 'A#', 'C', 'D', 'E'],
      chords: {
        I: { root: 'F', type: 'major' },
        ii: { root: 'G', type: 'minor' },
        iii: { root: 'A', type: 'minor' },
        IV: { root: 'A#', type: 'major' },
        V: { root: 'C', type: 'major' },
        vi: { root: 'D', type: 'minor' },
        vii: { root: 'E', type: 'diminished' }
      }
    },
    'Am': {
      name: 'A Minor',
      root: 'A',
      scale: ['A', 'B', 'C', 'D', 'E', 'F', 'G'],
      chords: {
        I: { root: 'A', type: 'minor' },
        ii: { root: 'B', type: 'diminished' },
        iii: { root: 'C', type: 'major' },
        IV: { root: 'D', type: 'minor' },
        V: { root: 'E', type: 'minor' },
        vi: { root: 'F', type: 'major' },
        vii: { root: 'G', type: 'major' }
      }
    },
    'Em': {
      name: 'E Minor',
      root: 'E',
      scale: ['E', 'F#', 'G', 'A', 'B', 'C', 'D'],
      chords: {
        I: { root: 'E', type: 'minor' },
        ii: { root: 'F#', type: 'diminished' },
        iii: { root: 'G', type: 'major' },
        IV: { root: 'A', type: 'minor' },
        V: { root: 'B', type: 'minor' },
        vi: { root: 'C', type: 'major' },
        vii: { root: 'D', type: 'major' }
      }
    },
    'Dm': {
      name: 'D Minor',
      root: 'D',
      scale: ['D', 'E', 'F', 'G', 'A', 'A#', 'C'],
      chords: {
        I: { root: 'D', type: 'minor' },
        ii: { root: 'E', type: 'diminished' },
        iii: { root: 'F', type: 'major' },
        IV: { root: 'G', type: 'minor' },
        V: { root: 'A', type: 'minor' },
        vi: { root: 'A#', type: 'major' },
        vii: { root: 'C', type: 'major' }
      }
    }
  }

  // Common chord progressions
  private static readonly PROGRESSIONS: Record<ChordProgressionType, string[]> = {
    'I-V-vi-IV': ['I', 'V', 'vi', 'IV'],
    'vi-IV-I-V': ['vi', 'IV', 'I', 'V'],
    'I-vi-IV-V': ['I', 'vi', 'IV', 'V'],
    'ii-V-I': ['ii', 'V', 'I'],
    'I-IV-V': ['I', 'IV', 'V'],
    'vi-V-IV-III': ['vi', 'V', 'IV', 'iii']
  }

  /**
   * Generate a chord progression for a given key and instrument
   */
  static generateChordProgression(
    key: string,
    progressionType: ChordProgressionType,
    instrument: SampleInstrument,
    numRepeats: number = 1,
    chordDuration: number = 2
  ): ChordProgression {
    const keyInfo = this.KEYS[key]
    if (!keyInfo) {
      throw new Error(`Unsupported key: ${key}`)
    }

    const progressionPattern = this.PROGRESSIONS[progressionType]
    const chords: ChordInfo[] = []

    for (let repeat = 0; repeat < numRepeats; repeat++) {
      for (const romanNumeral of progressionPattern) {
        const chordDef = keyInfo.chords[romanNumeral as keyof typeof keyInfo.chords]
        if (chordDef) {
          const chordInfo = this.createChordInfo(chordDef.root, chordDef.type, instrument)
          chords.push(chordInfo)
        }
      }
    }

    return {
      chords,
      duration: chords.length * chordDuration,
      instrument
    }
  }

  /**
   * Generate a random chord progression
   */
  static generateRandomProgression(
    key: string,
    instrument: SampleInstrument,
    length: number = 4,
    chordDuration: number = 2
  ): ChordProgression {
    const keyInfo = this.KEYS[key]
    if (!keyInfo) {
      throw new Error(`Unsupported key: ${key}`)
    }

    const chords: ChordInfo[] = []
    const romanNumerals = Object.keys(keyInfo.chords)

    for (let i = 0; i < length; i++) {
      const randomRoman = romanNumerals[Math.floor(Math.random() * romanNumerals.length)]
      const chordDef = keyInfo.chords[randomRoman as keyof typeof keyInfo.chords]
      const chordInfo = this.createChordInfo(chordDef.root, chordDef.type, instrument)
      chords.push(chordInfo)
    }

    return {
      chords,
      duration: chords.length * chordDuration,
      instrument
    }
  }

  /**
   * Get all available chord progressions
   */
  static getAvailableProgressions(): ChordProgressionType[] {
    return Object.keys(this.PROGRESSIONS) as ChordProgressionType[]
  }

  /**
   * Get all available keys
   */
  static getAvailableKeys(): string[] {
    return Object.keys(this.KEYS)
  }

  /**
   * Create chord info with sample path
   */
  private static createChordInfo(root: NoteName, type: ChordType, instrument: SampleInstrument): ChordInfo {
    const notes = this.getChordNotes(root, type)
    const samplePath = this.getSamplePath(root, type, instrument)
    
    return {
      root,
      type,
      notes,
      samplePath
    }
  }

  /**
   * Get the theoretical notes for a chord (for display purposes)
   */
  private static getChordNotes(root: NoteName, type: ChordType): string[] {
    const noteMapping: Record<NoteName, number> = {
      'C': 0, 'C#': 1, 'D': 2, 'D#': 3, 'E': 4, 'F': 5,
      'F#': 6, 'G': 7, 'G#': 8, 'A': 9, 'A#': 10, 'B': 11
    }

    const noteNames = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    const rootIndex = noteMapping[root]

    const intervals: Record<ChordType, number[]> = {
      'major': [0, 4, 7],
      'minor': [0, 3, 7],
      'dom7': [0, 4, 7, 10],
      'maj7': [0, 4, 7, 11],
      'min7': [0, 3, 7, 10],
      'augmented': [0, 4, 8],
      'diminished': [0, 3, 6],
      'sus2': [0, 2, 7],
      'sus4': [0, 5, 7]
    }

    const chordIntervals = intervals[type] || intervals.major
    return chordIntervals.map(interval => {
      const noteIndex = (rootIndex + interval) % 12
      return noteNames[noteIndex] + '4'
    })
  }

  /**
   * Get the sample file path for a chord
   */
  private static getSamplePath(root: NoteName, type: ChordType, instrument: SampleInstrument): string {
    const duration = instrument === 'piano' ? '2_0s' : '1_0s'
    return `/samples/${instrument}/${duration}/wav/${root}_${type}.wav`
  }

  /**
   * Create a Tone.js player for a chord sample
   */
  static async createChordPlayer(chordInfo: ChordInfo, volume: number = 0.8): Promise<Tone.Player> {
    const player = new Tone.Player({
      url: chordInfo.samplePath,
      autostart: false,
      volume: Tone.gainToDb(Math.max(0.01, volume)),
    }).toDestination()

    // Wait for the sample to load
    await Tone.loaded()
    return player
  }

  /**
   * Generate chord progression clips for a track
   */
  static generateChordClips(
    progression: ChordProgression,
    startTime: number = 0,
    chordDuration: number = 2
  ): Array<{
    startTime: number
    duration: number
    chordInfo: ChordInfo
    sampleUrl: string
  }> {
    return progression.chords.map((chord, index) => ({
      startTime: startTime + (index * chordDuration),
      duration: chordDuration,
      chordInfo: chord,
      sampleUrl: chord.samplePath
    }))
  }

  /**
   * Get chord progression suggestions
   */
  static getProgressionSuggestions(): Array<{
    name: string
    type: ChordProgressionType
    description: string
  }> {
    return [
      {
        name: 'Pop Progression',
        type: 'I-V-vi-IV',
        description: 'Classic pop/rock progression (C-G-Am-F in C major)'
      },
      {
        name: 'Alternative Pop',
        type: 'vi-IV-I-V',
        description: 'Modern alternative progression (Am-F-C-G in C major)'
      },
      {
        name: 'Traditional',
        type: 'I-vi-IV-V',
        description: 'Traditional doo-wop progression (C-Am-F-G in C major)'
      },
      {
        name: 'Jazz ii-V-I',
        type: 'ii-V-I',
        description: 'Essential jazz progression (Dm-G-C in C major)'
      },
      {
        name: 'Blues/Rock',
        type: 'I-IV-V',
        description: 'Classic blues and rock progression (C-F-G in C major)'
      },
      {
        name: 'Alternative',
        type: 'vi-V-IV-III',
        description: 'Alternative/indie progression (Am-G-F-Em in C major)'
      }
    ]
  }

  /**
   * Public method to generate chord notes from a root note
   */
  static generateChordNotes(root: string, type: ChordType = 'major'): string[] {
    // Clean the root note (remove octave numbers)
    const cleanRoot = root.replace(/\d+$/, '') as NoteName
    return this.getChordNotes(cleanRoot, type)
  }

  /**
   * Public method to create chord info
   */
  static createChordData(root: NoteName, type: ChordType = 'major', instrument: SampleInstrument = 'piano'): ChordInfo {
    return this.createChordInfo(root, type, instrument)
  }
}
