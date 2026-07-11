// Mirrors of backend Pydantic models (subset the UI needs)

export interface Asset {
  id: string
  asset_type: string
  filename: string
  relative_path: string
  extension: string
  file_size: number
  modified_at: string | null
  analysis_status: string
  tags: string[]
  user_description: string
  generated_description: string
  license_notes: string
  source: string
  is_missing: boolean
}

export interface NoteEvent {
  id: string
  pitch: string
  midi_note: number
  start_beat: number
  duration_beats: number
  velocity: number
  lyric_syllable: string
}

export interface Clip {
  id: string
  section_id: string
  clip_type: 'midi' | 'sample' | 'vocal'
  start_beat: number
  duration_beats: number
  note_events: NoteEvent[]
  source_asset_id: string | null
  gain_db: number
  loop: boolean
  fade_in_seconds: number
  fade_out_seconds: number
  source_offset_seconds: number
}

export interface Effect {
  id: string
  effect_type: string
  enabled: boolean
  params: Record<string, number>
}

export interface Track {
  id: string
  name: string
  track_type: string
  instrument_config: { soundfont_asset_id: string | null; program: number; is_drum_kit: boolean; bank: number }
  clips: Clip[]
  effects: { effects: Effect[] }
  volume: number
  pan: number
  mute: boolean
  solo: boolean
  voice_profile_id: string | null
  vocal_style: 'sing' | 'rap' | 'soft' | 'powerful'
}

export interface Section {
  id: string
  name: string
  start_bar: number
  length_bars: number
  energy: number
  description: string
}

export interface LyricsLine { id: string; section_id: string; text: string }

export interface SongProject {
  id: string
  title: string
  style: string
  bpm: number
  key: string
  time_signature: string
  sections: Section[]
  tracks: Track[]
  lyrics: { id: string; language: string; lines: LyricsLine[] }
  mix_settings: { master_volume: number; normalize: boolean; limiter: boolean; master_effects: { effects: Effect[] } }
  render_status: string
  stems: StemRef[]
  midi_files: Record<string, string>
  updated_at: string
}

export interface ProjectSummary {
  id: string
  title: string
  style: string
  bpm: number
  key: string
  updated_at: string
  track_count: number
}

export interface StemRef {
  track_id: string
  stem_type: 'instrument' | 'sample' | 'vocal'
  path: string
  asset_id: string | null
  rendered_at: string
}

// --- PlaybackManifest ---

export interface SectionTiming {
  section_id: string
  name: string
  start_bar: number
  length_bars: number
  start_beat: number
  end_beat: number
  start_seconds: number
  end_seconds: number
  energy: number
}

export interface ClipTiming {
  clip_id: string
  track_id: string
  section_id: string
  clip_type: string
  start_beat: number
  end_beat: number
  start_seconds: number
  end_seconds: number
  source_asset_id: string | null
}

export interface NoteTiming {
  note_id: string
  track_id: string
  clip_id: string
  midi_note: number
  pitch: string
  velocity: number
  start_beat: number
  end_beat: number
  start_seconds: number
  end_seconds: number
  lyric_syllable: string
}

export interface ManifestTrack {
  track_id: string
  name: string
  track_type: string
  volume: number
  pan: number
  mute: boolean
  solo: boolean
  soundfont_asset_id: string | null
  voice_profile_id: string | null
}

export interface WordTiming {
  word: string
  start_time: number
  end_time: number
  linked_note_id: string | null
}

export interface LyricsAlignmentLine {
  line_id: string
  section_id: string
  text: string
  start_time: number
  end_time: number
  words: WordTiming[]
  confidence: number
}

export interface WaveformMeta {
  track_id: string
  path: string
  peaks: number[]
  duration_seconds: number
}

export interface PlaybackManifest {
  project_id: string
  title: string
  bpm: number
  time_signature: string
  beats_per_bar: number
  total_bars: number
  duration_seconds: number
  sections: SectionTiming[]
  tracks: ManifestTrack[]
  clips: ClipTiming[]
  stems: StemRef[]
  waveform_metadata: WaveformMeta[]
  midi_note_metadata: NoteTiming[]
  lyrics_alignment: LyricsAlignmentLine[]
  markers: { bar: number; seconds: number; label: string }[]
  mix_settings: { master_volume: number }
}

export interface VoiceProfile {
  id: string
  name: string
  source_recording_ids: string[]
  consent_confirmed: boolean
  consent_notes: string
  performer_alias: string
  vocal_range: string
  language_notes: string
  status: string
  usage_restrictions: string
  created_at: string
}

export interface ExportJob {
  id: string
  project_id: string
  status: string
  requested_formats: string[]
  output_files: string[]
  started_at: string | null
  completed_at: string | null
  warnings: string[]
  errors: string[]
}

export interface ChatResponse {
  reply: string
  operations: { op_type: string; summary: string; applied: boolean; error: string | null }[]
  project: SongProject
}
