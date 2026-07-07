<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Clip, NoteEvent, Track } from '../api/types'
import { useStudioStore } from '../stores/studio'
import { usePlaybackStore } from '../stores/playback'

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
  const at = playheadBeatInClip()
  midis.forEach((m, i) => {
    props.clip.note_events.push({
      id: uid(), pitch: '', midi_note: m,
      start_beat: Math.min(at + i * stagger, props.clip.duration_beats - 0.1),
      duration_beats: Math.min(dur, props.clip.duration_beats - at),
      velocity: vel, lyric_syllable: '',
    } as NoteEvent)
  })
  lastInsert.value = `added at beat ${(at + props.clip.start_beat).toFixed(2)}`
  emit('changed')
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
    <div class="hint dim">
      tap to hear & write at the playhead <span v-if="lastInsert">· {{ lastInsert }}</span>
    </div>

    <!-- drum pads -->
    <div v-if="surface === 'drums'" class="pads">
      <button v-for="p in PADS" :key="p.midi" class="pad-btn"
              :class="{ hit: hitPad === p.midi }" @pointerdown="tapPad(p.midi)">
        <span class="pad-icon">{{ p.icon }}</span>
        <span class="pad-label">{{ p.label }}</span>
      </button>
    </div>

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
.hint { font-size: 11px; padding: 6px 12px; flex: none; }
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
