<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '../api/client'
import type { Clip, NoteEvent, Track } from '../api/types'
import { useStudioStore } from '../stores/studio'
import { usePlaybackStore } from '../stores/playback'
import { DRUM_SVG } from '../lib/drumIcons'
import BeatSequencer from './BeatSequencer.vue'

const props = defineProps<{ track: Track; clip: Clip }>()
const emit = defineEmits<{ changed: [] }>()

const { t } = useI18n()
const studio = useStudioStore()
const playback = usePlaybackStore()
const uid = () => crypto.randomUUID().replace(/-/g, '')

// ---------------- shared synth preview ----------------
let ctx: AudioContext | null = null
function ensureCtx() {
  if (!ctx) ctx = new AudioContext()
  return ctx
}
function playTone(midi: number, dur = 0.5, delay = 0, gainVal = 0.16) {
  const c = ensureCtx()
  const t = c.currentTime + delay
  const g = c.createGain()
  g.connect(c.destination)
  g.gain.setValueAtTime(0, t)
  g.gain.linearRampToValueAtTime(gainVal, t + 0.015)
  g.gain.exponentialRampToValueAtTime(0.001, t + dur)
  for (const detune of [0, 6]) {
    const o = c.createOscillator()
    o.type = 'triangle'
    o.frequency.value = 440 * 2 ** ((midi - 69) / 12)
    o.detune.value = detune
    o.connect(g)
    o.start(t)
    o.stop(t + dur + 0.05)
  }
}
function playDrum(midi: number) {
  const c = ensureCtx()
  const t = c.currentTime
  const g = c.createGain()
  g.connect(c.destination)
  if (midi === 36) { // kick
    const o = c.createOscillator()
    o.frequency.setValueAtTime(140, t)
    o.frequency.exponentialRampToValueAtTime(45, t + 0.12)
    g.gain.setValueAtTime(0.5, t)
    g.gain.exponentialRampToValueAtTime(0.001, t + 0.18)
    o.connect(g); o.start(t); o.stop(t + 0.2)
    return
  }
  // noise-based hits (snare/hats/cymbals/shaker)
  const len = [49, 51].includes(midi) ? 0.7 : midi === 46 ? 0.3 : 0.12
  const buf = c.createBuffer(1, c.sampleRate * len, c.sampleRate)
  const d = buf.getChannelData(0)
  for (let i = 0; i < d.length; i++) d[i] = (Math.random() * 2 - 1) * (1 - i / d.length) ** 2
  const src = c.createBufferSource()
  src.buffer = buf
  const f = c.createBiquadFilter()
  f.type = [49, 51, 42, 46, 70].includes(midi) ? 'highpass' : 'bandpass'
  f.frequency.value = midi === 38 ? 1800 : midi === 39 ? 1200 : [45, 47, 50].includes(midi) ? 300 + (midi - 45) * 120 : 6000
  g.gain.setValueAtTime(0.35, t)
  g.gain.exponentialRampToValueAtTime(0.001, t + len)
  src.connect(f).connect(g)
  src.start(t)
  if ([45, 47, 50].includes(midi)) playTone(midi + 12, 0.25, 0, 0.2) // tom body
}

// ---------------- write vs practice + step record ----------------
const writeMode = ref(false)   // practice by default: tap to hear only

// first-use coach mark for the drum modes
const showDrumCoach = ref(props.track.track_type === 'drums'
  && !localStorage.getItem('mity-drums-coach'))
function dismissDrumCoach() {
  showDrumCoach.value = false
  localStorage.setItem('mity-drums-coach', '1')
}

// ---------------- loop preview with the REAL instrument sound -------------
const looping = ref(false)
const loopLoading = ref(false)
let loopAudio: HTMLAudioElement | null = null
let loopTimer: ReturnType<typeof setTimeout> | null = null

function loopNotes() {
  const bpb = studio.manifest?.beats_per_bar ?? 4
  const span = bpb * 2  // two-bar loop
  // smart drums preview the designed BUFFER; other surfaces loop the clip
  if (props.track.track_type === 'drums' && drumMode.value === 'smart') {
    return smartBuffer.value
      .filter((h) => h.beat < span)
      .map((h) => ({ midi_note: h.midi, start_beat: h.beat,
                     duration_beats: 0.2, velocity: h.vel }))
  }
  return props.clip.note_events
    .filter((n) => n.start_beat < span)
    .map((n) => ({ midi_note: n.midi_note, start_beat: n.start_beat,
                   duration_beats: Math.min(n.duration_beats, span - n.start_beat),
                   velocity: n.velocity }))
}

async function refreshLoop() {
  const p = studio.project
  if (!p || !looping.value) return
  const notes = loopNotes()
  if (!notes.length) { lastInsert.value = t('play.nothingToLoop'); return }
  loopLoading.value = true
  try {
    const cfg = props.track.instrument_config
    const res = await fetch('/api/projects/preview/instrument', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        soundfont_asset_id: cfg.soundfont_asset_id, bank: cfg.bank,
        program: cfg.program, is_drum_kit: cfg.is_drum_kit,
        bpm: p.bpm, notes,
      }),
    })
    if (!res.ok) throw new Error((await res.json()).detail ?? res.statusText)
    const url = URL.createObjectURL(await res.blob())
    const next = new Audio(url)
    next.loop = true
    if (loopAudio) { loopAudio.pause() }
    loopAudio = next
    if (looping.value) void next.play()
  } catch (e) {
    lastInsert.value = String(e)
    looping.value = false
  } finally {
    loopLoading.value = false
  }
}

function toggleLoop() {
  looping.value = !looping.value
  if (looping.value) void refreshLoop()
  else if (loopAudio) { loopAudio.pause(); loopAudio = null }
}

function queueLoopRefresh() {
  if (!looping.value) return
  if (loopTimer) clearTimeout(loopTimer)
  loopTimer = setTimeout(refreshLoop, 700)
}

onBeforeUnmount(() => { if (loopAudio) loopAudio.pause() })

// ---------------- insert into clip ----------------
const lastInsert = ref('')
function playheadBeatInClip(): number {
  const m = studio.manifest
  if (!m) return 0
  const beat = (playback.playhead * m.bpm) / 60 - props.clip.start_beat
  const snapped = Math.round(beat / 0.25) * 0.25
  return Math.min(Math.max(snapped, 0), Math.max(props.clip.duration_beats - 0.25, 0))
}
function insertNotes(midis: number[], dur: number, vel = 100, stagger = 0) {
  if (!writeMode.value) return   // practice mode: hear only
  const at = playheadBeatInClip()
  midis.forEach((m, i) => {
    props.clip.note_events.push({
      id: uid(), pitch: '', midi_note: m,
      start_beat: Math.min(at + i * stagger, props.clip.duration_beats - 0.1),
      duration_beats: Math.min(dur, props.clip.duration_beats - at),
      velocity: vel, lyric_syllable: '',
    } as NoteEvent)
  })
  // step record: advance the playhead so the next tap lands after this note
  const p = studio.project
  if (p) playback.playhead += (dur * 60) / p.bpm
  lastInsert.value = t('play.writtenAt', { beat: (at + props.clip.start_beat).toFixed(2) })
  emit('changed')
  queueLoopRefresh()
}

// ---------------- smart drums (GarageBand-style board) ----------------
const drumMode = ref<'smart' | 'seq' | 'pads'>('smart')

// --- drum kit picker (real Drum Kit presets from the SoundFont library) ---
interface KitPreset { label: string; asset_id: string; soundfont: string; bank: number; program: number }
const kits = ref<KitPreset[]>([])
const kitIndex = ref(0)

const currentKit = computed(() => kits.value[kitIndex.value] ?? null)

onMounted(async () => {
  if (props.track.track_type !== 'drums') return
  try {
    const catalog = await api.get<{ category: string; presets: KitPreset[] }[]>('/assets/instruments')
    kits.value = catalog.find((c) => c.category === 'Drum Kits')?.presets ?? []
    const cfg = props.track.instrument_config
    const i = kits.value.findIndex((k) =>
      k.asset_id === cfg.soundfont_asset_id && k.bank === cfg.bank && k.program === cfg.program)
    if (i >= 0) kitIndex.value = i
  } catch { /* catalog unavailable — picker hides */ }
})

function pickKit(delta: number) {
  if (!kits.value.length) return
  kitIndex.value = (kitIndex.value + delta + kits.value.length) % kits.value.length
  const k = kits.value[kitIndex.value]
  props.track.instrument_config.soundfont_asset_id = k.asset_id
  props.track.instrument_config.bank = k.bank
  props.track.instrument_config.program = k.program
  props.track.instrument_config.is_drum_kit = true
  lastInsert.value = t('play.kit') + ': ' + k.label
  emit('changed')
  if (looping.value) void refreshLoop()   // hear the new kit immediately
  else playDrum(36)
}

function resetBoard() {
  for (const e of smartEls.value) e.placed = false
  smartBuffer.value = []
  lastInsert.value = t('play.boardCleared')
}
interface SmartEl { midis: number[]; label: string; icon: string; placed: boolean; x: number; y: number }
const smartEls = ref<SmartEl[]>([
  { midis: [36], label: 'Kick', icon: '🦶', placed: true, x: 0.4, y: 0.65 },
  { midis: [38], label: 'Snare', icon: '🥁', placed: true, x: 0.35, y: 0.6 },
  { midis: [42], label: 'Hi-Hat', icon: '🎩', placed: true, x: 0.5, y: 0.5 },
  { midis: [46], label: 'Open Hat', icon: '✨', placed: false, x: 0.5, y: 0.5 },
  { midis: [51], label: 'Ride', icon: '🛎', placed: false, x: 0.4, y: 0.4 },
  { midis: [49], label: 'Crash', icon: '💥', placed: false, x: 0.3, y: 0.6 },
  { midis: [45, 47, 50], label: 'Toms', icon: '🥁', placed: false, x: 0.5, y: 0.5 },
  { midis: [39], label: 'Clap', icon: '👏', placed: false, x: 0.4, y: 0.5 },
  { midis: [70], label: 'Shaker', icon: '🪇', placed: false, x: 0.5, y: 0.4 },
])

const beatsPerBar = computed(() => studio.manifest?.beats_per_bar ?? 4)

const SMART_BARS = 4

function smartPattern(el: SmartEl): { beat: number; midi: number; vel: number }[] {
  const c = el.x            // simple → complex
  const loud = 1 - el.y     // board top = loud
  const bars = SMART_BARS
  const base = Math.round(45 + 75 * loud)
  const out: { beat: number; midi: number; vel: number }[] = []
  const push = (bar: number, b: number, midi: number, velScale = 1) => {
    const beat = bar * beatsPerBar.value + b
    if (beat < SMART_BARS * beatsPerBar.value) {
      out.push({ beat, midi, vel: Math.max(25, Math.min(127, Math.round(base * velScale + (b % 1 === 0 ? 8 : -6)))) })
    }
  }
  for (let bar = 0; bar < bars; bar++) {
    const m = el.midis[0]
    if (m === 36) {          // kick
      push(bar, 0, m, 1.05); push(bar, 2, m)
      if (c > 0.35) push(bar, 2.5, m, 0.85)
      if (c > 0.6) push(bar, 3.5, m, 0.8)
      if (c > 0.85) push(bar, 1.75, m, 0.7)
    } else if (m === 38) {   // snare + ghosts
      push(bar, 1, m, 1.05); push(bar, 3, m, 1.05)
      if (c > 0.45) push(bar, 3.75, m, 0.35)
      if (c > 0.7) { push(bar, 1.75, m, 0.3); push(bar, 2.25, m, 0.3) }
    } else if (m === 42) {   // hi-hat
      const step = c < 0.33 ? 1 : c < 0.7 ? 0.5 : 0.25
      for (let b = 0; b < beatsPerBar.value; b += step) push(bar, b, m, b % 1 === 0 ? 0.95 : 0.7)
    } else if (m === 46) {   // open hat pushes
      push(bar, beatsPerBar.value - 0.5, m, 0.9)
      if (c > 0.5) push(bar, 1.5, m, 0.8)
    } else if (m === 51) {   // ride
      for (let b = 0; b < beatsPerBar.value; b++) {
        push(bar, b, m, 0.9)
        if (c > 0.5) push(bar, b + 0.66, m, 0.6)
      }
    } else if (m === 49) {   // crash
      if (bar % (c > 0.6 ? 2 : 4) === 0) push(bar, 0, m, 1)
    } else if (el.midis.length === 3) {  // toms fill
      if (bar % 4 === 3) {
        const hits = c < 0.4 ? 2 : c < 0.75 ? 3 : 4
        for (let i = 0; i < hits; i++) push(bar, beatsPerBar.value - 1 + i * 0.25, el.midis[Math.min(i, 2)], 0.85 + i * 0.05)
      }
    } else if (m === 39) {   // clap layers the backbeat
      push(bar, 1, m, 0.9); push(bar, 3, m, 0.9)
      if (c > 0.6) push(bar, 3.5, m, 0.6)
    } else if (m === 70) {   // shaker
      const step = c < 0.5 ? 0.5 : 0.25
      for (let b = 0; b < beatsPerBar.value; b += step) push(bar, b, m, 0.6)
    }
  }
  return out
}

// smart drums design into a BUFFER — "＋ Add as clip" drops it in the song
const smartBuffer = ref<{ beat: number; midi: number; vel: number }[]>([])

function regenerateSmart() {
  smartBuffer.value = smartEls.value
    .filter((e) => e.placed)
    .flatMap((e) => smartPattern(e))
  lastInsert.value = t('play.patternHits', { n: smartBuffer.value.length, bars: SMART_BARS })
  queueLoopRefresh()
}

function addSmartAsClip() {
  const p = studio.project
  const m = studio.manifest
  if (!p || !m) return
  if (!smartBuffer.value.length) regenerateSmart()
  if (!smartBuffer.value.length) { lastInsert.value = t('play.placePieces'); return }
  const track = p.tracks.find((t) => t.id === props.track.id)
  if (!track) return
  const bpb = m.beats_per_bar
  const startBar = Math.round(((playback.playhead * m.bpm) / 60) / bpb)
  const clip: Clip = {
    id: uid(), section_id: '', clip_type: 'midi',
    start_beat: startBar * bpb, duration_beats: SMART_BARS * bpb,
    note_events: smartBuffer.value.map((h) => ({
      id: uid(), pitch: '', midi_note: h.midi, start_beat: h.beat,
      duration_beats: 0.2, velocity: h.vel, lyric_syllable: '',
    } as NoteEvent)),
    source_asset_id: null, gain_db: 0, loop: false,
    fade_in_seconds: 0, fade_out_seconds: 0, source_offset_seconds: 0,
  }
  track.clips.push(clip)
  studio.selectedClip = { trackId: track.id, clipId: clip.id }
  lastInsert.value = '✓ ' + t('play.smartClipAdded', { bars: SMART_BARS, bar: startBar + 1 })
  emit('changed')
}

function diceSmart() {
  for (const e of smartEls.value) {
    e.placed = Math.random() < (['Kick', 'Snare', 'Hi-Hat'].includes(e.label) ? 0.95 : 0.45)
    e.x = 0.15 + Math.random() * 0.7
    e.y = 0.15 + Math.random() * 0.7
  }
  regenerateSmart()
}

// chip dragging on the board
const boardEl = ref<HTMLElement | null>(null)
let dragEl: SmartEl | null = null
function chipDown(e: PointerEvent, el: SmartEl) {
  dragEl = el
  window.addEventListener('pointermove', chipMove)
  window.addEventListener('pointerup', chipUp, { once: true })
  chipMove(e)
}
function chipMove(e: PointerEvent) {
  const b = boardEl.value
  if (!dragEl || !b) return
  const r = b.getBoundingClientRect()
  const x = (e.clientX - r.left) / r.width
  const y = (e.clientY - r.top) / r.height
  if (x >= -0.08 && x <= 1.08 && y >= -0.08 && y <= 1.08) {
    dragEl.placed = true
    dragEl.x = Math.min(Math.max(x, 0.02), 0.98)
    dragEl.y = Math.min(Math.max(y, 0.02), 0.98)
  } else {
    dragEl.placed = false
  }
}
function chipUp() {
  window.removeEventListener('pointermove', chipMove)
  if (dragEl) {
    playDrum(dragEl.midis[0])
    regenerateSmart()
  }
  dragEl = null
}

// ---------------- drums: pad grid ----------------
// svg key: which DRUM_SVG glyph draws this pad (the app's own drum icon set)
const PADS = [
  { midi: 49, label: 'Crash', svg: 'Crash' }, { midi: 51, label: 'Ride', svg: 'Ride' },
  { midi: 46, label: 'Open Hat', svg: 'Open Hat' }, { midi: 42, label: 'Hi-Hat', svg: 'Hi-Hat' },
  { midi: 50, label: 'Hi Tom', svg: 'Toms' }, { midi: 47, label: 'Mid Tom', svg: 'Toms' },
  { midi: 45, label: 'Lo Tom', svg: 'Lo Tom' }, { midi: 39, label: 'Clap', svg: 'Clap' },
  { midi: 70, label: 'Shaker', svg: 'Shaker' }, { midi: 37, label: 'Rimshot', svg: 'Snare' },
  { midi: 38, label: 'Snare', svg: 'Snare' }, { midi: 36, label: 'Kick', svg: 'Kick' },
]
const hitPad = ref<number | null>(null)
function tapPad(midi: number) {
  playDrum(midi)
  insertNotes([midi], 0.2, 105)
  hitPad.value = midi
  setTimeout(() => { if (hitPad.value === midi) hitPad.value = null }, 150)
}

// ---------------- chords: diatonic strips ----------------
const NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
const MAJOR = [0, 2, 4, 5, 7, 9, 11]
const MINOR = [0, 2, 3, 5, 7, 8, 10]

const keyInfo = computed(() => {
  const key = studio.project?.key ?? 'C major'
  const m = key.match(/^([A-G][#b]?)\s*(minor|min|m)?/i)
  const names: Record<string, number> = { C: 0, 'C#': 1, DB: 1, D: 2, 'D#': 3, EB: 3, E: 4, F: 5, 'F#': 6, GB: 6, G: 7, 'G#': 8, AB: 8, A: 9, 'A#': 10, BB: 10, B: 11 }
  const root = m ? (names[m[1].toUpperCase()] ?? 0) : 0
  return { root, minor: !!m?.[2] }
})

interface ChordStrip { name: string; midis: number[] }
const chords = computed<ChordStrip[]>(() => {
  const { root, minor } = keyInfo.value
  const scale = minor ? MINOR : MAJOR
  const strips: ChordStrip[] = []
  for (let deg = 0; deg < 7; deg++) {
    const pcs = [0, 2, 4].map((o) => (root + scale[(deg + o) % 7]) % 12)
    const third = (pcs[1] - pcs[0] + 12) % 12
    const fifth = (pcs[2] - pcs[0] + 12) % 12
    const quality = fifth === 6 ? 'dim' : third === 3 ? 'm' : ''
    const base = 48 + pcs[0]
    const midis = [base, base + ((pcs[1] - pcs[0] + 12) % 12), base + ((pcs[2] - pcs[0] + 12) % 12), base + 12]
    strips.push({ name: NOTE_NAMES[pcs[0]] + quality, midis })
  }
  return strips
})

const activeStrip = ref<number | null>(null)
const isStrings = computed(() => ['strings', 'brass'].includes(props.track.track_type))
function tapChord(i: number, zone: number) {
  const strip = chords.value[i]
  // zone 0 = high strum, later zones = lower/arpeggio feel
  const stagger = isStrings.value ? 0.02 : 0.045
  strip.midis.forEach((m, j) => playTone(m + (zone === 0 ? 12 : 0), isStrings.value ? 1.2 : 0.8, j * stagger, 0.12))
  insertNotes(strip.midis.map((m) => m + (zone === 0 ? 12 : 0)),
              isStrings.value ? 2 : 1, 95, 0.02)
  activeStrip.value = i
  setTimeout(() => { if (activeStrip.value === i) activeStrip.value = null }, 250)
}

// ---------------- keys: playable keyboard ----------------
const KEY_START = 48 // C3
const KEY_COUNT = 25 // 2 octaves
const whiteKeys = computed(() => {
  const out: { midi: number; label: string }[] = []
  for (let m = KEY_START; m < KEY_START + KEY_COUNT; m++) {
    if (![1, 3, 6, 8, 10].includes(m % 12)) out.push({ midi: m, label: m % 12 === 0 ? 'C' + (Math.floor(m / 12) - 1) : '' })
  }
  return out
})
const blackKeys = computed(() => {
  const out: { midi: number; offset: number }[] = []
  let whiteIndex = 0
  for (let m = KEY_START; m < KEY_START + KEY_COUNT; m++) {
    if ([1, 3, 6, 8, 10].includes(m % 12)) out.push({ midi: m, offset: whiteIndex })
    else whiteIndex++
  }
  return out
})
const pressedKey = ref<number | null>(null)
function tapKey(midi: number) {
  playTone(midi, 0.6)
  insertNotes([midi], 0.5, 96)
  pressedKey.value = midi
  setTimeout(() => { if (pressedKey.value === midi) pressedKey.value = null }, 180)
}

const surface = computed<'drums' | 'chords' | 'keys'>(() => {
  const t = props.track.track_type
  if (t === 'drums') return 'drums'
  if (['guitar', 'strings', 'brass'].includes(t)) return 'chords'
  return 'keys'
})
const bgImage = computed(() => {
  if (surface.value === 'drums') return '/instruments/drums-bg.png'
  if (props.track.track_type === 'guitar') return '/instruments/guitar-bg.png'
  if (surface.value === 'chords') return '/instruments/strings-bg.png'
  return ''
})
</script>

<template>
  <div class="play-surface" :style="bgImage ? { backgroundImage: `linear-gradient(rgba(10,12,16,0.55), rgba(10,12,16,0.7)), url(${bgImage})` } : {}">
    <div class="hint-bar">
      <div class="mode-switch">
        <button :class="{ on: !writeMode }" :title="t('play.practiceTip')"
                @click="writeMode = false">👂 {{ t('play.practice') }}</button>
        <button :class="{ on: writeMode }" class="write"
                :title="t('play.writeTip')"
                @click="writeMode = true">
          <span class="rec-dot" :class="{ live: writeMode }" /> {{ t('play.write') }}
        </button>
      </div>
      <span v-if="writeMode" class="rec-banner">● {{ t('play.recBanner') }}</span>
      <button class="loop-btn" :class="{ on: looping }" :disabled="loopLoading"
              :title="t('play.loopTip')"
              @click="toggleLoop">
        {{ loopLoading ? '⏳' : looping ? '■ ' + t('play.stopLoop') : '▶ ' + t('play.loop') }}
      </button>
      <span class="dim hint-text">
        {{ writeMode ? t('play.writeHint') : t('play.practiceHint') }}
        <span v-if="lastInsert"> · {{ lastInsert }}</span>
      </span>
    </div>
    <div v-if="['lead_vocal', 'backing_vocal'].includes(track.track_type)" class="vocal-note dim">
      🎤 {{ t('play.vocalNote') }}
    </div>

    <!-- drums: smart board or pads -->
    <template v-if="surface === 'drums'">
      <div v-if="showDrumCoach" class="coach">
        <strong>{{ t('play.coachTitle') }}</strong>
        <span>{{ t('play.coachBody') }}</span>
        <span>{{ t('play.coachAdd') }}</span>
        <button class="coach-close" @click="dismissDrumCoach">{{ t('play.gotIt') }}</button>
      </div>
      <div class="drum-mode">
        <button :class="{ on: drumMode === 'smart' }"
                :title="t('play.smartDesc')"
                @click="drumMode = 'smart'">{{ t('play.smartDrums') }}</button>
        <button :class="{ on: drumMode === 'seq' }"
                :title="t('play.seqDesc')"
                @click="drumMode = 'seq'">{{ t('play.beatSequencer') }}</button>
        <button :class="{ on: drumMode === 'pads' }"
                :title="t('play.padsDesc')"
                @click="drumMode = 'pads'">{{ t('play.pads') }}</button>
        <span class="mode-desc dim">{{
          drumMode === 'smart' ? t('play.smartDesc')
          : drumMode === 'seq' ? t('play.seqDesc')
          : t('play.padsDesc') }}</span>
        <template v-if="drumMode === 'smart'">
          <button class="dice" :title="t('play.diceTip')" @click="diceSmart">🎲</button>
          <button class="reset" :title="t('play.resetTip')" @click="resetBoard">{{ t('play.reset') }}</button>
          <button class="audition" :class="{ on: looping }" :disabled="loopLoading"
                  :title="t('seq.previewTip')"
                  @click="toggleLoop">
            {{ loopLoading ? '⏳ ' + t('seq.rendering') : looping ? '■ ' + t('common.stop') : '▶ ' + t('seq.previewLoop') }}
          </button>
          <button class="add-clip" :title="t('play.addClipTip')"
                  @click="addSmartAsClip">＋ {{ t('seq.addAsClip') }}</button>
        </template>
      </div>
      <div v-if="drumMode === 'smart'" class="smart-wrap">
        <!-- kit picker (GarageBand-style left panel) -->
        <div v-if="kits.length" class="kit-panel">
          <div class="kit-visual" v-html="DRUM_SVG['Toms'] + DRUM_SVG['Crash']" />
          <button class="kit-arrow" :title="t('play.prevKit')" @click="pickKit(-1)">‹</button>
          <div class="kit-name" :title="currentKit?.soundfont">
            {{ currentKit?.label ?? 'Drum Kit' }}
          </div>
          <button class="kit-arrow" :title="t('play.nextKit')" @click="pickKit(1)">›</button>
          <div class="dim tiny">{{ t('play.kitCount', { i: kitIndex + 1, n: kits.length }) }}</div>
        </div>
        <div ref="boardEl" class="smart-board">
          <span class="axis top">{{ t('play.loud') }}</span>
          <span class="axis bottom">{{ t('play.quiet') }}</span>
          <span class="axis left">{{ t('play.simple') }}</span>
          <span class="axis right">{{ t('play.complex') }}</span>
          <div v-for="el in smartEls.filter(e => e.placed)" :key="el.label" class="smart-chip on-board"
               :style="{ left: el.x * 100 + '%', top: el.y * 100 + '%' }"
               @pointerdown.prevent="chipDown($event, el)">
            <span v-if="DRUM_SVG[el.label]" class="chip-svg" v-html="DRUM_SVG[el.label]" />
            <span v-else>{{ el.icon }}</span>
            <span class="chip-label">{{ el.label }}</span>
          </div>
        </div>
        <div class="smart-tray">
          <div class="dim tiny">{{ t('play.dragOnto') }}</div>
          <div v-for="el in smartEls.filter(e => !e.placed)" :key="el.label" class="smart-chip"
               @pointerdown.prevent="chipDown($event, el)">
            <span v-if="DRUM_SVG[el.label]" class="chip-svg" v-html="DRUM_SVG[el.label]" />
            <span v-else>{{ el.icon }}</span>
            <span class="chip-label">{{ el.label }}</span>
          </div>
        </div>
      </div>
      <BeatSequencer v-else-if="drumMode === 'seq'"
                     :track="props.track" :clip="props.clip"
                     @changed="emit('changed')" />
      <div v-else class="pads">
        <button v-for="p in PADS" :key="p.midi" class="pad-btn"
                :class="{ hit: hitPad === p.midi }" @pointerdown="tapPad(p.midi)">
          <span class="pad-icon" v-html="DRUM_SVG[p.svg] ?? DRUM_SVG['Toms']" />
          <span class="pad-label">{{ p.label }}</span>
        </button>
      </div>
    </template>

    <!-- chord strips -->
    <div v-else-if="surface === 'chords'" class="strips">
      <div v-for="(c, i) in chords" :key="c.name" class="strip"
           :class="{ active: activeStrip === i }">
        <div class="strip-name" @pointerdown="tapChord(i, 0)">{{ c.name }}</div>
        <div v-for="z in 3" :key="z" class="strip-zone" @pointerdown="tapChord(i, z)" />
      </div>
    </div>

    <!-- keyboard -->
    <div v-else class="kbd">
      <div class="white-row">
        <div v-for="k in whiteKeys" :key="k.midi" class="wkey"
             :class="{ pressed: pressedKey === k.midi }" @pointerdown="tapKey(k.midi)">
          <span class="wlabel">{{ k.label }}</span>
        </div>
      </div>
      <div v-for="b in blackKeys" :key="b.midi" class="bkey"
           :class="{ pressed: pressedKey === b.midi }"
           :style="{ left: `calc(${(b.offset / whiteKeys.length) * 100}% - 1.4%)` }"
           @pointerdown="tapKey(b.midi)" />
    </div>
  </div>
</template>

<style scoped>
.play-surface { height: 100%; display: flex; flex-direction: column; background-size: cover; background-position: center; border-radius: 0 0 8px 8px; overflow: hidden; position: relative; }
.hint-bar { display: flex; align-items: center; gap: 10px; padding: 5px 12px; flex: none; }
.mode-switch { display: flex; gap: 2px; background: rgba(0,0,0,0.45); border-radius: 6px; padding: 2px; }
.mode-switch button { border: none; background: transparent; color: var(--text-dim); font-size: 11px; padding: 2px 10px; }
.mode-switch button.on { background: var(--bg-elevated); color: var(--text); border-radius: 4px; }
.mode-switch button.write.on { background: var(--err); color: #fff; }
.rec-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #777; margin-right: 3px; }
.rec-dot.live { background: #fff; animation: rec-pulse 1.1s ease-in-out infinite; }
@keyframes rec-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.25; } }
.rec-banner { font-size: 11px; color: var(--err); font-weight: 700; }
.coach { display: flex; flex-direction: column; gap: 4px; font-size: 12px; background: rgba(79,156,249,0.12); border: 1px solid var(--accent); border-radius: 8px; padding: 8px 12px; margin: 0 12px 6px; position: relative; }
.coach-close { align-self: flex-end; font-size: 11px; padding: 2px 10px; }
.mode-desc { font-size: 11px; margin-left: 6px; }
.loop-btn { font-size: 11px; padding: 2px 10px; }
.loop-btn.on { border-color: var(--accent); color: var(--accent); }
.hint-text { font-size: 11px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.vocal-note { font-size: 11px; padding: 0 12px 4px; }
/* smart drums */
.drum-mode { display: flex; gap: 4px; padding: 0 12px 4px; align-items: center; }
.drum-mode button { padding: 2px 10px; font-size: 11px; border: none; background: rgba(0,0,0,0.4); color: var(--text-dim); border-radius: 5px; }
.drum-mode button.on { color: var(--text); background: var(--bg-elevated); }
.drum-mode .dice { font-size: 14px; margin-left: auto; }
.drum-mode .reset { font-size: 11px; }
.drum-mode .add-clip { font-size: 11px; border-color: var(--accent); color: var(--accent); }
.drum-mode .audition { font-size: 11px; font-weight: 600; border-color: #3ecf6e; border-radius: 14px; }
.drum-mode .audition.on { color: #3ecf6e; box-shadow: 0 0 10px rgba(62,207,110,0.35); }
/* kit picker */
.kit-panel { width: 110px; flex: none; display: flex; flex-direction: column; align-items: center; gap: 6px; background: rgba(22,25,31,0.85); border: 1px solid #3a3f49; border-radius: 12px; padding: 12px 6px; }
.kit-visual { color: var(--text-dim); display: flex; }
.kit-visual :deep(svg) { width: 34px; height: 34px; }
.kit-name { font-size: 11px; font-weight: 600; text-align: center; min-height: 28px; }
.kit-arrow { padding: 0 10px; font-size: 16px; }
.chip-svg { color: var(--text); display: flex; }
.chip-svg :deep(svg) { width: 22px; height: 22px; }
.smart-wrap { flex: 1; display: flex; gap: 10px; padding: 0 12px 12px; min-height: 0; }
.smart-board { flex: 1; position: relative; border: 2px solid #3a3f49; border-radius: 12px; background: radial-gradient(ellipse at center, rgba(45,49,58,0.85), rgba(18,20,24,0.92)); }
.axis { position: absolute; font-size: 9px; color: var(--text-dim); letter-spacing: 0.1em; text-transform: uppercase; }
.axis.top { top: 4px; left: 50%; transform: translateX(-50%); }
.axis.bottom { bottom: 4px; left: 50%; transform: translateX(-50%); }
.axis.left { left: 6px; top: 50%; transform: translateY(-50%) rotate(-90deg); transform-origin: center; }
.axis.right { right: 6px; top: 50%; transform: translateY(-50%) rotate(90deg); transform-origin: center; }
.smart-chip { display: inline-flex; flex-direction: column; align-items: center; gap: 1px; background: rgba(30,33,40,0.95); border: 1px solid #4a5160; border-radius: 50%; width: 52px; height: 52px; justify-content: center; cursor: grab; user-select: none; font-size: 16px; box-shadow: 0 2px 6px rgba(0,0,0,0.6); }
.smart-chip.on-board { position: absolute; transform: translate(-50%, -50%); border-color: var(--accent); }
.smart-chip:active { cursor: grabbing; border-color: var(--accent); }
.chip-label { font-size: 8px; color: var(--text-dim); }
.smart-tray { width: 120px; flex: none; display: flex; flex-wrap: wrap; gap: 6px; align-content: flex-start; padding-top: 14px; position: relative; }
.smart-tray .tiny { position: absolute; top: 0; left: 0; font-size: 9px; }
/* pads */
.pads { flex: 1; display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; padding: 4px 12px 12px; }
.pad-btn { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 3px; border-radius: 10px; background: rgba(30,33,40,0.82); border: 1px solid #3a3f49; box-shadow: inset 0 -3px 8px rgba(0,0,0,0.5), 0 2px 4px rgba(0,0,0,0.4); cursor: pointer; min-height: 0; }
.pad-btn:active, .pad-btn.hit { background: rgba(79,156,249,0.35); border-color: var(--accent); box-shadow: inset 0 0 14px rgba(79,156,249,0.4); }
.pad-icon { display: flex; color: currentColor; }
.pad-icon :deep(svg) { width: 26px; height: 26px; }
.pad-label { font-size: 10px; color: var(--text-dim); }
/* chord strips */
.strips { flex: 1; display: flex; gap: 6px; padding: 4px 12px 12px; }
.strip { flex: 1; display: flex; flex-direction: column; border-radius: 8px 8px 4px 4px; overflow: hidden; border: 1px solid rgba(0,0,0,0.5); background: rgba(122,72,32,0.35); box-shadow: 0 2px 6px rgba(0,0,0,0.5); }
.strip.active { outline: 2px solid var(--accent); }
.strip-name { text-align: center; font-weight: 700; font-size: 15px; padding: 8px 0; background: rgba(0,0,0,0.35); color: #ffe9c9; cursor: pointer; text-shadow: 0 1px 2px #000; }
.strip-zone { flex: 1; border-top: 1px solid rgba(255,235,200,0.25); cursor: pointer; }
.strip-zone:hover, .strip-name:hover { background: rgba(255,255,255,0.08); }
/* keyboard */
.kbd { flex: 1; position: relative; padding: 4px 12px 12px; }
.white-row { display: flex; height: 100%; border-radius: 6px; overflow: hidden; }
.wkey { flex: 1; background: linear-gradient(#fdfdfd, #e8e8e8); border: 1px solid #999; border-radius: 0 0 5px 5px; cursor: pointer; position: relative; display: flex; align-items: flex-end; justify-content: center; }
.wkey.pressed, .wkey:active { background: linear-gradient(#cfe0ff, #a9c8fb); }
.wlabel { font-size: 9px; color: #888; padding-bottom: 4px; }
.bkey { position: absolute; top: 4px; width: 2.9%; height: 58%; background: linear-gradient(#333, #111); border-radius: 0 0 4px 4px; cursor: pointer; box-shadow: 1px 2px 4px rgba(0,0,0,0.6); z-index: 2; }
.bkey.pressed, .bkey:active { background: linear-gradient(#4f9cf9, #2b6cd4); }
</style>
