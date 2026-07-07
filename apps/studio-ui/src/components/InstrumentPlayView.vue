<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { api } from '../api/client'
import type { Clip, NoteEvent, Track } from '../api/types'
import { useStudioStore } from '../stores/studio'
import { usePlaybackStore } from '../stores/playback'

// monochrome drum-piece glyphs (GarageBand-style)
const DRUM_SVG: Record<string, string> = {
  Kick: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="3"/></svg>',
  Snare: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><ellipse cx="12" cy="8" rx="8" ry="3"/><path d="M4 8v6c0 1.7 3.6 3 8 3s8-1.3 8-3V8"/><path d="M4 11h16" stroke-width="1"/></svg>',
  'Hi-Hat': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><ellipse cx="12" cy="8" rx="9" ry="2"/><ellipse cx="12" cy="11" rx="9" ry="2"/><path d="M12 12.5V21"/></svg>',
  'Open Hat': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><ellipse cx="12" cy="6" rx="9" ry="2" transform="rotate(-8 12 6)"/><ellipse cx="12" cy="12" rx="9" ry="2" transform="rotate(6 12 12)"/><path d="M12 14V21"/></svg>',
  Ride: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><ellipse cx="12" cy="8" rx="10" ry="2.6"/><circle cx="12" cy="7.4" r="1.2"/><path d="M12 10.5V21"/></svg>',
  Crash: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><ellipse cx="12" cy="7" rx="9.5" ry="2.4" transform="rotate(-14 12 7)"/><path d="M12 9.5V21"/><path d="M8 21h8"/></svg>',
  Toms: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><ellipse cx="7.5" cy="9" rx="5" ry="2"/><path d="M2.5 9v5c0 1.1 2.2 2 5 2s5-.9 5-2V9"/><ellipse cx="17.5" cy="8" rx="4" ry="1.7"/><path d="M13.5 8v4.5c0 .9 1.8 1.6 4 1.6s4-.7 4-1.6V8"/></svg>',
  Clap: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M9 12 4 7m5 9-6-3m7 7-5-1"/><path d="M12 11c1-3 3-5 6-5 2 0 3 1.5 2 3.5S16 14 14 17c-1.4 2-4 2.5-5.5 1"/></svg>',
  Shaker: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="8" y="4" width="8" height="16" rx="4"/><circle cx="11" cy="9" r="0.7" fill="currentColor"/><circle cx="13.5" cy="12" r="0.7" fill="currentColor"/><circle cx="11.5" cy="15" r="0.7" fill="currentColor"/></svg>',
}

const props = defineProps<{ track: Track; clip: Clip }>()
const emit = defineEmits<{ changed: [] }>()

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

// ---------------- loop preview with the REAL instrument sound -------------
const looping = ref(false)
const loopLoading = ref(false)
let loopAudio: HTMLAudioElement | null = null
let loopTimer: ReturnType<typeof setTimeout> | null = null

function loopNotes() {
  const bpb = studio.manifest?.beats_per_bar ?? 4
  const span = bpb * 2  // first two bars of the clip
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
  if (!notes.length) { lastInsert.value = 'nothing to loop yet — place some pieces'; return }
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
  lastInsert.value = `♪ written at beat ${(at + props.clip.start_beat).toFixed(2)}`
  emit('changed')
  queueLoopRefresh()
}

// ---------------- smart drums (GarageBand-style board) ----------------
const drumMode = ref<'smart' | 'pads'>('smart')

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
  lastInsert.value = `kit: ${k.label}`
  emit('changed')
  if (looping.value) void refreshLoop()   // hear the new kit immediately
  else playDrum(36)
}

function resetBoard() {
  for (const e of smartEls.value) e.placed = false
  props.clip.note_events = []
  lastInsert.value = 'board cleared'
  emit('changed')
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

function smartPattern(el: SmartEl): { beat: number; midi: number; vel: number }[] {
  const c = el.x            // simple → complex
  const loud = 1 - el.y     // board top = loud
  const bars = Math.max(Math.floor(props.clip.duration_beats / beatsPerBar.value), 1)
  const base = Math.round(45 + 75 * loud)
  const out: { beat: number; midi: number; vel: number }[] = []
  const push = (bar: number, b: number, midi: number, velScale = 1) => {
    const beat = bar * beatsPerBar.value + b
    if (beat < props.clip.duration_beats) {
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

function regenerateSmart() {
  props.clip.note_events = smartEls.value
    .filter((e) => e.placed)
    .flatMap((e) => smartPattern(e).map((h) => ({
      id: uid(), pitch: '', midi_note: h.midi, start_beat: h.beat,
      duration_beats: 0.2, velocity: h.vel, lyric_syllable: '',
    } as NoteEvent)))
  lastInsert.value = 'pattern updated'
  emit('changed')
  queueLoopRefresh()
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
const PADS = [
  { midi: 49, label: 'Crash', icon: '💥' }, { midi: 51, label: 'Ride', icon: '🛎' },
  { midi: 46, label: 'Open Hat', icon: '✨' }, { midi: 42, label: 'Hi-Hat', icon: '🎩' },
  { midi: 50, label: 'Hi Tom', icon: '🥁' }, { midi: 47, label: 'Mid Tom', icon: '🥁' },
  { midi: 45, label: 'Lo Tom', icon: '🥁' }, { midi: 39, label: 'Clap', icon: '👏' },
  { midi: 70, label: 'Shaker', icon: '🪇' }, { midi: 37, label: 'Rimshot', icon: '🪘' },
  { midi: 38, label: 'Snare', icon: '🥁' }, { midi: 36, label: 'Kick', icon: '🦶' },
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
        <button :class="{ on: !writeMode }" @click="writeMode = false">👂 Practice</button>
        <button :class="{ on: writeMode }" class="write" @click="writeMode = true">● Write</button>
      </div>
      <button class="loop-btn" :class="{ on: looping }" :disabled="loopLoading"
              title="loop the first 2 bars with the real instrument sound"
              @click="toggleLoop">
        {{ loopLoading ? '⏳' : looping ? '■ Stop loop' : '▶ Loop' }}
      </button>
      <span class="dim hint-text">
        {{ writeMode ? 'taps are written at the playhead and step forward'
                     : 'taps just play — switch to ● Write to record' }}
        <span v-if="lastInsert"> · {{ lastInsert }}</span>
      </span>
    </div>
    <div v-if="['lead_vocal', 'backing_vocal'].includes(track.track_type)" class="vocal-note dim">
      🎤 This keyboard writes the <strong>vocal melody</strong> — the AI voice sings your
      lyrics on these notes. Manage lyrics in the <strong>Lyrics</strong> tab
      (“Sing these lyrics” writes melodies automatically).
    </div>

    <!-- drums: smart board or pads -->
    <template v-if="surface === 'drums'">
      <div class="drum-mode">
        <button :class="{ on: drumMode === 'smart' }" @click="drumMode = 'smart'">Smart Drums</button>
        <button :class="{ on: drumMode === 'pads' }" @click="drumMode = 'pads'">Pads</button>
        <template v-if="drumMode === 'smart'">
          <button class="dice" title="random groove" @click="diceSmart">🎲</button>
          <button class="reset" title="clear the board" @click="resetBoard">⏻ Reset</button>
        </template>
      </div>
      <div v-if="drumMode === 'smart'" class="smart-wrap">
        <!-- kit picker (GarageBand-style left panel) -->
        <div v-if="kits.length" class="kit-panel">
          <div class="kit-visual" v-html="DRUM_SVG['Toms'] + DRUM_SVG['Crash']" />
          <button class="kit-arrow" title="previous kit" @click="pickKit(-1)">‹</button>
          <div class="kit-name" :title="currentKit?.soundfont">
            {{ currentKit?.label ?? 'Drum Kit' }}
          </div>
          <button class="kit-arrow" title="next kit" @click="pickKit(1)">›</button>
          <div class="dim tiny">{{ kitIndex + 1 }} / {{ kits.length }} kits</div>
        </div>
        <div ref="boardEl" class="smart-board">
          <span class="axis top">loud</span>
          <span class="axis bottom">quiet</span>
          <span class="axis left">simple</span>
          <span class="axis right">complex</span>
          <div v-for="el in smartEls.filter(e => e.placed)" :key="el.label" class="smart-chip on-board"
               :style="{ left: el.x * 100 + '%', top: el.y * 100 + '%' }"
               @pointerdown.prevent="chipDown($event, el)">
            <span v-if="DRUM_SVG[el.label]" class="chip-svg" v-html="DRUM_SVG[el.label]" />
            <span v-else>{{ el.icon }}</span>
            <span class="chip-label">{{ el.label }}</span>
          </div>
        </div>
        <div class="smart-tray">
          <div class="dim tiny">drag onto the board</div>
          <div v-for="el in smartEls.filter(e => !e.placed)" :key="el.label" class="smart-chip"
               @pointerdown.prevent="chipDown($event, el)">
            <span v-if="DRUM_SVG[el.label]" class="chip-svg" v-html="DRUM_SVG[el.label]" />
            <span v-else>{{ el.icon }}</span>
            <span class="chip-label">{{ el.label }}</span>
          </div>
        </div>
      </div>
      <div v-else class="pads">
        <button v-for="p in PADS" :key="p.midi" class="pad-btn"
                :class="{ hit: hitPad === p.midi }" @pointerdown="tapPad(p.midi)">
          <span class="pad-icon">{{ p.icon }}</span>
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
.pad-icon { font-size: 22px; }
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
