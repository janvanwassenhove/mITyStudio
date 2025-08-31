/**
 * Test utility for creating sample vocal tracks to test the master lyric lane
 */

import type { Track, AudioClip, LyricFragment } from '../stores/audioStore'

export interface TestSong {
  tracks: Track[]
  title: string
  duration: number
}

/**
 * Creates a test song with vocal tracks for testing the master lyric lane
 */
export function createTestSongWithVocals(): TestSong {
  // Sample lyrics for testing (original content)
  const sampleLyrics: LyricFragment[] = [
    {
      text: "Walking through the digital world",
      notes: ["C4", "D4", "E4", "F4", "G4"],
      start: 0,
      durations: [0.5, 0.5, 0.5, 0.5, 1.0]
    },
    {
      text: "Code and music come alive",
      notes: ["A4", "G4", "F4", "E4", "D4"],
      start: 3,
      durations: [0.6, 0.6, 0.6, 0.6, 1.0]
    }
  ]

  const harmonyLyrics: LyricFragment[] = [
    {
      text: "Digital world echoes",
      notes: ["E4", "F4", "G4"],
      start: 0.5,
      durations: [0.8, 0.8, 1.4]
    },
    {
      text: "Music flows",
      notes: ["C5", "B4"],
      start: 4,
      durations: [1.0, 1.0]
    }
  ]

  const leadVocalClip: AudioClip = {
    id: "clip-lead-vocal-1",
    trackId: "track-lead-vocals",
    startTime: 4,
    duration: 8,
    type: "lyrics",
    instrument: "vocals",
    voiceId: "soprano01",
    volume: 0.8,
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
      lyrics: sampleLyrics
    }]
  }

  const harmonyVocalClip: AudioClip = {
    id: "clip-harmony-vocal-1", 
    trackId: "track-harmony-vocals",
    startTime: 4,
    duration: 8,
    type: "lyrics",
    instrument: "vocals",
    voiceId: "alto01",
    volume: 0.6,
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
      lyrics: harmonyLyrics
    }]
  }

  const leadTrack: Track = {
    id: "track-lead-vocals",
    name: "Lead Vocals",
    instrument: "vocals",
    category: "vocal",
    voiceId: "soprano01",
    volume: 0.8,
    pan: 0,
    muted: false,
    solo: false,
    clips: [leadVocalClip],
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

  const harmonyTrack: Track = {
    id: "track-harmony-vocals",
    name: "Harmony Vocals",
    instrument: "vocals", 
    category: "vocal",
    voiceId: "alto01",
    volume: 0.6,
    pan: -0.3,
    muted: false,
    solo: false,
    clips: [harmonyVocalClip],
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

  return {
    title: "Test Song with Vocals",
    duration: 16, // bars
    tracks: [leadTrack, harmonyTrack]
  }
}

/**
 * Creates a test song with extended vocal structure including syllables and phonemes
 */
export function createExtendedTestSong(): TestSong {
  const extendedLyrics: LyricFragment[] = [
    {
      text: "Music flows like water",
      notes: ["C4", "D4", "E4", "F4", "G4"],
      start: 0,
      durations: [0.5, 0.5, 0.5, 0.8, 0.7],
      // Extended structure with syllables and phonemes
      syllables: [
        { t: "Mu", noteIdx: [0], dur: 0.25 },
        { t: "sic", noteIdx: [0], dur: 0.25 },
        { t: "flows", noteIdx: [1, 2], dur: 1.0, melisma: true },
        { t: "like", noteIdx: [3], dur: 0.8 },
        { t: "wa", noteIdx: [4], dur: 0.35 },
        { t: "ter", noteIdx: [4], dur: 0.35 }
      ],
      phonemes: ["m", "ju", "z", "ɪ", "k", "f", "l", "oʊ", "z", "l", "aɪ", "k", "w", "ɔ", "t", "ər"]
    }
  ]

  const extendedClip: AudioClip = {
    id: "clip-extended-vocal",
    trackId: "track-extended-vocals",
    startTime: 0,
    duration: 4,
    type: "lyrics",
    instrument: "vocals",
    voiceId: "soprano01",
    volume: 0.8,
    // Extended structure fields
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
      lyrics: extendedLyrics
    }]
  }

  const extendedTrack: Track = {
    id: "track-extended-vocals",
    name: "Extended Structure Vocals",
    instrument: "vocals",
    category: "vocal", 
    voiceId: "soprano01",
    volume: 0.8,
    pan: 0,
    muted: false,
    solo: false,
    clips: [extendedClip],
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

  return {
    title: "Extended Vocal Structure Test",
    duration: 8,
    tracks: [extendedTrack]
  }
}
