<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import type { Clip, NoteEvent, Track } from '../api/types'
import { useStudioStore } from '../stores/studio'
import { DRUM_SVG } from '../lib/drumIcons'

const props = defineProps<{ track: Track; clip: Clip }>()
const emit = defineEmits<{ changed: [] }>()
const studio = useStudioStore()
const uid = () => crypto.randomUUID().replace(/-/g, '')

// GarageBand-style lanes, each with its own color
const LANES = [
  { midi: 36, label: 'Kick', color: '#e73896' },
  { midi: 38, label: 'Snare', color: '#e6a23c' },
  { midi: 39, label: 'Clap', color: '#c99215' },
  { midi: 42, label: 'Hi-Hat', color: '#2dd4cf' },
  { midi: 46, label: 'Open Hat', color: '#1fa89b' },
  { midi: 51, label: 'Ride', color: '#3b82c4' },
  { midi: 49, label: 'Crash', color: '#2a7f8f' },
  { midi: 70, label: 'Shaker', color: '#a06cf2' },
  { midi: 45, label: 'Lo Tom', color: '#8d5cd4' },
  { midi: 50, label: 'Toms', color: '#3ecf6e' },
]

const STEP = 0.25
const bars = ref(1)
const beatsPerBar = computed(() => studio.manifest?.beats_per_bar ?? 4)
const stepCount = computed(() => Math.round(bars.value * beatsPerBar.value / STEP))

type EditTool = 'toggle' | 'velocity'
const tool = ref<EditTool>('toggle')

function noteAt(midi: number, step: number): NoteEvent | undefined {
  return props.clip.note_events.find((n) =>
    n.midi_note === midi && Math.abs(n.start_beat - step * STEP) < STEP / 2)
}

function tapStep(midi: number, step: number) {
  const existing = noteAt(midi, step)
  if (tool.value === 'velocity') {
    if (existing) {
      // cycle soft → medium → accent
      existing.velocity = existing.velocity < 75 ? 95 : existing.velocity < 110 ? 122 : 60
    } else {
      addNote(midi, step, 95)
    }
  } else if (existing) {
    props.clip.note_events = props.clip.note_events.filter((n) => n.id !== existing.id)
  } else {
    addNote(midi, step, step % 4 === 0 ? 110 : 90)
  }
  emit('changed')
  queueLoopRefresh()
}

function addNote(midi: number, step: number, vel: number) {
  props.clip.note_events.push({
    id: uid(), pitch: '', midi_note: midi, start_beat: step * STEP,
    duration_beats: 0.2, velocity: vel, lyric_syllable: '',
  } as NoteEvent)
}

// --- pattern presets (steps are 16th indices within one bar) ---
const PATTERNS: Record<string, Partial<Record<number, number[]>>> = {
  'Modern 808': { 36: [0, 7, 10], 39: [4, 12], 42: [0, 2, 4, 6, 8, 10, 12, 14], 46: [15], 70: [1, 3, 5, 7, 9, 11, 13, 15] },
  'Hip-Hop': { 36: [0, 6, 10], 38: [4, 12], 42: [0, 2, 4, 6, 8, 10, 12, 14], 46: [7] },
  'House': { 36: [0, 4, 8, 12], 39: [4, 12], 46: [2, 6, 10, 14], 70: [0, 2, 4, 6, 8, 10, 12, 14] },
  'Rock': { 36: [0, 8, 10], 38: [4, 12], 42: [0, 2, 4, 6, 8, 10, 12, 14], 49: [0] },
  'Funk': { 36: [0, 3, 10], 38: [4, 12, 14], 42: [0, 2, 4, 5, 6, 8, 10, 12, 14, 15], 46: [7] },
  'Techno': { 36: [0, 4, 8, 12], 39: [4, 12], 42: [2, 6, 10, 14], 51: [0, 8], 70: [1, 3, 5, 7, 9, 11, 13, 15] },
}
const patternName = ref('')

function applyPattern(name: string) {
  const pat = PATTERNS[name]
  if (!pat) return
  const seqMidis = new Set(LANES.map((l) => l.midi))
  const span = stepCount.value * STEP
  props.clip.note_events = props.clip.note_events.filter(
    (n) => n.start_beat >= span || !seqMidis.has(n.midi_note))
  for (let bar = 0; bar < bars.value; bar++) {
    for (const [midi, steps] of Object.entries(pat)) {
      for (const s of steps ?? []) {
        addNote(Number(midi), bar * 16 + s, s % 4 === 0 ? 110 : 90)
      }
    }
  }
  patternName.value = name
  emit('changed')
  queueLoopRefresh()
}

function clearGrid() {
  const seqMidis = new Set(LANES.map((l) => l.midi))
  const span = stepCount.value * STEP
  props.clip.note_events = props.clip.note_events.filter(
    (n) => n.start_beat >= span || !seqMidis.has(n.midi_note))
  emit('changed')
  queueLoopRefresh()
}

function applyToClip() {
  // tile the sequencer bars across the whole clip
  const span = stepCount.value * STEP
  const pattern = props.clip.note_events.filter((n) => n.start_beat < span)
  const out = [...pattern]
  for (let offset = span; offset < props.clip.duration_beats - 0.01; offset += span) {
    for (const n of pattern) {
      if (offset + n.start_beat < props.clip.duration_beats) {
        out.push({ ...n, id: uid(), start_beat: offset + n.start_beat })
      }
    }
  }
  props.clip.note_events = out
  emit('changed')
}

// --- loop playback with the real kit + step highlight ---
const playing = ref(false)
const loading = ref(false)
const currentStep = ref(-1)
let audio: HTMLAudioElement | null = null
let raf = 0
let loopTimer: ReturnType<typeof setTimeout> | null = null

const loopSeconds = computed(() => {
  const bpm = studio.project?.bpm ?? 120
  return (stepCount.value * STEP * 60) / bpm
})

async function fetchLoop(): Promise<HTMLAudioElement | null> {
  const p = studio.project
  if (!p) return null
  const span = stepCount.value * STEP
  const notes = props.clip.note_events
    .filter((n) => n.start_beat < span)
    .map((n) => ({ midi_note: n.midi_note, start_beat: n.start_beat,
                   duration_beats: Math.min(n.duration_beats, span - n.start_beat),
                   velocity: n.velocity }))
  if (!notes.length) return null
  // a silent tail-guard note keeps the render exactly loop-length
  notes.push({ midi_note: 36, start_beat: span - 0.01, duration_beats: 0.01, velocity: 1 })
  const cfg = props.track.instrument_config
  const res = await fetch('/api/projects/preview/instrument', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ soundfont_asset_id: cfg.soundfont_asset_id,
                           bank: cfg.bank, program: cfg.program,
                           is_drum_kit: true, bpm: p.bpm, notes }),
  })
  if (!res.ok) throw new Error((await res.json()).detail ?? res.statusText)
  const el = new Audio(URL.createObjectURL(await res.blob()))
  el.loop = true
  return el
}

function tick() {
  if (!playing.value || !audio) return
  currentStep.value = Math.floor((audio.currentTime % loopSeconds.value)
    / (loopSeconds.value / stepCount.value)) % stepCount.value
  raf = requestAnimationFrame(tick)
}

async function togglePower() {
  if (playing.value) {
    playing.value = false
    currentStep.value = -1
    cancelAnimationFrame(raf)
    audio?.pause()
    audio = null
    return
  }
  loading.value = true
  try {
    const el = await fetchLoop()
    if (!el) return
    audio = el
    playing.value = true
    void el.play()
    raf = requestAnimationFrame(tick)
  } catch { /* preview unavailable */ }
  finally { loading.value = false }
}

function queueLoopRefresh() {
  if (!playing.value) return
  if (loopTimer) clearTimeout(loopTimer)
  loopTimer = setTimeout(async () => {
    try {
      const el = await fetchLoop()
      if (!el || !playing.value) return
      const t = audio?.currentTime ?? 0
      audio?.pause()
      audio = el
      el.currentTime = t % loopSeconds.value
      void el.play()
    } catch { /* keep old loop */ }
  }, 600)
}

onBeforeUnmount(() => { audio?.pause(); cancelAnimationFrame(raf) })
</script>

<template>
  <div class="seq">
    <div class="seq-grid">
      <div v-for="lane in LANES" :key="lane.midi" class="seq-row">
        <div class="seq-icon" :style="{ color: lane.color }"
             v-html="DRUM_SVG[lane.label] ?? DRUM_SVG['Toms']" />
        <div class="seq-cells">
          <div v-for="s in stepCount" :key="s" class="seq-cell"
               :class="{ beat: (s - 1) % 4 === 0, playhead: currentStep === s - 1 }"
               :style="{ background: noteAt(lane.midi, s - 1)
                 ? lane.color : lane.color + '22' }"
               @pointerdown.prevent="tapStep(lane.midi, s - 1)">
            <div v-if="tool === 'velocity' && noteAt(lane.midi, s - 1)" class="vel-dot"
                 :style="{ opacity: (noteAt(lane.midi, s - 1)?.velocity ?? 90) / 127 }" />
          </div>
        </div>
      </div>
    </div>
    <div class="seq-bar">
      <select class="pattern-pick" :value="patternName"
              @change="applyPattern(($event.target as HTMLSelectElement).value)">
        <option value="" disabled>Choose a pattern…</option>
        <option v-for="(_, name) in PATTERNS" :key="name" :value="name">{{ name }}</option>
      </select>
      <button class="power" :class="{ on: playing }" :disabled="loading"
              title="start/stop the loop (real kit sound)" @click="togglePower">⏻</button>
      <div class="tools">
        <button :class="{ on: tool === 'toggle' }" @click="tool = 'toggle'">Step On/Off</button>
        <button :class="{ on: tool === 'velocity' }" @click="tool = 'velocity'">Velocity</button>
      </div>
      <div class="tools">
        <button :class="{ on: bars === 1 }" @click="bars = 1">1 bar</button>
        <button :class="{ on: bars === 2 }" @click="bars = 2">2 bars</button>
      </div>
      <button class="tb" title="repeat this pattern across the whole clip" @click="applyToClip">⇥ Fill clip</button>
      <button class="tb" @click="clearGrid">✕ Clear</button>
    </div>
  </div>
</template>

<style scoped>
.seq { flex: 1; display: flex; flex-direction: column; min-height: 0; padding: 0 12px 10px; }
.seq-grid { flex: 1; overflow: auto; display: flex; flex-direction: column; gap: 3px; }
.seq-row { display: flex; align-items: center; gap: 6px; flex: 1; min-height: 20px; }
.seq-icon { width: 24px; flex: none; display: flex; }
.seq-icon :deep(svg) { width: 20px; height: 20px; }
.seq-cells { display: flex; gap: 3px; flex: 1; height: 100%; }
.seq-cell { flex: 1; border-radius: 4px; cursor: pointer; position: relative; transition: filter 0.05s; }
.seq-cell.beat { margin-left: 5px; }
.seq-cell:hover { filter: brightness(1.5); }
.seq-cell.playhead { outline: 2px solid #fff; outline-offset: -1px; }
.vel-dot { position: absolute; inset: 25%; border-radius: 50%; background: #fff; }
.seq-bar { display: flex; align-items: center; gap: 10px; padding-top: 8px; flex: none; flex-wrap: wrap; }
.pattern-pick { font-size: 12px; background: rgba(0,0,0,0.5); }
.power { font-size: 20px; padding: 2px 14px; border-radius: 20px; color: var(--text-dim); }
.power.on { color: #3ecf6e; border-color: #3ecf6e; box-shadow: 0 0 12px rgba(62,207,110,0.4); }
.tools { display: flex; gap: 2px; background: rgba(0,0,0,0.45); border-radius: 6px; padding: 2px; }
.tools button { border: none; background: transparent; color: var(--text-dim); font-size: 11px; padding: 2px 10px; }
.tools button.on { background: var(--bg-elevated); color: var(--text); border-radius: 4px; }
.tb { font-size: 11px; padding: 2px 10px; }
</style>
